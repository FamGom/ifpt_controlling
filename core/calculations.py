import calendar
from datetime import date

from core.models import Projekt, Zuweisung, ZuweisungsTyp, AusgabePosition, AusgabenStatus, Kostenart, KontoBuchung, ProjektStatus, AusgabeKopf, InstitutsKonto, OverheadRegel
from core.journal import generiere_mitarbeiter_lohnjournal

def generiere_instituts_controlling(session):
    """
    Erzeugt die Makro-Ansicht (Top-Down) für die Institutsleitung.
    Aggregiert alle Kontostände, laufenden Projekte und den globalen Forecast.
    """
    # 1. Globale Liquidität (Rücklagen)
    konten = session.query(InstitutsKonto).all()
    summe_guthaben = sum(k.guthaben or 0.0 for k in konten)
    
    # 2. Laufende Projekte aggregieren
    aktive_projekte = session.query(Projekt).filter(
        Projekt.status.in_([ProjektStatus.BEWILLIGT, ProjektStatus.BEANTRAGT])
    ).all()
    
    global_budget = 0.0
    global_ist = 0.0
    global_obligo = 0.0
    global_plan = 0.0
    global_overhead_potenzial = 0.0
    
    projekt_kpis = []
    
    for p in aktive_projekte:
        # Wir nutzen die bereits perfekte Einzel-Berechnung
        report = generiere_projekt_controlling(session, p.id)
        
        global_budget += report["budget_gesamt"]
        global_ist += report["ist_kosten_cf"]
        global_obligo += report["obligo"]
        global_plan += report["plan_kosten"]
        global_overhead_potenzial += report.get("erwirtschafteter_overhead", 0.0)
        
        projekt_kpis.append({
            "name": p.projektname,
            "status": p.status.value,
            "budget": report["budget_gesamt"],
            "verfuegbar": report["verfuegbare_mittel"],
            "overhead": report.get("erwirtschafteter_overhead", 0.0)
        })
        
    global_verfuegbar = global_budget - global_ist - global_obligo - global_plan
        
    return {
        "liquiditaet_konten": summe_guthaben,
        "anzahl_aktiv": len(aktive_projekte),
        "global_budget": global_budget,
        "global_ist": global_ist,
        "global_obligo": global_obligo,
        "global_plan": global_plan,
        "global_verfuegbar": global_verfuegbar,
        "global_overhead_potenzial": global_overhead_potenzial,
        "projekte": sorted(projekt_kpis, key=lambda x: x["verfuegbar"]) # Sortiert: Kritische zuerst
    }

def generiere_projekt_controlling(session, projekt_id, stichtag=None):
    """
    Kombiniert die exakten HR-Lohnjournale mit dem Sachmittel-/Ausgaben-Journal.
    Integriert Management-by-Exception (Stichtag) und trennt direkte Kosten
    strikt vom erwirtschafteten Overhead des Instituts.
    """
    if stichtag is None:
        stichtag = date.today()

    projekt = session.query(Projekt).filter_by(id=projekt_id).first()
    if not projekt:
        raise ValueError("Projekt nicht gefunden")

    if not projekt.projektbeginn or not projekt.projektende:
        raise ValueError("Dem Projekt fehlen Start- oder Enddatum.")

    # 1. Budgets & Parameter (REINE DIREKTKOSTEN!)
    budget_gesamt = (
        (projekt.personalbudget_e1_e12 or 0.0) + 
        (projekt.personalbudget_e13_e15 or 0.0) + 
        (projekt.personalbudget_besch_entgelt or 0.0) + 
        (projekt.sachmittelbudget or 0.0)
    )
    
    # Exakte Trennung nach Instituts-Anteil für das Overhead-Sparbuch
    institut_pct = 0.0
    if getattr(projekt, "overhead_regel", None):
        institut_pct = projekt.overhead_regel.institut_pct / 100.0

    start_y, start_m = projekt.projektbeginn.year, projekt.projektbeginn.month
    end_y, end_m = projekt.projektende.year, projekt.projektende.month
    stichtag_monat = date(stichtag.year, stichtag.month, 1)

    # 2. Container initialisieren
    monate_dict = {}
    
    def init_month(y, m):
        m_str = f"{m:02d}/{y}"
        if m_str not in monate_dict:
            monate_dict[m_str] = {
                "monat": m_str,
                "ist": {"e13_15": (0.0, 0.0), "e1_12": (0.0, 0.0), "hiwi": (0.0, 0.0), "sachmittel": (0.0, 0.0)},
                "obligo": {"e13_15": (0.0, 0.0), "e1_12": (0.0, 0.0), "hiwi": (0.0, 0.0), "sachmittel": (0.0, 0.0)},
                "plan": {"e13_15": (0.0, 0.0), "e1_12": (0.0, 0.0), "hiwi": (0.0, 0.0), "sachmittel": (0.0, 0.0)},
                "sort_key": y * 12 + m
            }
        return m_str

    # Alle Projekt-Monate vorab anlegen, um Lücken in den Graphen zu vermeiden
    start_abs = start_y * 12 + start_m
    end_abs = end_y * 12 + end_m
    for sm in range(start_abs, end_abs + 1):
        y = sm // 12
        m = sm % 12
        if m == 0: y -= 1; m = 12
        init_month(y, m)

    def add_to_details(m_str, typ, topf, cf_wert, ctrl_wert):
        alt_cf, alt_ctrl = monate_dict[m_str][typ][topf]
        monate_dict[m_str][typ][topf] = (alt_cf + cf_wert, alt_ctrl + ctrl_wert)

    # ==========================================
    # 3. PERSONAL-KOSTEN (HR Matrix)
    # ==========================================
    zuweisungen = session.query(Zuweisung).filter_by(projekt_id=projekt_id).all()
    ma_ids = set([z.mitarbeiter_id for z in zuweisungen if z.mitarbeiter_id])
    
    ma_journale = {}
    for ma_id in ma_ids:
        try:
            journal = generiere_mitarbeiter_lohnjournal(session, ma_id, start_y, start_m, end_y, end_m)
            ma_journale[ma_id] = {e["monat"]: e for e in journal}
        except ValueError:
            continue

    for sm in range(start_abs, end_abs + 1):
        y = sm // 12
        m = sm % 12
        if m == 0: y -= 1; m = 12
        
        loop_date = date(y, m, 1)
        loop_end = date(y, m, calendar.monthrange(y, m)[1])
        m_str = f"{m:02d}/{y}"
        
        for ma_id in ma_ids:
            aktive_z = [z for z in zuweisungen if z.mitarbeiter_id == ma_id and z.start_datum <= loop_end and (not z.end_datum or z.end_datum >= loop_date)]
            if not aktive_z: continue

            z_ist = next((z for z in aktive_z if z.typ == ZuweisungsTyp.IST), None)
            z_vertrag = next((z for z in aktive_z if z.typ == ZuweisungsTyp.VERTRAG), None)
            z_plan = next((z for z in aktive_z if z.typ == ZuweisungsTyp.PLANUNG), None)

            anteil, z_typ = 0.0, None
            if z_ist: anteil, z_typ = z_ist.anteil_pct, ZuweisungsTyp.IST
            elif z_vertrag: anteil, z_typ = z_vertrag.anteil_pct, ZuweisungsTyp.VERTRAG
            elif z_plan: anteil, z_typ = z_plan.anteil_pct, ZuweisungsTyp.PLANUNG

            if anteil > 0:
                eintrag = ma_journale.get(ma_id, {}).get(m_str, {})
                # Reine Kosten (OHNE Overhead-Multiplikator)
                kosten_ist = eintrag.get("gesamtkosten_ist", 0.0) * anteil
                kosten_rueck = eintrag.get("gesamtkosten_inkl_rueck", 0.0) * anteil
                
                eg_str = eintrag.get("entgeltgruppe", "")
                topf = "e1_12"
                if "SHK" in eg_str or "WHK" in eg_str or "Student" in eg_str: topf = "hiwi"
                elif any(x in eg_str for x in ["E13", "E14", "E15", "13Ü", "15Ü"]): topf = "e13_15"

                # Management by Exception
                ziel_typ = "ist" if loop_date < stichtag_monat else ("ist" if z_typ == ZuweisungsTyp.IST else ("obligo" if z_typ == ZuweisungsTyp.VERTRAG else "plan"))
                add_to_details(m_str, ziel_typ, topf, kosten_ist, kosten_rueck)

    # ==========================================
    # 4. SACHMITTEL & REISEKOSTEN (Journal)
    # ==========================================
    ausgaben = session.query(AusgabePosition).filter_by(projekt_id=projekt_id).all()
    for pos in ausgaben:
        kopf = pos.kopf
        
        datum = kopf.bestelldatum
        if kopf.status == AusgabenStatus.BEZAHLT and kopf.rechnungsdatum:
            datum = kopf.rechnungsdatum
        if not datum: 
            datum = stichtag
            
        m_str = init_month(datum.year, datum.month)
        
        topf = "sachmittel"
        if pos.kostenart == Kostenart.E12_E15: topf = "e13_15"
        elif pos.kostenart == Kostenart.E1_E11: topf = "e1_12"
        elif pos.kostenart in [Kostenart.LOHNEMPFAENGER, Kostenart.BESCHAEFTIGUNGSENTGELTE]: topf = "hiwi"
        
        # Reine Kosten (OHNE Overhead-Multiplikator)
        wert = pos.betrag_euro
        
        if kopf.status == AusgabenStatus.PLAN:
            add_to_details(m_str, "plan", topf, wert, wert)
        elif kopf.status == AusgabenStatus.BESTELLT:
            add_to_details(m_str, "obligo", topf, wert, wert)
        elif kopf.status == AusgabenStatus.BEZAHLT:
            add_to_details(m_str, "ist", topf, wert, wert)

    # ==========================================
    # 5. AGGREGATION FÜR DASHBOARDS & SPARBUCH
    # ==========================================
    monats_verlauf = []
    summe_ist_cf = summe_ist_ctrl = summe_obligo = summe_plan = 0.0
    
    # Sicherstellen, dass das Sachmittel-Ausgabenjournal in die Summen fließt
    alle_toepfe = ["e13_15", "e1_12", "hiwi", "sachmittel"]
    
    sorted_months = sorted(monate_dict.values(), key=lambda d: d["sort_key"])
    for d in sorted_months:
        m_ist_cf = sum(d["ist"][t][0] for t in alle_toepfe)
        m_ist_ctrl = sum(d["ist"][t][1] for t in alle_toepfe)
        
        m_obligo_cf = sum(d["obligo"][t][0] for t in alle_toepfe)
        m_obligo_ctrl = sum(d["obligo"][t][1] for t in alle_toepfe)
        
        m_plan_cf = sum(d["plan"][t][0] for t in alle_toepfe)
        m_plan_ctrl = sum(d["plan"][t][1] for t in alle_toepfe)
        
        summe_ist_cf += m_ist_cf
        summe_ist_ctrl += m_ist_ctrl
        summe_obligo += m_obligo_ctrl
        summe_plan += m_plan_ctrl
            
        monats_verlauf.append({
            "monat": d["monat"],
            "ist_kosten_cf": m_ist_cf,
            "ist_kosten_ctrl": m_ist_ctrl,
            "obligo": m_obligo_ctrl,
            "plan_kosten": m_plan_ctrl,
            "details": {
                "ist": d["ist"],
                "obligo": d["obligo"],
                "plan": d["plan"]
            }
        })

    verfuegbar = budget_gesamt - summe_ist_ctrl - summe_obligo
    
    # Das echte Instituts-Sparbuch: Wird nur aus bezahlten Ist-Kosten (Cash-Flow) gebildet
    erwirtschafteter_overhead_institut = summe_ist_cf * institut_pct

    return {
        "projekt_id": projekt_id,
        "projekt": projekt.projektname,
        "projektname": projekt.projektname,
        "budget_gesamt": budget_gesamt,
        "ist_kosten_cf": summe_ist_cf,
        "ist_kosten_ctrl": summe_ist_ctrl,
        "obligo": summe_obligo,
        "plan_kosten": summe_plan,
        "verfuegbare_mittel": verfuegbar,
        "erwirtschafteter_overhead": erwirtschafteter_overhead_institut,
        "monats_verlauf": monats_verlauf
    }

def schliesse_projekt_ab(session, projekt_id):
    """
    Führt den kaufmännischen Projektabschluss durch:
    1. Löscht offene Obligos/Pläne.
    2. Bucht Overhead und erlaubte Restmittel auf das Institutskonto.
    3. Nullt das Projektbudget auf exakt die Ist-Kosten aus (PT-Rückforderung).
    """
    projekt = session.query(Projekt).filter_by(id=projekt_id).first()
    if not projekt or projekt.status == ProjektStatus.ABGESCHLOSSEN:
        return

    # 1. Offene Bestellungen/Pläne (Obligos) hart löschen, da Projekt endet
    offene_positionen = session.query(AusgabePosition).join(AusgabeKopf).filter(
        AusgabePosition.projekt_id == projekt_id,
        AusgabeKopf.status != AusgabenStatus.BEZAHLT
    ).all()
    for pos in offene_positionen:
        session.delete(pos)
    session.flush()

    # 2. Finalen Kassensturz berechnen (NUR Ist-Kosten verbleiben)
    report = generiere_projekt_controlling(session, projekt_id)
    
    # 3. Geld auf Institutskonto transferieren & Beleg schreiben
    if projekt.ziel_konto:
        overhead = report.get("erwirtschafteter_overhead", 0.0)
        restmittel_pct = getattr(projekt, "restmittel_institut_pct", 0.0) / 100.0
        erlaubte_restmittel = report.get("verfuegbare_mittel", 0.0) * restmittel_pct
        
        gesamt_transfer = overhead + erlaubte_restmittel
        
        if gesamt_transfer > 0:
            buchung = KontoBuchung(
                konto_id=projekt.ziel_konto.id,
                datum=date.today(),
                beschreibung=f"Projektabschluss: {projekt.projektname} (Overhead & Restmittel)",
                betrag=gesamt_transfer
            )
            session.add(buchung)
            projekt.ziel_konto.guthaben = (projekt.ziel_konto.guthaben or 0.0) + gesamt_transfer

    # 4. Projektbudget bilanzneutral ausnullen (Reste an PT zurückgeben)
    ist_summe = report.get("ist_kosten_cf", 0.0)
    b_personal = (projekt.personalbudget_e1_e12 or 0) + (projekt.personalbudget_e13_e15 or 0) + (projekt.personalbudget_besch_entgelt or 0)
    b_sach = (projekt.sachmittelbudget or 0)
    
    # Wir reduzieren das Sachmittelbudget so, dass Budget = Ist-Kosten (Verfügbar = 0)
    # Das markiert den kaufmännischen Abschluss
    differenz = (b_personal + b_sach) - ist_summe
    projekt.sachmittelbudget = b_sach - differenz
    
    projekt.status = ProjektStatus.BEENDET


def generiere_instituts_controlling(session):
    from datetime import date
    from core.models import InstitutsKonto, Projekt, ProjektStatus, Mitarbeiter
    from core.journal import generiere_mitarbeiter_lohnjournal
    
    heute = date.today()
    
    # 1. Verfügbare Reserve (Sparbücher Personal)
    konten = session.query(InstitutsKonto).all()
    reserve_personal = sum(k.guthaben_personal or 0.0 for k in konten)
    
    aktive_projekte = session.query(Projekt).filter(
        Projekt.status.in_([ProjektStatus.BEWILLIGT, ProjektStatus.BEANTRAGT])
    ).all()
    
    projekt_analysen = []
    
    # 2. Projekt-Analysen für die Tabelle generieren (Alle Projekte!)
    for p in aktive_projekte:
        prob = 1.0 if p.status == ProjektStatus.BEWILLIGT else (p.bewilligungswahrscheinlichkeit_pct or 0.0) / 100.0
        report = generiere_projekt_controlling(session, p.id, stichtag=heute)
        
        ist_e13 = ist_e1 = ist_hiwi = 0.0
        for m_data in report["monats_verlauf"]:
            d_ist = m_data["details"]["ist"]
            ist_e13 += d_ist["e13_15"][1]; ist_e1 += d_ist["e1_12"][1]; ist_hiwi += d_ist["hiwi"][1]
            
        hr_budget = (p.personalbudget_e13_e15 or 0) + (p.personalbudget_e1_e12 or 0) + (p.personalbudget_besch_entgelt or 0)
        hr_ist = ist_e13 + ist_e1 + ist_hiwi
        hr_remaining = hr_budget - hr_ist
        
        status_text = "🟢 Ausgeglichen"
        if hr_remaining < 0: status_text = "🔴 Akutes Defizit"
        elif hr_remaining > (hr_budget * 0.1): status_text = "🟣 Hohe Reste"
            
        projekt_analysen.append({
            "name": p.projektname, "status": p.status.value, "prob": prob,
            "hr_budget": hr_budget * prob, "hr_ist": hr_ist * prob,
            "hr_remaining": hr_remaining * prob, "status_text": status_text
        })

    # 3. Verbindlichkeiten (Mitarbeiter-Versprechen 12M)
    mitarbeiter_liste = session.query(Mitarbeiter).all()
    kosten_12m = {"e13_15": 0.0, "e1_12": 0.0, "hiwi": 0.0}
    
    for ma in mitarbeiter_liste:
        ziel_datum = getattr(ma, "austrittsdatum", None)
        if not ziel_datum: ziel_datum = date(heute.year + 6, heute.month, heute.day)
        if ziel_datum < heute: continue 
        
        calc_end_y = min(heute.year + 1, ziel_datum.year)
        calc_end_m = heute.month if calc_end_y == heute.year + 1 else ziel_datum.month
        
        try:
            journal = generiere_mitarbeiter_lohnjournal(session, ma.id, heute.year, heute.month, calc_end_y, calc_end_m)
            for eintrag in journal:
                eg_str = eintrag.get("entgeltgruppe", "")
                k = eintrag.get("gesamtkosten_inkl_rueck", 0.0)
                if "SHK" in eg_str or "WHK" in eg_str or "Student" in eg_str: kosten_12m["hiwi"] += k
                elif any(x in eg_str for x in ["E13", "E14", "E15", "13Ü"]): kosten_12m["e13_15"] += k
                else: kosten_12m["e1_12"] += k
        except Exception: pass

    # 4. Szenarien-Rechner (Garantiert vs. Planung)
    def berechne_szenario(include_beantragt=False):
        b_e13 = b_e1 = b_hiwi = 0.0
        
        for p in aktive_projekte:
            if p.status == ProjektStatus.BEANTRAGT and not include_beantragt: continue
            prob = 1.0 if p.status == ProjektStatus.BEWILLIGT else (p.bewilligungswahrscheinlichkeit_pct or 0.0) / 100.0
            
            report = generiere_projekt_controlling(session, p.id, stichtag=heute)
            ist_e13 = ist_e1 = ist_hiwi = 0.0
            for m_data in report["monats_verlauf"]:
                d_ist = m_data["details"]["ist"]
                ist_e13 += d_ist["e13_15"][1]; ist_e1 += d_ist["e1_12"][1]; ist_hiwi += d_ist["hiwi"][1]
                
            b_e13 += ((p.personalbudget_e13_e15 or 0.0) - ist_e13) * prob
            b_e1 += ((p.personalbudget_e1_e12 or 0.0) - ist_e1) * prob
            b_hiwi += ((p.personalbudget_besch_entgelt or 0.0) - ist_hiwi) * prob

        total_budget = b_e13 + b_e1 + b_hiwi + reserve_personal
        total_kosten = kosten_12m["e13_15"] + kosten_12m["e1_12"] + kosten_12m["hiwi"]
        
        # Ein negativer Wert bedeutet hier: Überschuss!
        global_diff = total_kosten - total_budget 

        # Lücke 1: Strikte Bindung
        def_e13 = max(0.0, kosten_12m["e13_15"] - b_e13)
        def_e1 = max(0.0, kosten_12m["e1_12"] - b_e1)
        def_hiwi = max(0.0, kosten_12m["hiwi"] - b_hiwi)
        gap_strict = (def_e13 + def_e1 + def_hiwi) - reserve_personal
        if gap_strict <= 0: gap_strict = global_diff # Überschuss ausweisen

        # Lücke 2: 20% Geduldete Überziehung
        uncov_e13 = max(0.0, kosten_12m["e13_15"] - (b_e13 * 1.2))
        uncov_e1 = max(0.0, kosten_12m["e1_12"] - (b_e1 * 1.2))
        uncov_hiwi = max(0.0, kosten_12m["hiwi"] - (b_hiwi * 1.2))
        gap_flex = max(global_diff, (uncov_e13 + uncov_e1 + uncov_hiwi) - reserve_personal)
        if gap_flex <= 0: gap_flex = global_diff

        # Runway Berechnung
        monthly_burn = total_kosten / 12.0
        if monthly_burn == 0:
            rw_strict = rw_flex = 999.0
        else:
            global_rw = total_budget / monthly_burn
            burn_e13 = kosten_12m["e13_15"] / 12.0
            burn_e1 = kosten_12m["e1_12"] / 12.0
            burn_hiwi = kosten_12m["hiwi"] / 12.0

            rw_e13 = (b_e13 / burn_e13) if burn_e13 > 0 else 999.0
            rw_e1 = (b_e1 / burn_e1) if burn_e1 > 0 else 999.0
            rw_hiwi = (b_hiwi / burn_hiwi) if burn_hiwi > 0 else 999.0
            
            rw_strict = min([rw_e13, rw_e1, rw_hiwi])
            # Reserve auf den zuerst reißenden Topf schlagen
            fb_strict = burn_e13 if rw_strict == rw_e13 else (burn_e1 if rw_strict == rw_e1 else burn_hiwi)
            if fb_strict > 0: rw_strict += reserve_personal / fb_strict
            rw_strict = min(rw_strict, global_rw)

            # Flex-Runway
            rw_e13_f = ((b_e13 * 1.2) / burn_e13) if burn_e13 > 0 else 999.0
            rw_e1_f = ((b_e1 * 1.2) / burn_e1) if burn_e1 > 0 else 999.0
            rw_hiwi_f = ((b_hiwi * 1.2) / burn_hiwi) if burn_hiwi > 0 else 999.0

            rw_flex = min([rw_e13_f, rw_e1_f, rw_hiwi_f])
            fb_flex = burn_e13 if rw_flex == rw_e13_f else (burn_e1 if rw_flex == rw_e1_f else burn_hiwi)
            if fb_flex > 0: rw_flex += reserve_personal / fb_flex
            rw_flex = min(rw_flex, global_rw)

        return gap_strict, gap_flex, rw_strict, rw_flex

    gap_base_strict, gap_base_flex, rw_base_strict, rw_base_flex = berechne_szenario(include_beantragt=False)
    gap_opt_strict, gap_opt_flex, rw_opt_strict, rw_opt_flex = berechne_szenario(include_beantragt=True)
    
    return {
        "runway_base_strict": rw_base_strict, "runway_base_flex": rw_base_flex,
        "runway_opt_strict": rw_opt_strict, "runway_opt_flex": rw_opt_flex,
        "gap_base_strict": gap_base_strict, "gap_base_flex": gap_base_flex,
        "gap_opt_strict": gap_opt_strict, "gap_opt_flex": gap_opt_flex,
        "analysen": sorted(projekt_analysen, key=lambda x: x["hr_remaining"])
    }