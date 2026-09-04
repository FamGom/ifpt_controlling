from datetime import date
from calendar import monthrange
from core.models import Mitarbeiter, TarifTabelle, SystemParameter

def get_sys_params(session, check_date):
    params = session.query(SystemParameter).filter(SystemParameter.gueltig_ab <= check_date).all()
    param_dict = {}
    for p in params:
        if p.schluessel not in param_dict or p.gueltig_ab > param_dict[p.schluessel]['date']:
            param_dict[p.schluessel] = {'val': p.wert, 'date': p.gueltig_ab}
    return {k: v['val'] for k, v in param_dict.items()}

def generiere_mitarbeiter_lohnjournal(session, ma_id, start_jahr, start_monat, end_jahr, end_monat):
    ma = session.query(Mitarbeiter).filter_by(id=ma_id).first()
    if not ma: return []

    fallback_tarife = {
        "15Ü_1": 6670.37, "15_1": 5504.26, "14_1": 5003.49, "13Ü_1": 4967.01,
        "13_1": 4629.74, "12_1": 4193.48, "11_1": 4064.54, "10_1": 3928.42
    }

    akt_jahr = start_jahr
    akt_monat = 1

    akkumuliert_sv_brutto_kv = 0.0
    akkumuliert_sv_brutto_rv = 0.0
    akkumuliert_bbg_kv = 0.0
    akkumuliert_bbg_rv = 0.0
    akkumuliert_obligo_jsz = 0.0
    akkumuliert_luk = 0.0

    alle_eintraege = []

    while akt_jahr < end_jahr or (akt_jahr == end_jahr and akt_monat <= end_monat):

        # --- RENTEN-DECKEL (67 JAHRE) ---
        if ma.geburtsdatum:
            alter = akt_jahr - ma.geburtsdatum.year - ((akt_monat, 1) < (ma.geburtsdatum.month, ma.geburtsdatum.day))
            if alter >= 67:
                break 

        if akt_monat == 1:
            akkumuliert_sv_brutto_kv = 0.0
            akkumuliert_sv_brutto_rv = 0.0
            akkumuliert_bbg_kv = 0.0
            akkumuliert_bbg_rv = 0.0
            akkumuliert_obligo_jsz = 0.0
            akkumuliert_luk = 0.0

        month_start = date(akt_jahr, akt_monat, 1)
        month_end = date(akt_jahr, akt_monat, monthrange(akt_jahr, akt_monat)[1])

        sys_params = get_sys_params(session, month_end)
        bbg_kv_pv = sys_params.get('bbg_kv_pv', 5175.0)
        bbg_rv_av = sys_params.get('bbg_rv_av', 7550.0)
        
        ag_rv_satz = sys_params.get('ag_rv', 0.093)
        ag_av_satz = sys_params.get('ag_av', 0.013)
        ag_kv_base = sys_params.get('ag_kv_base', 0.073)
        ag_pv_satz = sys_params.get('ag_pv', 0.017)
        vbl_satz = sys_params.get('vbl_satz', 0.0645)
        u2_satz = sys_params.get('u2_satz', 0.0039)
        luk_satz = sys_params.get('luk_satz', 0.0032)

        eff_start = max(month_start, ma.am_ifpt_seit) if ma.am_ifpt_seit else month_start
        eff_end = min(month_end, ma.geplanter_abgang) if ma.geplanter_abgang else month_end

        active_factor = 0.0
        if not (eff_start > month_end or eff_end < month_start):
            active_factor = ((eff_end - eff_start).days + 1) / monthrange(akt_jahr, akt_monat)[1]

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
        jsz_pct = 0.4647

        if eg and stufe:
            tarif = session.query(TarifTabelle).filter(
                TarifTabelle.entgeltgruppe == eg,
                TarifTabelle.stufe == stufe,
                TarifTabelle.gueltig_ab <= month_end
            ).order_by(TarifTabelle.gueltig_ab.desc()).first()

            if tarif:
                brutto_voll = tarif.betrag_euro
                jsz_pct = tarif.jsz_prozent or 0.4647
            else:
                key = f"{eg}_{stufe}"
                brutto_voll = fallback_tarife.get(key, 4500.0)

        eff_az_pct = az_pct * active_factor

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
                jsz_auszahlung = (brutto_voll * eff_az_pct) * jsz_pct * (aktive_monate_im_jahr / 12.0)

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
            if akt_monat == 12:
                is_luk_faellig = True
            if ma.geplanter_abgang and ma.geplanter_abgang.year == akt_jahr and ma.geplanter_abgang.month == akt_monat:
                is_luk_faellig = True
                
            if is_luk_faellig:
                luk_euro = akkumuliert_luk
                luk_obligo = -(akkumuliert_luk - luk_monats_wert) 
                akkumuliert_luk = 0.0
            else:
                luk_euro = 0.0 
                luk_obligo = luk_monats_wert 

            # ========================================================
            # TV-L / TVöD GLÄTTUNG (JSZ-RÜCKSTELLUNG)
            # ========================================================
            obligo_jsz = 0.0
            if akt_monat <= 10 and anspruch_auf_jsz:
                jsz_estimate = (brutto_voll * eff_az_pct) * jsz_pct * (aktive_monate_im_jahr / 12.0)
                sv_faktor = ag_kv_base + ag_kv_zusatz_satz + ag_pv_satz + ag_rv_satz + ag_av_satz + vbl_satz + u2_satz + luk_satz
                obligo_jsz = (jsz_estimate * (1.0 + sv_faktor)) / 10.0
                akkumuliert_obligo_jsz += obligo_jsz
            elif akt_monat == 11 and anspruch_auf_jsz:
                # Im November wird das Konto (Cash-Flow) extrem belastet. 
                # Das Controlling-Budget wurde durch monatliche Rückstellungen vorbereitet.
                obligo_jsz = -akkumuliert_obligo_jsz
                akkumuliert_obligo_jsz = 0.0

            obligo_gesamt = obligo_jsz + luk_obligo

            # 1. CASH-FLOW (Echter Konto-Abfluss, Peak im November inkl. LUK-Peak im Dezember)
            gesamtkosten_ist = brutto_anzeige + vl_anteil + ag_kv_euro + ag_zkv_euro + ag_pv_euro + ag_rv_euro + ag_av_euro + vbl_euro + u2_euro + luk_euro
            
            # 2. CONTROLLING (Geglättete Kosten-Ansicht inkl. JSZ- & LUK-Rückstellungen)
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