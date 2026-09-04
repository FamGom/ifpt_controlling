from datetime import date
import calendar

from core.models import Projekt, Zuweisung, ZuweisungsTyp
from core.journal import generiere_mitarbeiter_lohnjournal

def generiere_projekt_controlling(session, projekt_id, stichtag):
    """
    Berechnet die Finanzen eines Projekts auf Basis der exakten Lohnjournale
    der zugewiesenen Mitarbeiter. Setzt 'Management by Exception' um.
    """
    projekt = session.query(Projekt).filter_by(id=projekt_id).first()
    if not projekt:
        return None

    # 1. Projekt-Gesamtbudget ermitteln
    budget_gesamt = (projekt.personalbudget_e1_e12 + 
                     projekt.personalbudget_e13_e15 + 
                     projekt.personalbudget_besch_entgelt + 
                     projekt.sachmittelbudget)

    # Overhead-Faktor (z.B. 20% Overhead -> 1.20)
    overhead_faktor = 1.0 + (projekt.overhead_pct / 100.0)

    # Laufzeit des Projekts
    start_y = projekt.projektbeginn.year
    start_m = projekt.projektbeginn.month
    end_y = projekt.projektende.year
    end_m = projekt.projektende.month

    # 2. Alle beteiligten Mitarbeiter identifizieren
    zuweisungen = session.query(Zuweisung).filter_by(projekt_id=projekt_id).all()
    ma_ids = set([z.mitarbeiter_id for z in zuweisungen if z.mitarbeiter_id])

    # 3. Lohnjournale cachen (Performance!)
    ma_journale = {}
    for ma_id in ma_ids:
        journal = generiere_mitarbeiter_lohnjournal(session, ma_id, start_y, start_m, end_y, end_m)
        # NEU: Wir speichern das komplette Monats-Paket, nicht nur eine Zahl
        ma_journale[ma_id] = {e["monat"]: e for e in journal}

    ist_gesamt = 0.0
    obligo_gesamt = 0.0
    plan_gesamt = 0.0
    monats_verlauf = []

    stichtag_monat = date(stichtag.year, stichtag.month, 1)

    y, m = start_y, start_m
    while y < end_y or (y == end_y and m <= end_m):
        loop_date = date(y, m, 1)
        loop_end = date(y, m, calendar.monthrange(y, m)[1])
        monat_str = f"{m:02d}/{y}"

        m_ist, m_obligo, m_plan = 0.0, 0.0, 0.0

        for ma_id in ma_ids:
            aktive_z = [z for z in zuweisungen if z.mitarbeiter_id == ma_id and z.start_datum <= loop_end and z.end_datum >= loop_date]
            if not aktive_z: continue

            z_ist = next((z for z in aktive_z if z.typ == ZuweisungsTyp.IST), None)
            z_vertrag = next((z for z in aktive_z if z.typ == ZuweisungsTyp.VERTRAG), None)
            z_plan = next((z for z in aktive_z if z.typ == ZuweisungsTyp.PLANUNG), None)

            anteil, typ = 0.0, None
            if z_ist: anteil, typ = z_ist.anteil_pct, ZuweisungsTyp.IST
            elif z_vertrag: anteil, typ = z_vertrag.anteil_pct, ZuweisungsTyp.VERTRAG
            elif z_plan: anteil, typ = z_plan.anteil_pct, ZuweisungsTyp.PLANUNG

            if anteil > 0:
                # NEU: Wir holen das volle Paket und greifen auf die geglätteten Controlling-Kosten zu
                eintrag = ma_journale[ma_id].get(monat_str, {})
                kosten_voll = eintrag.get("gesamtkosten_inkl_rueck", 0.0) 
                
                kosten_anteilig = kosten_voll * anteil * overhead_faktor

                if loop_date < stichtag_monat:
                    m_ist += kosten_anteilig
                else:
                    if typ == ZuweisungsTyp.IST: m_ist += kosten_anteilig
                    elif typ == ZuweisungsTyp.VERTRAG: m_obligo += kosten_anteilig
                    elif typ == ZuweisungsTyp.PLANUNG: m_plan += kosten_anteilig

        ist_gesamt += m_ist
        obligo_gesamt += m_obligo
        plan_gesamt += m_plan

        monats_verlauf.append({
            "monat": monat_str,
            "ist_kosten": m_ist,
            "obligo": m_obligo,
            "plan_kosten": m_plan
        })

        m += 1
        if m > 12:
            m = 1
            y += 1

    # 5. Restmittel berechnen
    verfuegbar = budget_gesamt - ist_gesamt - obligo_gesamt - plan_gesamt
    verfuegbar_pct = (verfuegbar / budget_gesamt * 100.0) if budget_gesamt > 0 else 0.0

    return {
        "projekt": projekt.projektname,
        "budget_gesamt": budget_gesamt,
        "ist_buchungen_gesamt": ist_gesamt,
        "obligo_gesamt": obligo_gesamt,
        "plan_ausgaben_gesamt": plan_gesamt,
        "verfuegbare_mittel": verfuegbar,
        "verfuegbar_pct": round(verfuegbar_pct, 1),
        "monats_verlauf": monats_verlauf
    }