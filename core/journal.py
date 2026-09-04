from datetime import date
from calendar import monthrange
from core.models import Mitarbeiter, TarifTabelle, SystemParameter

def get_sys_params(session, check_date):
    params = session.query(SystemParameter).filter(SystemParameter.gueltig_ab <= check_date).all()
    param_dict = {}
    for p in params:
        if p.schluessel not in param_dict or p.gueltig_ab > param_dict[p.schluessel]['date']:
            param_dict[p.schluessel] = {'val': p.wert, 'date': p.gueltig_ab}
            
    # HARTER CHECK: Alle Parameter müssen existieren, keine Fallbacks!
    required_keys = ['bbg_kv_pv', 'bbg_rv_av', 'ag_rv', 'ag_av', 'ag_kv_base', 'ag_pv', 'vbl_satz', 'u2_satz', 'luk_satz']
    for k in required_keys:
        if k not in param_dict:
            raise ValueError(f"Systemparameter '{k}' fehlt (Gültig am {check_date.strftime('%d.%m.%Y')}). Bitte unter 'System & Administration' anlegen.")
            
    return {k: v['val'] for k, v in param_dict.items()}

def generiere_mitarbeiter_lohnjournal(session, ma_id, start_jahr, start_monat, end_jahr, end_monat):
    ma = session.query(Mitarbeiter).filter_by(id=ma_id).first()
    if not ma: return []

    akt_jahr = start_jahr
    akt_monat = start_monat if start_monat else 1

    akkumuliert_sv_brutto_kv = 0.0
    akkumuliert_sv_brutto_rv = 0.0
    akkumuliert_bbg_kv = 0.0
    akkumuliert_bbg_rv = 0.0
    akkumuliert_obligo_jsz = 0.0
    akkumuliert_luk = 0.0

    jsz_basis_brutto = 0.0
    jsz_basis_pct = 0.0
    letztes_berechnetes_jsz_jahr = 0

    alle_eintraege = []

    while akt_jahr < end_jahr or (akt_jahr == end_jahr and akt_monat <= end_monat):

        # --- RENTEN-DECKEL (67 JAHRE) ---
        if ma.geburtsdatum:
            alter = akt_jahr - ma.geburtsdatum.year - ((akt_monat, 1) < (ma.geburtsdatum.month, ma.geburtsdatum.day))
            if alter >= 67: break 

        if akt_monat == 1:
            akkumuliert_sv_brutto_kv = 0.0
            akkumuliert_sv_brutto_rv = 0.0
            akkumuliert_bbg_kv = 0.0
            akkumuliert_bbg_rv = 0.0
            akkumuliert_obligo_jsz = 0.0
            akkumuliert_luk = 0.0

        anspruch_auf_jsz = True
        dez_1 = date(akt_jahr, 12, 1)
        if ma.geplanter_abgang and ma.geplanter_abgang < dez_1: anspruch_auf_jsz = False
        if ma.am_ifpt_seit and ma.am_ifpt_seit > dez_1: anspruch_auf_jsz = False

        aktive_monate_im_jahr = 0
        if anspruch_auf_jsz:
            for m in range(1, 13):
                m_start = date(akt_jahr, m, 1)
                m_end = date(akt_jahr, m, monthrange(akt_jahr, m)[1])
                e_start = max(m_start, ma.am_ifpt_seit) if ma.am_ifpt_seit else m_start
                e_end = min(m_end, ma.geplanter_abgang) if ma.geplanter_abgang else m_end
                if e_start <= m_end and e_end >= m_start: aktive_monate_im_jahr += 1

        # =========================================================================
        # TV-L KONFORM: NUR VOLLE MONATE AUS JULI, AUG, SEP ALS JSZ-BASIS
        # =========================================================================
        if akt_jahr != letztes_berechnetes_jsz_jahr:
            jsz_basis_brutto = 0.0
            jsz_basis_pct = 0.0
            if anspruch_auf_jsz:
                summe_brutto = 0.0
                monate_count = 0
                for bm in [7, 8, 9]:
                    bm_start = date(akt_jahr, bm, 1)
                    bm_end = date(akt_jahr, bm, monthrange(akt_jahr, bm)[1])
                    b_eff_start = max(bm_start, ma.am_ifpt_seit) if ma.am_ifpt_seit else bm_start
                    b_eff_end = min(bm_end, ma.geplanter_abgang) if ma.geplanter_abgang else bm_end
                    
                    # PRÜFUNG: Nur wenn es ein voller Kalendermonat ist!
                    if b_eff_start <= bm_start and b_eff_end >= bm_end:
                        b_az_pct = 0.0
                        for az in ma.arbeitszeiten:
                            if az.gueltig_ab <= bm_end and (not az.gueltig_bis or az.gueltig_bis >= bm_end):
                                b_az_pct = az.anteil_pct
                                break
                                
                        b_eg, b_stufe = None, None
                        for g in ma.gehaltsverlauf:
                            if g.gueltig_ab <= bm_end and (not g.gueltig_bis or g.gueltig_bis >= bm_end):
                                b_eg, b_stufe = str(g.entgeltgruppe), g.stufe
                                break
                                
                        if b_eg and b_stufe:
                            tarif = session.query(TarifTabelle).filter(
                                TarifTabelle.entgeltgruppe == b_eg,
                                TarifTabelle.stufe == b_stufe,
                                TarifTabelle.gueltig_ab <= bm_end
                            ).order_by(TarifTabelle.gueltig_ab.desc()).first()
                            
                            if tarif:
                                if tarif.jsz_prozent is None:
                                    raise ValueError(f"JSZ-Prozentsatz fehlt in der Tariftabelle für {b_eg} Stufe {b_stufe} (Gültig am {bm_end.strftime('%d.%m.%Y')}).")
                                summe_brutto += tarif.betrag_euro * b_az_pct
                                jsz_basis_pct = tarif.jsz_prozent
                                monate_count += 1
                            else:
                                raise ValueError(f"Keine Tariftabelle für {b_eg} Stufe {b_stufe} im Monat {bm:02d}/{akt_jahr} gefunden.")
                        else:
                            raise ValueError(f"Gehaltsverlauf (Entgeltgruppe/Stufe) fehlt für den Mitarbeiter {ma.vorname} {ma.nachname} im Monat {bm:02d}/{akt_jahr}.")

                if monate_count > 0:
                    jsz_basis_brutto = summe_brutto / monate_count
                    
            letztes_berechnetes_jsz_jahr = akt_jahr

        month_start = date(akt_jahr, akt_monat, 1)
        month_end = date(akt_jahr, akt_monat, monthrange(akt_jahr, akt_monat)[1])

        sys_params = get_sys_params(session, month_end)
        bbg_kv_pv = sys_params['bbg_kv_pv']
        bbg_rv_av = sys_params['bbg_rv_av']
        ag_rv_satz = sys_params['ag_rv']
        ag_av_satz = sys_params['ag_av']
        ag_kv_base = sys_params['ag_kv_base']
        ag_pv_satz = sys_params['ag_pv']
        vbl_satz = sys_params['vbl_satz']
        u2_satz = sys_params['u2_satz']
        luk_satz = sys_params['luk_satz']

        eff_start = max(month_start, ma.am_ifpt_seit) if ma.am_ifpt_seit else month_start
        eff_end = min(month_end, ma.geplanter_abgang) if ma.geplanter_abgang else month_end

        active_factor = 0.0
        if not (eff_start > month_end or eff_end < month_start):
            active_factor = ((eff_end - eff_start).days + 1) / monthrange(akt_jahr, akt_monat)[1]

        az_pct = 0.0
        kv_zusatz_pct = 1.7 
        if active_factor > 0:
            for az in ma.arbeitszeiten:
                if az.gueltig_ab <= month_end and (not az.gueltig_bis or az.gueltig_bis >= month_end):
                    az_pct = az.anteil_pct
                    break
            
            for kvz in ma.kv_zusatz_verlauf:
                if kvz.gueltig_ab <= month_end and (not kvz.gueltig_bis or kvz.gueltig_bis >= month_end):
                    kv_zusatz_pct = kvz.beitrag_pct
                    break

        ag_kv_zusatz_satz = (kv_zusatz_pct / 100.0) / 2.0

        eg, stufe = None, None
        if active_factor > 0 and az_pct > 0:
            for g in ma.gehaltsverlauf:
                if g.gueltig_ab <= month_end and (not g.gueltig_bis or g.gueltig_bis >= month_end):
                    eg = str(g.entgeltgruppe)
                    stufe = g.stufe
                    break

        brutto_voll = 0.0
        jsz_pct = 0.0

        if eg and stufe:
            tarif = session.query(TarifTabelle).filter(
                TarifTabelle.entgeltgruppe == eg,
                TarifTabelle.stufe == stufe,
                TarifTabelle.gueltig_ab <= month_end
            ).order_by(TarifTabelle.gueltig_ab.desc()).first()

            if tarif:
                if tarif.jsz_prozent is None:
                    raise ValueError(f"JSZ-Prozentsatz fehlt in Tariftabelle für {eg} Stufe {stufe}.")
                brutto_voll = tarif.betrag_euro
                jsz_pct = tarif.jsz_prozent
            else:
                raise ValueError(f"Keine Tariftabelle für E{eg} Stufe {stufe} am {month_end.strftime('%d.%m.%Y')} im System gefunden.")

        eff_az_pct = az_pct * active_factor

        # Harte Fehlerprüfung bei Lücken in der Laufbahn!
        if active_factor > 0:
            if az_pct == 0.0:
                raise ValueError(f"Arbeitszeit-Anteil (Teilzeit/Vollzeit) fehlt für {ma.vorname} {ma.nachname} im Monat {akt_monat:02d}/{akt_jahr}.")
            if brutto_voll == 0.0:
                raise ValueError(f"Gehaltsverlauf (Entgeltgruppe/Stufe) fehlt für {ma.vorname} {ma.nachname} im Monat {akt_monat:02d}/{akt_jahr}.")

        if eff_az_pct == 0.0 or brutto_voll == 0.0:
            alle_eintraege.append({
                "monat": f"{akt_monat:02d}/{akt_jahr}", "entgeltgruppe": "-",
                "brutto_gesamt": 0.0, "davon_jsz": 0.0, "obligo_jsz": 0.0,
                "vl": 0.0, "versorgungszuschlag": 0.0,
                "ag_kv": 0.0, "ag_zkv": 0.0, "ag_pv": 0.0, "ag_rv": 0.0, "ag_av": 0.0, "ag_u2": 0.0,
                "ag_luk": 0.0, 
                "gesamtkosten_ist": 0.0,             
                "gesamtkosten_inkl_rueck": 0.0       
            })
        else:
            grundgehalt_eff = brutto_voll * eff_az_pct
            vl_anteil = (ma.vl_betrag_euro or 0.0) * eff_az_pct

            jsz_auszahlung = 0.0
            if akt_monat == 11 and anspruch_auf_jsz:
                basis = jsz_basis_brutto if jsz_basis_brutto > 0 else (brutto_voll * eff_az_pct)
                pct = jsz_basis_pct if jsz_basis_pct > 0 else jsz_pct
                jsz_auszahlung = basis * pct * (aktive_monate_im_jahr / 12.0)

            brutto_anzeige = grundgehalt_eff + jsz_auszahlung
            brutto_fuer_sv = grundgehalt_eff + vl_anteil + jsz_auszahlung

            eff_bbg_kv = bbg_kv_pv * active_factor
            eff_bbg_rv = bbg_rv_av * active_factor
            akkumuliert_bbg_kv += eff_bbg_kv
            akkumuliert_bbg_rv += eff_bbg_rv

            sv_brutto_laufend_kv = min(grundgehalt_eff + vl_anteil, eff_bbg_kv)
            sv_brutto_laufend_rv = min(grundgehalt_eff + vl_anteil, eff_bbg_rv)
            
            akkumuliert_sv_brutto_kv += sv_brutto_laufend_kv
            akkumuliert_sv_brutto_rv += sv_brutto_laufend_rv

            jsz_sv_kv = 0.0
            jsz_sv_rv = 0.0
            if jsz_auszahlung > 0:
                luft_kv = max(0.0, akkumuliert_bbg_kv - akkumuliert_sv_brutto_kv)
                luft_rv = max(0.0, akkumuliert_bbg_rv - akkumuliert_sv_brutto_rv)
                jsz_sv_kv = min(jsz_auszahlung, luft_kv)
                jsz_sv_rv = min(jsz_auszahlung, luft_rv)
                
                akkumuliert_sv_brutto_kv += jsz_sv_kv
                akkumuliert_sv_brutto_rv += jsz_sv_rv

            sv_brutto_kv = sv_brutto_laufend_kv + jsz_sv_kv
            sv_brutto_rv = sv_brutto_laufend_rv + jsz_sv_rv

            ag_kv_euro = sv_brutto_kv * ag_kv_base
            ag_zkv_euro = sv_brutto_kv * ag_kv_zusatz_satz
            ag_pv_euro = sv_brutto_kv * ag_pv_satz
            ag_rv_euro = sv_brutto_rv * ag_rv_satz
            ag_av_euro = sv_brutto_rv * ag_av_satz
            
            vbl_euro = brutto_fuer_sv * vbl_satz
            u2_euro = brutto_fuer_sv * u2_satz
            luk_monats_wert = brutto_fuer_sv * luk_satz
            akkumuliert_luk += luk_monats_wert
            
            is_luk_faellig = False
            if akt_monat == 12: is_luk_faellig = True
            if ma.geplanter_abgang and ma.geplanter_abgang.year == akt_jahr and ma.geplanter_abgang.month == akt_monat: is_luk_faellig = True
                
            if is_luk_faellig:
                luk_euro = akkumuliert_luk
                luk_obligo = -(akkumuliert_luk - luk_monats_wert) 
                akkumuliert_luk = 0.0
            else:
                luk_euro = 0.0 
                luk_obligo = luk_monats_wert 

            obligo_jsz = 0.0
            if akt_monat <= 10 and anspruch_auf_jsz:
                basis = jsz_basis_brutto if jsz_basis_brutto > 0 else (brutto_voll * eff_az_pct)
                pct = jsz_basis_pct if jsz_basis_pct > 0 else jsz_pct
                jsz_estimate = basis * pct * (aktive_monate_im_jahr / 12.0)
                sv_faktor = ag_kv_base + ag_kv_zusatz_satz + ag_pv_satz + ag_rv_satz + ag_av_satz + vbl_satz + u2_satz + luk_satz
                obligo_jsz = (jsz_estimate * (1.0 + sv_faktor)) / 10.0
                akkumuliert_obligo_jsz += obligo_jsz
            elif akt_monat == 11 and anspruch_auf_jsz:
                obligo_jsz = -akkumuliert_obligo_jsz
                akkumuliert_obligo_jsz = 0.0

            obligo_gesamt = obligo_jsz + luk_obligo

            gesamtkosten_ist = brutto_anzeige + vl_anteil + ag_kv_euro + ag_zkv_euro + ag_pv_euro + ag_rv_euro + ag_av_euro + vbl_euro + u2_euro + luk_euro
            gesamtkosten_inkl_rueck = gesamtkosten_ist + obligo_gesamt

            alle_eintraege.append({
                "monat": f"{akt_monat:02d}/{akt_jahr}",
                "entgeltgruppe": f"E{eg}.{stufe}",
                "brutto_gesamt": brutto_anzeige,
                "davon_jsz": jsz_auszahlung,
                "obligo_jsz": obligo_gesamt, 
                "vl": vl_anteil,
                "versorgungszuschlag": vbl_euro,
                "ag_kv": ag_kv_euro,
                "ag_zkv": ag_zkv_euro,
                "ag_pv": ag_pv_euro,
                "ag_rv": ag_rv_euro,
                "ag_av": ag_av_euro,
                "ag_u2": u2_euro,
                "ag_luk": luk_euro,
                "gesamtkosten_ist": gesamtkosten_ist,
                "gesamtkosten_inkl_rueck": gesamtkosten_inkl_rueck
            })

        akt_monat += 1
        if akt_monat > 12:
            akt_monat = 1
            akt_jahr += 1

    result = []
    for e in alle_eintraege:
        m_str, y_str = e["monat"].split("/")
        m, y = int(m_str), int(y_str)
        after_start = (y > start_jahr) or (y == start_jahr and m >= start_monat)
        before_end = (y < end_jahr) or (y == end_jahr and m <= end_monat)
        if after_start and before_end: result.append(e)

    return result