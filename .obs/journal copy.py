from datetime import date
from calendar import monthrange
from core.models import Mitarbeiter, TarifTabelle

def generiere_mitarbeiter_lohnjournal(session, ma_id, start_jahr, start_monat, end_jahr, end_monat):
    """
    Berechnet das Lohnjournal auf den Tag genau, unter Berücksichtigung 
    von Teilzeit (Arbeitszeitverlauf), TV-L Sprüngen und Rumpfmonaten.
    """
    ma = session.query(Mitarbeiter).filter_by(id=ma_id).first()
    if not ma: return []

    # 1. Parameter für Sozialabgaben (AG-Anteile)
    ag_rv_satz = 0.093   # 9,3 % Rentenversicherung
    ag_av_satz = 0.013   # 1,3 % Arbeitslosenversicherung
    ag_pv_satz = 0.017   # 1,7 % Pflegeversicherung (AG-Anteil ist immer fix)
    ag_kv_base = 0.073   # 7,3 % Krankenversicherung Grundbeitrag
    vbl_satz = 0.0645    # 6,45 % VBL (West)
    u2_satz = 0.0039     # 0,39 % U2-Umlage

    # Individueller Zusatzbeitrag wird paritätisch geteilt
    kv_zusatz = (ma.kv_zusatzbeitrag_pct or 1.7) / 100.0
    ag_kv_zusatz_satz = kv_zusatz / 2.0

    # Beitragsbemessungsgrenzen (Beispiel 2024 West)
    bbg_west_rv_av = 7550.0
    bbg_west_kv_pv = 5175.0

    # TV-L Fallback (Greift, falls in der Tarif-Datenbank keine Werte hinterlegt wurden)
    fallback_tarife = {
        "13_1": 4628.76, "13_2": 4965.86, "13_3": 5225.68, "13_4": 5716.48, "13_5": 6378.11, "13_6": 6635.40,
        "14_1": 5003.84, "14_2": 5370.21, "14_3": 5707.13, "14_4": 6164.71, "14_5": 6843.83, "14_6": 7069.91
    }

    eintraege = []
    jahr = start_jahr
    monat = start_monat

    while jahr < end_jahr or (jahr == end_jahr and monat <= end_monat):
        month_start = date(jahr, monat, 1)
        month_end = date(jahr, monat, monthrange(jahr, monat)[1])

        # --- A. RUMPFMONATE (Taggenaue Beschäftigung) ---
        eff_start = max(month_start, ma.am_ifpt_seit) if ma.am_ifpt_seit else month_start
        eff_end = min(month_end, ma.geplanter_abgang) if ma.geplanter_abgang else month_end

        if eff_start > month_end or eff_end < month_start:
            # Mitarbeiter ist in diesem Monat überhaupt nicht am Institut
            active_factor = 0.0
        else:
            # Berechnet, wie viel % des Monats er angestellt ist
            active_factor = ((eff_end - eff_start).days + 1) / monthrange(jahr, monat)[1]

        # --- B. TEILZEIT (Arbeitszeitverlauf) ---
        az_pct = 0.0
        if active_factor > 0:
            for az in ma.arbeitszeiten:
                if az.gueltig_ab <= month_end and (not az.gueltig_bis or az.gueltig_bis >= month_end):
                    az_pct = az.anteil_pct
                    break

        # --- C. GEHALTSVERLAUF (EG & Stufe) ---
        eg, stufe = None, None
        if active_factor > 0 and az_pct > 0:
            for g in ma.gehaltsverlauf:
                if g.gueltig_ab <= month_end and (not g.gueltig_bis or g.gueltig_bis >= month_end):
                    eg = str(g.entgeltgruppe).replace('E', '') # 'E13' zu '13' machen
                    stufe = g.stufe
                    break

        brutto_voll = 0.0
        jsz_pct = 0.4647 # Standard JSZ E13

        if eg and stufe:
            # Wir suchen zuerst in der Datenbank nach dem echten Tarif
            tarif = session.query(TarifTabelle).filter(
                TarifTabelle.entgeltgruppe.like(f"%{eg}%"),
                TarifTabelle.stufe == stufe,
                TarifTabelle.gueltig_ab <= month_end
            ).order_by(TarifTabelle.gueltig_ab.desc()).first()

            if tarif:
                brutto_voll = tarif.betrag_euro
                jsz_pct = tarif.jsz_prozent or 0.4647
            else:
                # Fallback, damit es immer funktioniert!
                key = f"{eg}_{stufe}"
                brutto_voll = fallback_tarife.get(key, 4500.0)

        # --- D. DER KOMBINIERTE FAKTOR ---
        # 75% Teilzeit * 100% Monatslänge = 0.75
        # 100% Vollzeit * 50% Monatslänge (halber Monat) = 0.50
        eff_az_pct = az_pct * active_factor

        # --- E. BERECHNUNG DER KOSTEN ---
        if eff_az_pct == 0.0 or brutto_voll == 0.0:
            # Null-Kosten (Ausgeschieden, vor Eintritt oder 0% Elternzeit)
            eintraege.append({
                "monat": f"{monat:02d}/{jahr}",
                "entgeltgruppe": "-",
                "brutto_gesamt": 0.0, "davon_jsz": 0.0, "obligo_jsz": 0.0,
                "vl": 0.0, "versorgungszuschlag": 0.0,
                "ag_kv": 0.0, "ag_zkv": 0.0, "ag_pv": 0.0, "ag_rv": 0.0, "ag_av": 0.0, "ag_u2": 0.0,
                "gesamtkosten": 0.0
            })
        else:
            # Skaliertes Laufendes Brutto
            brutto_laufend = brutto_voll * eff_az_pct
            
            # Skalierte VWL
            vl_anteil = (ma.vl_betrag_euro or 0.0) * eff_az_pct
            brutto_laufend += vl_anteil

            # JSZ Auszahlung im November
            jsz_auszahlung = 0.0
            if monat == 11:
                jsz_auszahlung = (brutto_voll * eff_az_pct) * jsz_pct

            brutto_gesamt = brutto_laufend + jsz_auszahlung

            # SV-Deckelung (Kappungsgrenzen)
            sv_brutto_kv_pv = min(brutto_gesamt, bbg_west_kv_pv)
            sv_brutto_rv_av = min(brutto_gesamt, bbg_west_rv_av)

            # Arbeitgeberanteile berechnen
            ag_kv = sv_brutto_kv_pv * ag_kv_base
            ag_zkv = sv_brutto_kv_pv * ag_kv_zusatz_satz
            ag_pv = sv_brutto_kv_pv * ag_pv_satz
            ag_rv = sv_brutto_rv_av * ag_rv_satz
            ag_av = sv_brutto_rv_av * ag_av_satz
            vbl = brutto_gesamt * vbl_satz
            u2 = brutto_gesamt * u2_satz

            # JSZ Obligo (Monatlicher Rückbau)
            obligo = 0.0
            if monat != 11:
                # 1/12 der erwarteten JSZ ansparen
                obligo_basis = ((brutto_voll * eff_az_pct) * jsz_pct) / 12.0
                sv_faktor = ag_kv_base + ag_kv_zusatz_satz + ag_pv_satz + ag_rv_satz + ag_av_satz + vbl_satz + u2_satz
                obligo = obligo_basis * (1 + sv_faktor)

            # Summe AG-Brutto
            gesamtkosten = brutto_gesamt + ag_kv + ag_zkv + ag_pv + ag_rv + ag_av + vbl + u2 + obligo

            eintraege.append({
                "monat": f"{monat:02d}/{jahr}",
                "entgeltgruppe": f"E{eg}.{stufe}",
                "brutto_gesamt": brutto_gesamt,
                "davon_jsz": jsz_auszahlung,
                "obligo_jsz": obligo,
                "vl": vl_anteil,
                "versorgungszuschlag": vbl,
                "ag_kv": ag_kv,
                "ag_zkv": ag_zkv,
                "ag_pv": ag_pv,
                "ag_rv": ag_rv,
                "ag_av": ag_av,
                "ag_u2": u2,
                "gesamtkosten": gesamtkosten
            })

        # Nächster Monat
        monat += 1
        if monat > 12:
            monat = 1
            jahr += 1

    return eintraege