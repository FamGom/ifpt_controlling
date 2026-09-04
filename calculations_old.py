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
            
    zulagen = 0.0
    for sz in ma.sonderzahlungen:
        if sz.gueltig_bis is not None:
            if sz.gueltig_ab <= betrachtungsmonat and sz.gueltig_bis >= betrachtungsmonat:
                zulagen += sz.betrag_euro
                
    return grundgehalt + zulagen, entgeltgruppe

def berechne_arbeitgeberbrutto(session, mitarbeiter_id, jahr, monat, aktueller_monat_system):
    betrachtungsmonat = date(jahr, monat, 1)
    ma = session.query(Mitarbeiter).filter_by(id=mitarbeiter_id).first()
    
    AG_ANTEIL_PCT = get_system_parameter(session, "AG_ANTEIL_PCT", betrachtungsmonat)
    BBG_KV = get_system_parameter(session, "BBG_KV", betrachtungsmonat)
    JSZ_PCT = get_system_parameter(session, "JSZ_PCT_E13", betrachtungsmonat) # Vereinfacht für E13
    
    # 1. Reguläres Gehalt
    an_brutto, eg_aktuell = get_monats_brutto(session, mitarbeiter_id, jahr, monat)
    ag_brutto_laufend = an_brutto + (min(an_brutto, BBG_KV) * AG_ANTEIL_PCT)
    
    # 2. JSZ Simulation (Stichtag 1.12.)
    ag_kosten_jsz_monatlich = 0.0
    stichtag = date(jahr, 12, 1)
    
    if ma.geplanter_abgang is None or ma.geplanter_abgang >= stichtag:
        b_jul, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 7)
        b_aug, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 8)
        b_sep, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 9)
        bemessung = (b_jul + b_aug + b_sep) / 3.0
        
        jsz_gesamt = bemessung * JSZ_PCT
        
        nov_brutto, _ = get_monats_brutto(session, mitarbeiter_id, jahr, 11)
        nov_gesamt = nov_brutto + jsz_gesamt
        nov_ag_gesamt = nov_gesamt + (min(nov_gesamt, BBG_KV) * AG_ANTEIL_PCT)
        nov_ag_ohne_jsz = nov_brutto + (min(nov_brutto, BBG_KV) * AG_ANTEIL_PCT)
        
        ag_kosten_jsz_monatlich = (nov_ag_gesamt - nov_ag_ohne_jsz) / 12.0
        
    kostenart = "IST" if betrachtungsmonat <= aktueller_monat_system else "OBLIGO"
    
    return {
        "kostenart": kostenart,
        "kosten_gesamt": ag_brutto_laufend + ag_kosten_jsz_monatlich
    }

def generiere_projekt_controlling(session, projekt_id, aktueller_monat_system):
    projekt = session.query(Projekt).filter_by(id=projekt_id).first()
    start_jahr, start_monat = projekt.projektbeginn.year, projekt.projektbeginn.month
    end_jahr, end_monat = projekt.projektende.year, projekt.projektende.month

    budget_gesamt = (projekt.personalbudget_e1_e12 + projekt.personalbudget_e13_e15 + projekt.personalbudget_besch_entgelt)
    ist_kosten = 0.0
    obligo = 0.0
    plan_kosten = 0.0
    
    # WICHTIG: Hier speichern wir den Verlauf für die Jahresscheiben (Ansicht 2)
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
                    
        # Monatswerte auf die Gesamtsummen addieren
        ist_kosten += monats_ist
        obligo += monats_obligo
        plan_kosten += monats_plan
        
        # Monatswerte in die Verlaufs-Liste anhängen
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

    # Die exakten Schlüssel, die Ansicht 1 & 2 erwarten!
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