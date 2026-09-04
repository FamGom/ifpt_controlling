from PyQt6.QtWidgets import (QMessageBox, QWidget, QVBoxLayout, QLabel, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QHBoxLayout, QComboBox, QSplitter, QTabWidget, 
                             QDateEdit, QSpinBox, QRadioButton)
from PyQt6.QtCore import Qt, QDate
from datetime import date

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.database import get_session
from core.models import Projekt, Zuweisung, ZuweisungsTyp, ProjektStatus
from core.calculations import generiere_projekt_controlling 

# ==========================================
# MODUL 1: FINANZ-CONTROLLING 
# ==========================================
class FinanzControllingWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.aktuelle_reports = []
        self.aktuelle_projekte = []
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        title = QLabel("Finanz-Dashboards (Budgets & Jahresscheiben)")
        title.setProperty("title", "true")
        
        refresh_btn = QPushButton("🔄 Finanzen aktualisieren")
        refresh_btn.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 5px;")
        refresh_btn.clicked.connect(self.load_data)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)
        
        widget_gesamt = QWidget()
        layout_gesamt = QVBoxLayout(widget_gesamt)
        layout_gesamt.setContentsMargins(0, 10, 0, 0)
        layout_gesamt.addWidget(QLabel("<b>Ansicht 1: Gesamt-Budget über gesamte Projektlaufzeit</b>"))
        
        self.table_gesamt = QTableWidget()
        spalten_gesamt = ["Projekt", "Budget gesamt", "Ist-Kosten", "Obligo", "Plan-Ausgaben", "Verfügbar", "Verfügbar %"]
        self.table_gesamt.setColumnCount(len(spalten_gesamt))
        self.table_gesamt.setHorizontalHeaderLabels(spalten_gesamt)
        self.table_gesamt.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_gesamt.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) 
        self.table_gesamt.setAlternatingRowColors(True)
        self.table_gesamt.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout_gesamt.addWidget(self.table_gesamt)
        splitter.addWidget(widget_gesamt)

        widget_jahr = QWidget()
        layout_jahr = QVBoxLayout(widget_jahr)
        layout_jahr.setContentsMargins(0, 20, 0, 0)
        
        header_jahr = QHBoxLayout()
        header_jahr.addWidget(QLabel("<b>Ansicht 2: Jahresscheibe für das Jahr:</b>"))
        self.combo_jahr = QComboBox()
        for y in range(2024, 2035):
            self.combo_jahr.addItem(str(y), y)
        self.combo_jahr.setCurrentText(str(date.today().year)) 
        self.combo_jahr.currentIndexChanged.connect(self.update_jahresscheibe)
        header_jahr.addWidget(self.combo_jahr)
        header_jahr.addStretch()
        layout_jahr.addLayout(header_jahr)
        
        self.table_jahr = QTableWidget()
        spalten_jahr = ["Projekt", "Initiales Jahresbudget", "Vorjahresübertrag", "Budget in Jahr", "Verbrauch (Ist+Obligo)", "Plan-Ausgaben", "Restmittel"]
        self.table_jahr.setColumnCount(len(spalten_jahr))
        self.table_jahr.setHorizontalHeaderLabels(spalten_jahr)
        self.table_jahr.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_jahr.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_jahr.setAlternatingRowColors(True)
        self.table_jahr.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout_jahr.addWidget(self.table_jahr)
        splitter.addWidget(widget_jahr)
        
        layout.addWidget(splitter)

    def format_currency(self, value):
        return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    def load_data(self):
        session = get_session()
        heute = date.today()
        self.aktuelle_reports = []
        self.aktuelle_projekte = []
        
        try:
            projekte = session.query(Projekt).all()
            self.table_gesamt.setRowCount(0)
            
            for projekt in projekte:
                try:
                    report = generiere_projekt_controlling(session, projekt.id, heute)
                except ValueError as e:
                    # HARTER CHECK: Schlägt an, wenn System- oder Tarifdaten in DB fehlen!
                    QMessageBox.critical(self, f"Stammdaten-Fehler in Projekt: {projekt.projektname}", str(e))
                    self.table_gesamt.setRowCount(0)
                    self.table_jahr.setRowCount(0)
                    return # Bricht das Laden ab, bis der User das Problem behebt
                    
                self.aktuelle_reports.append(report)
                self.aktuelle_projekte.append(projekt)
                
                row_idx = self.table_gesamt.rowCount()
                self.table_gesamt.insertRow(row_idx)
                self.table_gesamt.setItem(row_idx, 0, QTableWidgetItem(report["projekt"]))
                
                werte = [
                    self.format_currency(report["budget_gesamt"]),
                    self.format_currency(report["ist_buchungen_gesamt"]),
                    self.format_currency(report["obligo_gesamt"]),
                    self.format_currency(report["plan_ausgaben_gesamt"]),
                    self.format_currency(report["verfuegbare_mittel"]),
                    f"{report['verfuegbar_pct']} %"
                ]
                
                for col_idx, wert in enumerate(werte, start=1):
                    item = QTableWidgetItem(wert)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if col_idx == 5 and report["verfuegbare_mittel"] < 0:
                        item.setForeground(Qt.GlobalColor.red)
                    self.table_gesamt.setItem(row_idx, col_idx, item)
                    
            self.update_jahresscheibe()
        finally:
            session.close()

    def update_jahresscheibe(self):
        ziel_jahr = self.combo_jahr.currentData()
        if not ziel_jahr: return
        self.table_jahr.setRowCount(0)
        
        for projekt, report in zip(self.aktuelle_projekte, self.aktuelle_reports):
            if not projekt.projektbeginn or not projekt.projektende: continue
            
            # ==============================================================
            # FIX: Projekte komplett ausblenden, wenn sie im Zieljahr nicht laufen!
            # Verhindert, dass alte Defizite in ferner Zukunft auftauchen.
            # ==============================================================
            if ziel_jahr < projekt.projektbeginn.year or ziel_jahr > projekt.projektende.year:
                continue

            start_m = projekt.projektbeginn.year * 12 + projekt.projektbeginn.month
            end_m = projekt.projektende.year * 12 + projekt.projektende.month
            monate_gesamt = end_m - start_m + 1
            if monate_gesamt <= 0: continue
            
            budget_pro_monat = report["budget_gesamt"] / monate_gesamt
            monate_im_zieljahr = sum(1 for m in range(1, 13) if start_m <= (ziel_jahr * 12 + m) <= end_m)
            initiales_jahresbudget = budget_pro_monat * monate_im_zieljahr
            
            vorjahresuebertrag = 0.0
            if ziel_jahr > projekt.projektbeginn.year:
                monate_davor = (ziel_jahr * 12 + 1) - start_m
                budget_davor_linear = budget_pro_monat * monate_davor
                kosten_davor = sum(m.get("ist_kosten_cf", m.get("ist_kosten", 0.0)) + m["obligo"] for m in report["monats_verlauf"] if int(m["monat"].split("/")[1]) < ziel_jahr)
                vorjahresuebertrag = budget_davor_linear - kosten_davor

            ist_und_obligo_jahr = sum(m.get("ist_kosten_cf", m.get("ist_kosten", 0.0)) + m["obligo"] for m in report["monats_verlauf"] if int(m["monat"].split("/")[1]) == ziel_jahr)
            plan_jahr = sum(m["plan_kosten"] for m in report["monats_verlauf"] if int(m["monat"].split("/")[1]) == ziel_jahr)
            
            budget_verfuegbar_jahr = initiales_jahresbudget + vorjahresuebertrag
            restmittel_jahr = budget_verfuegbar_jahr - ist_und_obligo_jahr
            
            row_idx = self.table_jahr.rowCount()
            self.table_jahr.insertRow(row_idx)
            self.table_jahr.setItem(row_idx, 0, QTableWidgetItem(projekt.projektname))
            
            werte = [
                self.format_currency(initiales_jahresbudget),
                self.format_currency(vorjahresuebertrag),
                self.format_currency(budget_verfuegbar_jahr),
                self.format_currency(ist_und_obligo_jahr),
                self.format_currency(plan_jahr),
                self.format_currency(restmittel_jahr)
            ]
            for col_idx, wert in enumerate(werte, start=1):
                item = QTableWidgetItem(wert)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col_idx == 6 and restmittel_jahr < 0:
                    item.setForeground(Qt.GlobalColor.red)
                self.table_jahr.setItem(row_idx, col_idx, item)


    
# ==========================================
# MODUL 2: PERSONAL-CONTROLLING (Soll vs. Ist)
# ==========================================
class PersonalControllingWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.lade_projekte_in_filter()
        self.load_controlling_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        title = QLabel("Personal-Controlling (Soll-Ist-Abgleich)")
        title.setProperty("title", "true")
        header_layout.addWidget(title)
        
        refresh_btn = QPushButton("🔄 Auswertung laden")
        refresh_btn.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold; padding: 5px;")
        refresh_btn.clicked.connect(self.load_controlling_data)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Stichtag für Auswertung:"))
        self.date_stichtag = QDateEdit()
        self.date_stichtag.setDate(QDate.currentDate())
        self.date_stichtag.setCalendarPopup(True)
        self.date_stichtag.dateChanged.connect(self.load_controlling_data)
        filter_layout.addWidget(self.date_stichtag)
        
        filter_layout.addWidget(QLabel("   Projekt-Filter:"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItem("Alle Projekte", None)
        self.combo_filter.currentIndexChanged.connect(self.load_controlling_data)
        filter_layout.addWidget(self.combo_filter)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        self.table = QTableWidget()
        self.spalten = ["Projekt", "Mitarbeiter", "Soll (Planung) %", "Ist (Gebucht) %", "Abweichung"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def lade_projekte_in_filter(self):
        session = get_session()
        try:
            for p in session.query(Projekt).order_by(Projekt.projektname).all():
                self.combo_filter.addItem(p.projektname, p.id)
        finally:
            session.close()

    def load_controlling_data(self):
        self.table.setRowCount(0)
        session = get_session()
        try:
            stichtag = self.date_stichtag.date().toPyDate()
            filter_projekt_id = self.combo_filter.currentData()
            
            query = session.query(Zuweisung).filter(
                Zuweisung.start_datum <= stichtag,
                Zuweisung.end_datum >= stichtag
            )
            
            if filter_projekt_id:
                query = query.filter(Zuweisung.projekt_id == filter_projekt_id)
                
            aktive_zuweisungen = query.all()
            
            daten = {}
            for z in aktive_zuweisungen:
                if not z.projekt or not z.mitarbeiter: continue
                
                key = (z.projekt.projektname, f"{z.mitarbeiter.nachname}, {z.mitarbeiter.vorname}")
                if key not in daten:
                    daten[key] = {"soll": 0.0, "ist": 0.0, "has_ist_record": False}
                    
                if z.typ in [ZuweisungsTyp.VERTRAG, ZuweisungsTyp.PLANUNG]:
                    daten[key]["soll"] += z.anteil_pct
                elif z.typ == ZuweisungsTyp.IST:
                    daten[key]["ist"] += z.anteil_pct
                    daten[key]["has_ist_record"] = True
                    
            for (p_name, m_name), werte in daten.items():
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                soll_pct = werte["soll"] * 100
                ist_pct = werte["ist"] * 100 if werte["has_ist_record"] else soll_pct
                abweichung = ist_pct - soll_pct
                
                self.table.setItem(row, 0, QTableWidgetItem(p_name))
                self.table.setItem(row, 1, QTableWidgetItem(m_name))
                self.table.setItem(row, 2, QTableWidgetItem(f"{soll_pct:.1f} %"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{ist_pct:.1f} %"))
                
                item_abw = QTableWidgetItem(f"{abweichung:+.1f} %")
                item_abw.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                if abweichung > 0:
                    item_abw.setForeground(Qt.GlobalColor.red)
                elif abweichung < 0:
                    item_abw.setForeground(Qt.GlobalColor.green)
                else:
                    item_abw.setForeground(Qt.GlobalColor.gray) 
                    
                self.table.setItem(row, 4, item_abw)
        finally:
            session.close()

# ==========================================
# MODUL 3: GRAFISCHES DASHBOARD (Burn-Down & Töpfe)
# ==========================================
class GraphControllingWidget(QWidget):
    def __init__(self, controlling_view_parent):
        super().__init__()
        self.main_view = controlling_view_parent
        self.aktuelle_reports = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- TOOLBAR 1: FILTER & AUSWAHL ---
        toolbar1 = QHBoxLayout()
        toolbar1.addWidget(QLabel("<b>Projekt:</b>"))
        self.combo_projekte = QComboBox()
        self.combo_projekte.setMinimumWidth(250)
        self.combo_projekte.currentIndexChanged.connect(self.update_ansicht)
        toolbar1.addWidget(self.combo_projekte)
        
        toolbar1.addWidget(QLabel("  <b>Status:</b>"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(["Nur Bewilligte Projekte", "Alle (inkl. Beantragt)"])
        # ÄNDERUNG: Status filtert jetzt aktiv die Dropdown-Liste
        self.combo_status.currentIndexChanged.connect(self.lade_projekte)
        toolbar1.addWidget(self.combo_status)
        
        toolbar1.addWidget(QLabel("  <b>Aktiv in:</b>"))
        self.spin_filter_start = QSpinBox()
        self.spin_filter_start.setRange(2000, 2060)
        self.spin_filter_start.setValue(date.today().year - 1)
        self.spin_filter_start.valueChanged.connect(self.check_filter_dates)
        toolbar1.addWidget(self.spin_filter_start)
        
        toolbar1.addWidget(QLabel("-"))
        self.spin_filter_end = QSpinBox()
        self.spin_filter_end.setRange(2000, 2060)
        self.spin_filter_end.setValue(date.today().year + 2)
        self.spin_filter_end.valueChanged.connect(self.check_filter_dates)
        toolbar1.addWidget(self.spin_filter_end)
        
        btn_refresh = QPushButton("🔄 Daten laden")
        btn_refresh.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold;")
        btn_refresh.clicked.connect(self.lade_projekte)
        toolbar1.addStretch()
        toolbar1.addWidget(btn_refresh)
        layout.addLayout(toolbar1)
        
        # --- TOOLBAR 2: GRAPH-EINSTELLUNGEN ---
        toolbar2 = QHBoxLayout()
        toolbar2.addWidget(QLabel("<b>X-Achse (Graph):</b>"))
        self.spin_start = QSpinBox()
        self.spin_start.setRange(2020, 2060)
        self.spin_start.setValue(date.today().year)
        self.spin_start.valueChanged.connect(self.check_dates)
        toolbar2.addWidget(self.spin_start)
        
        toolbar2.addWidget(QLabel("bis"))
        self.spin_end = QSpinBox()
        self.spin_end.setRange(2020, 2060)
        self.spin_end.setValue(date.today().year)
        self.spin_end.valueChanged.connect(self.check_dates)
        toolbar2.addWidget(self.spin_end)
        
        toolbar2.addSpacing(30)
        toolbar2.addWidget(QLabel("<b>Balken-Berechnung:</b>"))
        self.radio_ist = QRadioButton("Konto-Belastung (Cash-Flow)")
        self.radio_ctrl = QRadioButton("Controlling (inkl. Rückstellungen)")
        self.radio_ctrl.setChecked(True)
        self.radio_ist.toggled.connect(self.zeichne_graph)
        
        toolbar2.addWidget(self.radio_ist)
        toolbar2.addWidget(self.radio_ctrl)
        toolbar2.addStretch()
        layout.addLayout(toolbar2)
        
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.zeichne_graph)
        layout.addWidget(self.tabs)
        
        self.tab_keys = [
            ("gesamt", "📊 Gesamtbudget", "Gesamtbudget"),
            ("personal_gesamt", "👥 Personal (Gesamt)", "Personal (Gesamt)"),
            ("e13_15", "🔬 Personal E13-E15", "Personal E13-E15"),
            ("e1_12", "⚙️ Personal E1-E12", "Personal E1-E12"),
            ("hiwi", "🎓 Hilfskräfte (SHK/WHK)", "Hilfskräfte"),
            ("sachmittel", "🛒 Sachmittel", "Sachmittel")
        ]
        
        for key, title, clean_title in self.tab_keys:
            self.tabs.addTab(QWidget(), title)
            
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    def check_filter_dates(self):
        self.spin_filter_start.blockSignals(True)
        self.spin_filter_end.blockSignals(True)
        if self.spin_filter_end.value() < self.spin_filter_start.value():
            self.spin_filter_end.setValue(self.spin_filter_start.value())
        self.spin_filter_start.blockSignals(False)
        self.spin_filter_end.blockSignals(False)
        self.lade_projekte()

    def check_dates(self):
        self.spin_start.blockSignals(True)
        self.spin_end.blockSignals(True)
        if self.spin_end.value() < self.spin_start.value():
            self.spin_end.setValue(self.spin_start.value())
        self.spin_start.blockSignals(False)
        self.spin_end.blockSignals(False)
        self.zeichne_graph()

    def lade_projekte(self):
        # Merken, welches Projekt gerade gewählt war
        aktuell_gewaehlt = self.combo_projekte.currentData()
        
        self.combo_projekte.blockSignals(True)
        self.combo_projekte.clear()
        self.combo_projekte.addItem("🌍 Gesamtportfolio (gefiltert)", "ALLE")
        
        status_filter = self.combo_status.currentIndex()
        f_start = self.spin_filter_start.value()
        f_end = self.spin_filter_end.value()
        
        session = get_session()
        try:
            self.aktuelle_reports = self.main_view.finanz_widget.aktuelle_reports
            for report in self.aktuelle_reports:
                p = session.query(Projekt).filter_by(projektname=report["projekt"]).first()
                if not p: continue
                
                # Filter 1: Status
                if status_filter == 0 and p.status != ProjektStatus.BEWILLIGT:
                    continue
                    
                # Filter 2: Zeitliche Überschneidung
                if p.projektbeginn and p.projektende:
                    if p.projektende.year >= f_start and p.projektbeginn.year <= f_end:
                        self.combo_projekte.addItem(report["projekt"], report)
        finally:
            session.close()
            
        # Projekt wiederherstellen, falls es nach dem Filtern noch da ist
        if aktuell_gewaehlt and aktuell_gewaehlt != "ALLE":
            idx = self.combo_projekte.findText(aktuell_gewaehlt["projekt"])
            if idx >= 0:
                self.combo_projekte.setCurrentIndex(idx)
                
        self.combo_projekte.blockSignals(False)
        self.update_ansicht()

    def update_ansicht(self):
        projekt_data = self.combo_projekte.currentData()
        if not projekt_data: return
        
        f_start = self.spin_filter_start.value()
        f_end = self.spin_filter_end.value()
        status_filter = self.combo_status.currentIndex()
        
        session = get_session()
        try:
            b_e13 = b_e12 = b_hiwi = b_sach = 0.0
            
            if projekt_data == "ALLE":
                query = session.query(Projekt)
                projekte = query.all()
                
                if status_filter == 0:
                    projekte = [p for p in projekte if p.status == ProjektStatus.BEWILLIGT]
                
                # Dieselbe Überschneidungs-Logik für das Portfolio-Budget
                projekte = [p for p in projekte if p.projektbeginn and p.projektende and p.projektende.year >= f_start and p.projektbeginn.year <= f_end]
                
                if projekte:
                    valid_starts = [p.projektbeginn.year for p in projekte if p.projektbeginn]
                    valid_ends = [p.projektende.year for p in projekte if p.projektende]
                    min_y = min(valid_starts, default=date.today().year)
                    max_y = max(valid_ends, default=date.today().year)
                    
                    self.spin_start.blockSignals(True); self.spin_end.blockSignals(True)
                    self.spin_start.setValue(min_y); self.spin_end.setValue(max_y)
                    self.spin_start.blockSignals(False); self.spin_end.blockSignals(False)
                    
                    for p in projekte:
                        b_e13 += getattr(p, "personalbudget_e13_e15", 0.0) or 0.0
                        b_e12 += getattr(p, "personalbudget_e1_e12", 0.0) or 0.0
                        b_hiwi += getattr(p, "personalbudget_besch_entgelt", 0.0) or 0.0
                        b_sach += getattr(p, "sachmittelbudget", 0.0) or 0.0
            else:
                p = session.query(Projekt).filter_by(projektname=projekt_data["projekt"]).first()
                if p:
                    if p.projektbeginn and p.projektende:
                        self.spin_start.blockSignals(True); self.spin_end.blockSignals(True)
                        self.spin_start.setValue(p.projektbeginn.year); self.spin_end.setValue(p.projektende.year)
                        self.spin_start.blockSignals(False); self.spin_end.blockSignals(False)
                    
                    b_e13 = getattr(p, "personalbudget_e13_e15", 0.0) or 0.0
                    b_e12 = getattr(p, "personalbudget_e1_e12", 0.0) or 0.0
                    b_hiwi = getattr(p, "personalbudget_besch_entgelt", 0.0) or 0.0
                    b_sach = getattr(p, "sachmittelbudget", 0.0) or 0.0
            
            self.tabs.setTabVisible(2, b_e13 > 0)
            self.tabs.setTabVisible(3, b_e12 > 0)
            self.tabs.setTabVisible(4, b_hiwi > 0)
            self.tabs.setTabVisible(5, b_sach > 0)
        finally:
            session.close()
            
        self.zeichne_graph()

    def zeichne_graph(self):
        if not hasattr(self, 'figure'): return
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        projekt_data = self.combo_projekte.currentData()
        if not projekt_data: return
        
        status_filter = self.combo_status.currentIndex()
        f_start = self.spin_filter_start.value()
        f_end = self.spin_filter_end.value()
        ansicht_key = self.tab_keys[self.tabs.currentIndex()][0]
        graph_title = "Portfolio-Ansicht" if projekt_data == "ALLE" else projekt_data["projekt"]
            
        start_y, end_y = self.spin_start.value(), self.spin_end.value()
        alle_monate = [f"{m:02d}/{y}" for y in range(start_y, end_y + 1) for m in range(1, 13)]
        if not alle_monate: return

        session = get_session()
        gefilterte_reports = []
        budget_zufluss = {m: 0.0 for m in alle_monate}
        budget_kumuliert_start = 0.0
        
        try:
            reports_to_check = self.aktuelle_reports if projekt_data == "ALLE" else [projekt_data]
            
            for r in reports_to_check:
                p = session.query(Projekt).filter_by(projektname=r["projekt"]).first()
                if not p: continue
                
                if projekt_data == "ALLE":
                    if status_filter == 0 and p.status != ProjektStatus.BEWILLIGT:
                        continue
                    if not (p.projektbeginn and p.projektende and p.projektende.year >= f_start and p.projektbeginn.year <= f_end):
                        continue
                    
                gefilterte_reports.append(r)
                
                b_e12 = getattr(p, "personalbudget_e1_e12", 0.0) or 0.0
                b_e13 = getattr(p, "personalbudget_e13_e15", 0.0) or 0.0
                b_hiwi = getattr(p, "personalbudget_besch_entgelt", 0.0) or 0.0
                b_sach = getattr(p, "sachmittelbudget", 0.0) or 0.0
                
                p_bud = 0.0
                if ansicht_key == "gesamt": 
                    p_bud = b_e12 + b_e13 + b_hiwi + b_sach
                elif ansicht_key == "personal_gesamt": 
                    p_bud = b_e12 + b_e13 + b_hiwi
                elif ansicht_key == "e13_15": p_bud = b_e13
                elif ansicht_key == "e1_12": p_bud = b_e12
                elif ansicht_key == "hiwi": p_bud = b_hiwi
                elif ansicht_key == "sachmittel": p_bud = b_sach
                
                if p.projektbeginn:
                    start_str = f"{p.projektbeginn.month:02d}/{p.projektbeginn.year}"
                    if start_str in budget_zufluss:
                        budget_zufluss[start_str] += p_bud
                    else:
                        if p.projektbeginn.year < start_y or (p.projektbeginn.year == start_y and p.projektbeginn.month < 1):
                            budget_kumuliert_start += p_bud
        finally:
            session.close()

        if not gefilterte_reports:
            ax.text(0.5, 0.5, "Keine aktiven Projekte für diesen Filter im gewählten Zeitraum.", 
                    horizontalalignment='center', verticalalignment='center', 
                    transform=ax.transAxes, fontsize=12, color="gray")
            self.figure.tight_layout()
            self.canvas.draw()
            return
            
        ist_cf_reihe = {m: 0.0 for m in alle_monate}
        ist_ctrl_reihe = {m: 0.0 for m in alle_monate}
        obligo_cf_reihe = {m: 0.0 for m in alle_monate}
        obligo_ctrl_reihe = {m: 0.0 for m in alle_monate}
        plan_cf_reihe = {m: 0.0 for m in alle_monate}
        plan_ctrl_reihe = {m: 0.0 for m in alle_monate}
        
        def safe_get(tup_or_float, idx):
            if isinstance(tup_or_float, tuple): return tup_or_float[idx]
            return tup_or_float if tup_or_float is not None else 0.0

        for r in gefilterte_reports:
            for mv in r.get("monats_verlauf", []):
                monat = mv["monat"]
                if monat not in alle_monate: continue
                det = mv.get("details")
                if not det: continue 
                
                toepfe = ["e13_15", "e1_12", "hiwi", "sachmittel"]
                if ansicht_key not in ["gesamt", "personal_gesamt"]: toepfe = [ansicht_key]
                elif ansicht_key == "personal_gesamt": toepfe = ["e13_15", "e1_12", "hiwi"]
                    
                for t in toepfe:
                    ist_cf_reihe[monat] += safe_get(det["ist"].get(t, (0.0, 0.0)), 0)
                    ist_ctrl_reihe[monat] += safe_get(det["ist"].get(t, (0.0, 0.0)), 1)
                    obligo_cf_reihe[monat] += safe_get(det["obligo"].get(t, (0.0, 0.0)), 0)
                    obligo_ctrl_reihe[monat] += safe_get(det["obligo"].get(t, (0.0, 0.0)), 1)
                    plan_cf_reihe[monat] += safe_get(det["plan"].get(t, (0.0, 0.0)), 0)
                    plan_ctrl_reihe[monat] += safe_get(det["plan"].get(t, (0.0, 0.0)), 1)

        rest_ist, rest_obligo, rest_plan, monats_balken, budget_linie = [], [], [], [], []
        laufendes_max_budget = budget_kumuliert_start
        
        kumuliert_ist = 0.0
        kumuliert_obligo = 0.0
        kumuliert_plan = 0.0
        
        nutze_ctrl = self.radio_ctrl.isChecked()
        
        for m in alle_monate:
            laufendes_max_budget += budget_zufluss[m]
            budget_linie.append(laufendes_max_budget)
            
            m_ist = ist_ctrl_reihe[m] if nutze_ctrl else ist_cf_reihe[m]
            m_obl = obligo_ctrl_reihe[m] if nutze_ctrl else obligo_cf_reihe[m]
            m_pln = plan_ctrl_reihe[m] if nutze_ctrl else plan_cf_reihe[m]
            
            monats_balken.append(m_ist + m_obl + m_pln)
            
            kumuliert_ist += m_ist
            kumuliert_obligo += (m_ist + m_obl)
            kumuliert_plan += (m_ist + m_obl + m_pln)
            
            rest_ist.append(laufendes_max_budget - kumuliert_ist)
            rest_obligo.append(laufendes_max_budget - kumuliert_obligo)
            rest_plan.append(laufendes_max_budget - kumuliert_plan)
            
        ax2 = ax.twinx()
        ax2.bar(alle_monate, monats_balken, alpha=0.15, color="#7F8C8D", label="Mtl. Ausgaben")
        ax2.set_ylabel("Monatlicher Abfluss (€)")
        ax2.set_ylim(0, max(monats_balken + [1]) * 3) 
            
        ax.plot(alle_monate, [0]*len(alle_monate), color="black", linewidth=1.5) 
        ax.plot(alle_monate, budget_linie, label="Verfügbares Portfolio-Budget (Zufluss)", color="black", linestyle="--", linewidth=1.5, alpha=0.6)
        
        ax.plot(alle_monate, rest_ist, label="Nur Ist-Kosten gebucht", color="#27AE60", linewidth=3)
        ax.plot(alle_monate, rest_obligo, label="Inkl. fester Verträge (Obligo)", color="#F39C12", linewidth=2.5)
        ax.plot(alle_monate, rest_plan, label="Inkl. unverbindl. Planung", color="#3498DB", linewidth=2, linestyle=":")
        ax.fill_between(alle_monate, rest_obligo, rest_plan, color="#3498DB", alpha=0.1)
        
        topf_name_clean = next(t[2] for t in self.tab_keys if t[0] == ansicht_key)
        ax.set_title(f"{graph_title} | {topf_name_clean}")
        ax.set_ylabel("Restbudget (€)")
        
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper right")
        
        ax.grid(True, linestyle=":", alpha=0.7)
        if len(alle_monate) > 12: 
            ax.set_xticks(range(0, len(alle_monate), max(1, len(alle_monate)//10)))
            
        self.figure.tight_layout()
        self.canvas.draw()

        
# ==========================================
# HAUPT-CONTAINER (Regelt die Rechte/Tabs)
# ==========================================
class ControllingView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.finanz_widget = FinanzControllingWidget()
        self.personal_widget = PersonalControllingWidget()
        self.graph_widget = GraphControllingWidget(self)
        
        self.tabs.addTab(self.finanz_widget, "💶 Finanz-Dashboard (Budgets)")
        self.tabs.addTab(self.personal_widget, "👥 Personal-Auslastung (Soll/Ist)")
        self.tabs.addTab(self.graph_widget, "📈 Budget Burn-Down (Graphen)")
        
        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        if index == 0:
            self.finanz_widget.load_data()
        elif index == 1:
            self.personal_widget.load_controlling_data()
        elif index == 2:
            self.finanz_widget.load_data() 
            self.graph_widget.lade_projekte()