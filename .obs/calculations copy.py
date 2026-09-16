from datetime import date
from sqlalchemy import or_
from core.models_old import Mitarbeiter, TarifTabelle, SystemParameter, Projekt, ZuweisungsTyp, Abrechnungsart

def get_system_parameter(session, schluessel, betrachtungsmonat):
    param = session.query(SystemParameter).filter(
        SystemParameter.schluessel == schluessel,
        SystemParameter.gueltig_ab <= betrachtungsmonat,
        or_(SystemParameter.gueltig_bis >= betrachtungsmonat, SystemParameter.gueltig_bis == None)
    ).first()
    return param.wert if param else 0.0

def get_monats_brutto(session, mitarbeiter_id, jahr, monat):
    betrachtungsmonat = date(jahr, monat, 1)
    ma = session.query(Mitarbeiter).filter_by(id=mitarbeiter_id).first()
    
    entgeltgruppe = "Keine"
    stufe = 0
    grundgehalt = 0.0
    jsz_faktor = 0.5634  # Fallback
    
    for gv in ma.gehaltsverlauf:
        if gv.gueltig_ab <= betrachtungsmonat and (gv.gueltig_bis is None or gv.gueltig_bis >= betrachtungsmonat):
            entgeltgruppe = gv.entgeltgruppe
            stufe = gv.stufe
            break
            
    if entgeltgruppe != "Keine":
        tarif = session.query(TarifTabelle).filter(
            TarifTabelle.entgeltgruppe == entgeltgruppe,
            TarifTabelle.stufe == stufe,
            TarifTabelle.gueltig_ab <= betrachtungsmonat,
            or_(TarifTabelle.gueltig_bis >= betrachtungsmonat, TarifTabelle.gueltig_bis == None)
        ).first()
        if tarif:
            grundgehalt = tarif.betrag_euro
            if tarif.jsz_prozent is not None:
                jsz_faktor = tarif.jsz_prozent
            
    zulagen = 0.0
    for sz in ma.sonderzahlungen:
        if sz.gueltig_bis is not None:
            if sz.gueltig_ab <= betrachtungsmonat and sz.gueltig_bis >= betrachtungsmonat:
                zulagen += sz.betrag_euro
                
    return grundgehalt + zulagen, entgeltgruppe, jsz_faktor

def berechne_arbeitgeberbrutto(session, mitarbeiter_id, jahr, monat, aktueller_monat_system):
    betrachtungsmonat = date(jahr, monat, 1)
    ma = session.query(Mitarbeiter).filter_by(id=mitarbeiter_id).first()
    
    # 1. Jahres-Beitragsbemessungsgrenzen ermitteln (Falls in DB als Monats-BBG gepflegt, * 12 nehmen)
    bbg_kv_jahr = get_system_parameter(session, "JAHRES_BBG_KV", betrachtungsmonat)
    if bbg_kv_jahr == 0.0:
        m_kv = get_system_parameter(session, "BBG_KV", betrachtungsmonat)
        bbg_kv_jahr = (m_kv if m_kv > 0.0 else 5175.0) * 12.0
        
    bbg_rv_jahr = get_system_parameter(session, "JAHRES_BBG_RV", betrachtungsmonat)
    if bbg_rv_jahr == 0.0:
        m_rv = get_system_parameter(session, "BBG_RV", betrachtungsmonat)
        bbg_rv_jahr = (m_rv if m_rv > 0.0 else 7550.0) * 12.0

    # 2. Individuelle Sätze (KV-Zusatzbeitrag & Kinderanzahl für PV)
    kv_zusatz = ma.kv_zusatzbeitrag_pct if ma.kv_zusatzbeitrag_pct else 1.7
    kv_ag_satz = 0.073 + ((kv_zusatz / 100.0) / 2.0)
    
    pv_basis_ag = 0.022
    kinder = ma.kinder_anzahl if ma.kinder_anzahl is not None else 0
    if kinder >= 2:
        abschlag = min(4, kinder - 1) * 0.0025
        pv_ag_satz = max(0.01, pv_basis_ag - abschlag)
    else:
        pv_ag_satz = pv_basis_ag
        
    rv_ag_satz = 0.093
    av_ag_satz = 0.013

    # 3. Year-to-Date (YTD) Simulation von Monat 1 bis zum aktuellen Monat
    # Hilfsfunktion zur Ermittlung des Bruttos für Monat m inkl. JSZ im November
    def get_brutto_fuer_sim_monat(m):
        b_val, _, jsz_pct = get_monats_brutto(session, mitarbeiter_id, jahr, m)
        jsz_betrag = 0.0
        if m == 11:
            stichtag = date(jahr, 12, 1)
            if ma.geplanter_abgang is None or ma.geplanter_abgang >= stichtag:
                b_jul, _, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 7)
                b_aug, _, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 8)
                b_sep, _, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 9)
                bemessung_jsz = (b_jul + b_aug + b_sep) / 3.0
                jsz_betrag = bemessung_jsz * jsz_pct
        return b_val + jsz_betrag

    ytd_brutto_aktuell = 0.0
    ytd_brutto_vorher = 0.0
    
    for m in range(1, monat + 1):
        brutto_m = get_brutto_fuer_sim_monat(m)
        ytd_brutto_aktuell += brutto_m
        if m < monat:
            ytd_brutto_vorher += brutto_m

    # 4. Jahres-BBG Deckelung auf die kumulierten Jahressummen anwenden
    ytd_kv_aktuell = min(ytd_brutto_aktuell, bbg_kv_jahr)
    ytd_kv_vorher = min(ytd_brutto_vorher, bbg_kv_jahr)
    kv_pv_bemessung_dieses_monat = ytd_kv_aktuell - ytd_kv_vorher

    ytd_rv_aktuell = min(ytd_brutto_aktuell, bbg_rv_jahr)
    ytd_rv_vorher = min(ytd_brutto_vorher, bbg_rv_jahr)
    rv_av_bemessung_dieses_monat = ytd_rv_aktuell - ytd_rv_vorher

    # 5. Tatsächliches Brutto des aktuellen Monats (für die Auszahlung/Ansicht)
    an_brutto_rein, _, _ = get_monats_brutto(session, mitarbeiter_id, jahr, monat)
    jsz_dieses_monat = 0.0
    if monat == 11:
        stichtag = date(jahr, 12, 1)
        if ma.geplanter_abgang is None or ma.geplanter_abgang >= stichtag:
            b_jul, _, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 7)
            b_aug, _, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 8)
            b_sep, _, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 9)
            bemessung_jsz = (b_jul + b_aug + b_sep) / 3.0
            _, _, jsz_pct_nov = get_monats_brutto(session, mitarbeiter_id, jahr, 11)
            jsz_dieses_monat = bemessung_jsz * jsz_pct_nov

    gesamt_brutto_monat = an_brutto_rein + jsz_dieses_monat

    # 6. Arbeitgeber-Sozialabgaben für diesen Monat berechnen
    ag_kv = kv_pv_bemessung_dieses_monat * kv_ag_satz
    ag_pv = kv_pv_bemessung_dieses_monat * pv_ag_satz
    ag_rv = rv_av_bemessung_dieses_monat * rv_ag_satz
    ag_av = rv_av_bemessung_dieses_monat * av_ag_satz
    
    sozialabgaben_ag = ag_kv + ag_pv + ag_rv + ag_av
    vl = ma.vl_betrag_euro if ma.vl_betrag_euro else 0.0
    
    kosten_gesamt = gesamt_brutto_monat + sozialabgaben_ag + vl
    kostenart = "IST" if betrachtungsmonat <= aktueller_monat_system else "OBLIGO"
    
    return {
        "kostenart": kostenart,
        "kosten_gesamt": kosten_gesamt
    }

def generiere_projekt_controlling(session, projekt_id, aktueller_monat_system):
    projekt = session.query(Projekt).filter_by(id=projekt_id).first()
    start_jahr, start_monat = projekt.projektbeginn.year, projekt.projektbeginn.month
    end_jahr, end_monat = projekt.projektende.year, projekt.projektende.month

    budget_gesamt = (projekt.personalbudget_e1_e12 + projekt.personalbudget_e13_e15 + projekt.personalbudget_besch_entgelt)
    ist_kosten = 0.0
    obligo = 0.0
    plan_kosten = 0.0
    
    monats_verlauf = [] 

    akt_jahr, akt_monat = start_jahr, start_monat
    while (akt_jahr < end_jahr) or (akt_jahr == end_jahr and akt_monat <= end_monat):
        b_datum = date(akt_jahr, akt_monat, 1)
        
        monats_ist = 0.0
        monats_obligo = 0.0
        monats_plan = 0.0
        
        for z in projekt.zuweisungen:
            if z.start_datum <= b_datum <= z.end_datum:
                kosten = berechne_arbeitgeberbrutto(session, z.mitarbeiter_id, akt_jahr, akt_monat, aktueller_monat_system)
                kosten_anteilig = kosten["kosten_gesamt"] * z.anteil_pct
                
                if z.typ == ZuweisungsTyp.PLANUNG:
                    monats_plan += kosten_anteilig
                else:
                    if kosten["kostenart"] == "IST": monats_ist += kosten_anteilig
                    else: monats_obligo += kosten_anteilig
                    
        ist_kosten += monats_ist
        obligo += monats_obligo
        plan_kosten += monats_plan
        
        monats_verlauf.append({
            "monat": f"{akt_monat:02d}/{akt_jahr}",
            "ist_kosten": monats_ist,
            "obligo": monats_obligo,
            "plan_kosten": monats_plan
        })
                
        akt_monat += 1
        if akt_monat > 12:
            akt_monat = 1
            akt_jahr += 1

    verfuegbar = budget_gesamt - ist_kosten - obligo
    prozent = round((verfuegbar / budget_gesamt) * 100, 1) if budget_gesamt > 0 else 0.0

    return {
        "projekt": projekt.projektname,
        "budget_gesamt": budget_gesamt,
        "ist_buchungen_gesamt": ist_kosten,
        "obligo_gesamt": obligo,
        "plan_ausgaben_gesamt": plan_kosten,
        "verfuegbare_mittel": verfuegbar,
        "verfuegbar_pct": prozent,
        "monats_verlauf": monats_verlauf
    }