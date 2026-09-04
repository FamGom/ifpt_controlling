import calendar
from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QSpinBox, QTabWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models import Mitarbeiter, Zuweisung, ZuweisungsTyp, Projekt, ProjektStatus
from core.journal import generiere_mitarbeiter_lohnjournal
from core.calculations import generiere_projekt_controlling

class VakanzenView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("Instituts-Steuerung: Vakanzen & 6-Jahres-Bedarfe")
        title.setProperty("title", "true")
        layout.addWidget(title)
        
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("<b>Betrachtungszeitraum:</b>"))
        self.spin_start = QSpinBox(); self.spin_start.setRange(2020, 2040); self.spin_start.setValue(date.today().year)
        self.spin_end = QSpinBox(); self.spin_end.setRange(2020, 2040); self.spin_end.setValue(date.today().year + 2)
        # Live-Update bei Änderung der Jahre
        self.spin_start.valueChanged.connect(self.load_data)
        self.spin_end.valueChanged.connect(self.load_data)
        
        btn_load = QPushButton("🔄 Bedarf & Budgets berechnen")
        btn_load.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold; padding: 6px;")
        btn_load.clicked.connect(self.load_data)
        
        toolbar.addWidget(self.spin_start)
        toolbar.addWidget(QLabel("bis"))
        toolbar.addWidget(self.spin_end)
        toolbar.addWidget(btn_load)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.tab1 = QTableWidget()
        self.tab2 = QTableWidget()
        self.tab3 = QTableWidget()
        
        self.tabs.addTab(self.tab1, "📅 Tab 1: Monatliche ungedeckte Bedarfe")
        self.tabs.addTab(self.tab2, "📊 Tab 2: Jahresscheiben (Kosten & Personenmonate)")
        self.tabs.addTab(self.tab3, "⚖️ Tab 3: Deckungsabgleich (Bedarf vs. Projektmittel)")

    def format_euro(self, val):
        if val == 0: return "-"
        return f"{val:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    def get_target_capacity(self, ma, check_date):
        check_end_date = date(check_date.year, check_date.month, calendar.monthrange(check_date.year, check_date.month)[1])
        for az in ma.arbeitszeiten:
            if az.gueltig_ab <= check_end_date and (not az.gueltig_bis or az.gueltig_bis >= check_date):
                return az.anteil_pct
        return 1.0

    def load_data(self):
        start_y = self.spin_start.value()
        end_y = self.spin_end.value()
        if start_y > end_y: return
        
        heute = date.today()
        session = get_session()
        try:
            mitarbeiter_liste = session.query(Mitarbeiter).all()
            zuweisungen = session.query(Zuweisung).filter(
                Zuweisung.end_datum >= date(start_y, 1, 1),
                Zuweisung.start_datum <= date(end_y, 12, 31)
            ).all()
            
            # --- 1. DATENBESCHAFFUNG ---
            ma_daten = {}
            for ma in mitarbeiter_liste:
                if not ma.am_ifpt_seit: continue
                try: 
                    limit_6j = date(ma.am_ifpt_seit.year + 6, ma.am_ifpt_seit.month, ma.am_ifpt_seit.day)
                except ValueError: 
                    limit_6j = date(ma.am_ifpt_seit.year + 6, ma.am_ifpt_seit.month, 28)
                
                commitment_end = ma.geplanter_abgang if (ma.geplanter_abgang and ma.geplanter_abgang < limit_6j) else limit_6j
                
                try:
                    journal = generiere_mitarbeiter_lohnjournal(session, ma.id, start_y, 1, end_y, 12)
                except ValueError as e:
                    QMessageBox.warning(self, "Stammdaten fehlen", str(e))
                    return
                
                kosten_dict = {e["monat"]: e["gesamtkosten_inkl_rueck"] for e in journal}
                
                ma_daten[ma.id] = {
                    "name": f"{ma.nachname}, {ma.vorname}",
                    "start": ma.am_ifpt_seit,
                    "commitment_end": commitment_end,
                    "kosten": kosten_dict,
                    "obj": ma,
                    "bedarf_monate": {},
                    "gedeckt_fix": {},
                    "gedeckt_plan": {}
                }

            for z in zuweisungen:
                if z.mitarbeiter_id not in ma_daten: continue
                start_m_abs = z.start_datum.year * 12 + z.start_datum.month
                end_m_abs = z.end_datum.year * 12 + z.end_datum.month
                for m_abs in range(start_m_abs, end_m_abs + 1):
                    y = m_abs // 12
                    m = m_abs % 12
                    if m == 0: y -= 1; m = 12
                    if y < start_y or y > end_y: continue
                    
                    monat_str = f"{m:02d}/{y}"
                    target_dict = "gedeckt_fix" if z.typ in [ZuweisungsTyp.IST, ZuweisungsTyp.VERTRAG] else "gedeckt_plan"
                    akt_anteil = ma_daten[z.mitarbeiter_id][target_dict].get(monat_str, 0.0)
                    ma_daten[z.mitarbeiter_id][target_dict][monat_str] = akt_anteil + z.anteil_pct

            alle_monate = [f"{m:02d}/{y}" for y in range(start_y, end_y + 1) for m in range(1, 13)]
            
            # Summen für Tab 3
            summen_ungedeckt = {m: 0.0 for m in alle_monate}
            summen_gedeckt_fix = {m: 0.0 for m in alle_monate}
            summen_gedeckt_plan = {m: 0.0 for m in alle_monate}
            
            for ma_id, d in ma_daten.items():
                for m_str in alle_monate:
                    m, y = int(m_str.split('/')[0]), int(m_str.split('/')[1])
                    col_date = date(y, m, 1)
                    
                    ist_pct = d["gedeckt_fix"].get(m_str, 0.0)
                    plan_pct = d["gedeckt_plan"].get(m_str, 0.0)
                    monats_kosten = d["kosten"].get(m_str, 0.0)
                    
                    summen_gedeckt_fix[m_str] += ist_pct * monats_kosten
                    summen_gedeckt_plan[m_str] += (ist_pct + plan_pct) * monats_kosten
                    
                    # LOGIK-FIX: Es kann keinen Bedarf in der Vergangenheit geben.
                    # Alles vor und inklusive dem aktuellen Monat ist 0.
                    is_past_or_current = (y < heute.year) or (y == heute.year and m <= heute.month)
                    
                    if d["start"] <= col_date < d["commitment_end"] and not is_past_or_current:
                        target_cap = self.get_target_capacity(d["obj"], col_date)
                        ungedeckt_pct = max(0.0, target_cap - (ist_pct + plan_pct))
                        
                        if ungedeckt_pct > 0:
                            euro_bedarf = monats_kosten * ungedeckt_pct
                            d["bedarf_monate"][m_str] = {
                                "euro": euro_bedarf,
                                "pm": ungedeckt_pct
                            }
                            summen_ungedeckt[m_str] += euro_bedarf

            # --- RENDER TABELLE 1: MONATLICH ---
            self.tab1.clear()
            self.tab1.setRowCount(0)
            self.tab1.setColumnCount(1 + len(alle_monate))
            self.tab1.setHorizontalHeaderLabels(["Mitarbeiter"] + alle_monate)
            
            for ma_id, d in ma_daten.items():
                if not d["bedarf_monate"]: continue
                row = self.tab1.rowCount()
                self.tab1.insertRow(row)
                self.tab1.setItem(row, 0, QTableWidgetItem(d["name"]))
                
                for c, m_str in enumerate(alle_monate, start=1):
                    val = d["bedarf_monate"].get(m_str, {}).get("euro", 0.0)
                    item = QTableWidgetItem(self.format_euro(val))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if val > 0: item.setForeground(QColor("#E74C3C"))
                    self.tab1.setItem(row, c, item)
            
            self.tab1.insertRow(0)
            sum_item = QTableWidgetItem("SUMMEN UNGEDECKT")
            sum_item.setBackground(QColor("#2C3E50"))
            sum_item.setForeground(QColor("#FFFFFF"))
            sum_item.setFont(sum_item.font()); sum_item.font().setBold(True)
            self.tab1.setItem(0, 0, sum_item)
            for c, m_str in enumerate(alle_monate, start=1):
                item = QTableWidgetItem(self.format_euro(summen_ungedeckt[m_str]))
                item.setBackground(QColor("#2C3E50"))
                item.setForeground(QColor("#FFFFFF"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setFont(item.font()); item.font().setBold(True)
                self.tab1.setItem(0, c, item)

            # --- RENDER TABELLE 2: JAHRESSCHEIBEN ---
            jahre = list(range(start_y, end_y + 1))
            self.tab2.clear()
            self.tab2.setRowCount(0)
            
            spalten_t2 = ["Mitarbeiter"]
            for y in jahre: spalten_t2.extend([f"{y} (€)", f"{y} (PM)"])
            self.tab2.setColumnCount(len(spalten_t2))
            self.tab2.setHorizontalHeaderLabels(spalten_t2)
            
            summen_jahre = {y: {"euro": 0.0, "pm": 0.0} for y in jahre}
            
            for ma_id, d in ma_daten.items():
                if not d["bedarf_monate"]: continue
                row = self.tab2.rowCount()
                self.tab2.insertRow(row)
                self.tab2.setItem(row, 0, QTableWidgetItem(d["name"]))
                
                c = 1
                for y in jahre:
                    y_euro, y_pm = 0.0, 0.0
                    for m in range(1, 13):
                        m_str = f"{m:02d}/{y}"
                        y_euro += d["bedarf_monate"].get(m_str, {}).get("euro", 0.0)
                        y_pm += d["bedarf_monate"].get(m_str, {}).get("pm", 0.0)
                    
                    summen_jahre[y]["euro"] += y_euro
                    summen_jahre[y]["pm"] += y_pm
                    
                    i_euro = QTableWidgetItem(self.format_euro(y_euro))
                    i_pm = QTableWidgetItem(f"{y_pm:.1f}" if y_pm > 0 else "-")
                    i_euro.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    i_pm.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if y_euro > 0: i_euro.setForeground(QColor("#E74C3C"))
                    self.tab2.setItem(row, c, i_euro)
                    self.tab2.setItem(row, c+1, i_pm)
                    c += 2
                    
            self.tab2.insertRow(0)
            sum_item2 = QTableWidgetItem("SUMMEN")
            sum_item2.setBackground(QColor("#2C3E50"))
            sum_item2.setForeground(QColor("#FFFFFF"))
            self.tab2.setItem(0, 0, sum_item2)
            c = 1
            for y in jahre:
                i_euro = QTableWidgetItem(self.format_euro(summen_jahre[y]["euro"]))
                i_pm = QTableWidgetItem(f"{summen_jahre[y]['pm']:.1f}")
                for item in [i_euro, i_pm]:
                    item.setBackground(QColor("#2C3E50"))
                    item.setForeground(QColor("#FFFFFF"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tab2.setItem(0, c, i_euro)
                self.tab2.setItem(0, c+1, i_pm)
                c += 2

            # --- 3. BERECHNUNG FREIE PROJEKTMITTEL (BURN-RATE) ---
            freie_mittel_monatlich = {m: 0.0 for m in alle_monate}
            freie_mittel_inkl_beantragt = {m: 0.0 for m in alle_monate}
            
            projekte = session.query(Projekt).filter(Projekt.status.in_([ProjektStatus.BEWILLIGT, ProjektStatus.BEANTRAGT])).all()
            for p in projekte:
                if not p.projektbeginn or not p.projektende: continue
                
                try: report = generiere_projekt_controlling(session, p.id, heute)
                except ValueError: continue
                
                rest = report["verfuegbare_mittel"]
                if rest <= 0: continue
                
                if p.bewilligungswahrscheinlichkeit_pct is None:
                    QMessageBox.warning(self, "Datenfehler", f"Dem Projekt '{p.projektname}' fehlt die Bewilligungswahrscheinlichkeit.")
                    return
                    
                prob_faktor = p.bewilligungswahrscheinlichkeit_pct / 100.0
                
                m_heute_abs = heute.year * 12 + heute.month
                m_start_abs = p.projektbeginn.year * 12 + p.projektbeginn.month
                m_end_abs = p.projektende.year * 12 + p.projektende.month
                
                # FIX: Wenn das Projekt in der Zukunft startet, beginnt die Burn-Rate erst dann!
                start_calc_abs = max(m_heute_abs, m_start_abs)
                rest_monate = m_end_abs - start_calc_abs + 1
                
                if rest_monate > 0:
                    burn_rate_full = rest / rest_monate
                    burn_rate_prob = burn_rate_full * prob_faktor
                    
                    for m_abs in range(start_calc_abs, m_end_abs + 1):
                        y = m_abs // 12
                        m = m_abs % 12
                        if m == 0: y -= 1; m = 12
                        m_str = f"{m:02d}/{y}"
                        
                        if m_str in freie_mittel_inkl_beantragt:
                            freie_mittel_inkl_beantragt[m_str] += burn_rate_prob
                            if p.status == ProjektStatus.BEWILLIGT:
                                freie_mittel_monatlich[m_str] += burn_rate_full

            # --- RENDER TABELLE 3: DECKUNGSABGLEICH ---
            self.tab3.clear()
            self.tab3.setRowCount(0)
            self.tab3.setColumnCount(1 + len(alle_monate))
            self.tab3.setHorizontalHeaderLabels(["Kennzahl"] + alle_monate)
            self.tab3.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            
            reihen_daten = [
                ("Ungedeckte WiMi-Ansprüche (Lücken)", summen_ungedeckt, "#E74C3C", "Kosten für WiMis, die im WissZeitVG-Fenster (6 Jahre) liegen, aber keinen Vertrag oder Planung haben."),
                ("Gedeckte WiMi-Ansprüche (IST + Obligo)", summen_gedeckt_fix, "#27AE60", "Kosten, die durch gültige, feste Verträge in Bewilligten Projekten gebunden sind."),
                ("Gedeckte WiMi-Ansprüche (inkl. Planung)", summen_gedeckt_plan, "#2980B9", "Kosten inklusive weicher 'Planungs'-Zuweisungen."),
                ("Summe freie Projektmittel (Nur Bewilligte)", freie_mittel_monatlich, "#F39C12", "Das unverplante Restbudget aller BEWILLIGTEN Projekte, gleichmäßig auf ihre verbleibenden Laufzeitmonate aufgeteilt."),
                ("Summe freie Projektmittel (Inkl. Beantragte)", freie_mittel_inkl_beantragt, "#8E44AD", "Soll-Burn-Rate inkl. BEANTRAGTER Projekte, multipliziert mit ihrer Bewilligungswahrscheinlichkeit.")
            ]
            
            for titel, daten_dict, color_hex, tooltip in reihen_daten:
                row = self.tab3.rowCount()
                self.tab3.insertRow(row)
                
                item_title = QTableWidgetItem(titel)
                item_title.setToolTip(tooltip)
                item_title.setBackground(QColor("#2C3E50"))
                item_title.setForeground(QColor("#FFFFFF"))
                item_title.setFont(item_title.font()); item_title.font().setBold(True)
                self.tab3.setItem(row, 0, item_title)
                
                for c, m_str in enumerate(alle_monate, start=1):
                    val = daten_dict.get(m_str, 0.0)
                    item = QTableWidgetItem(self.format_euro(val))
                    item.setBackground(QColor("#34495E"))
                    item.setForeground(QColor("#FFFFFF"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if val > 0: item.setForeground(QColor(color_hex))
                    self.tab3.setItem(row, c, item)
                
        finally:
            session.close()