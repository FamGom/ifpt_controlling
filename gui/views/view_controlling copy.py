from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QHBoxLayout, QComboBox, QSplitter, QTabWidget, QDateEdit)
from PyQt6.QtCore import Qt, QDate
from datetime import date

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.database import get_session
from core.models import Projekt, Zuweisung, ZuweisungsTyp
from core.calculations import generiere_projekt_controlling 

# ==========================================
# MODUL 1: FINANZ-CONTROLLING 
# ==========================================
class FinanzControllingWidget(QWidget):
    """Zeigt Budgets, Ist-Kosten, Obligo und Jahresscheiben in Euro an."""
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
        
        # --- TABELLE 1: GESAMTÜBERSICHT ---
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

        # --- TABELLE 2: JAHRESSCHEIBEN ---
        widget_jahr = QWidget()
        layout_jahr = QVBoxLayout(widget_jahr)
        layout_jahr.setContentsMargins(0, 20, 0, 0)
        
        header_jahr = QHBoxLayout()
        header_jahr.addWidget(QLabel("<b>Ansicht 2: Jahresscheibe für das Jahr:</b>"))
        self.combo_jahr = QComboBox()
        for y in range(2024, 2031):
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
                report = generiere_projekt_controlling(session, projekt.id, heute)
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
                kosten_davor = sum(m["ist_kosten"] + m["obligo"] for m in report["monats_verlauf"] if int(m["monat"].split("/")[1]) < ziel_jahr)
                vorjahresuebertrag = budget_davor_linear - kosten_davor

            ist_und_obligo_jahr = sum(m["ist_kosten"] + m["obligo"] for m in report["monats_verlauf"] if int(m["monat"].split("/")[1]) == ziel_jahr)
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
    """Zeigt die Auslastung und Plan-Ist-Abweichung auf Personalbasis in %."""
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
        
        # --- FILTER-BEREICH ---
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
        
        # --- TABELLE ---
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
        """Echte Soll-Ist Logik: Ist = Soll (Default), es sei denn, es gibt eine Ausnahme."""
        self.table.setRowCount(0)
        session = get_session()
        try:
            stichtag = self.date_stichtag.date().toPyDate()
            filter_projekt_id = self.combo_filter.currentData()
            
            # Alle Zuweisungen laden, die am gewählten Stichtag aktiv sind
            query = session.query(Zuweisung).filter(
                Zuweisung.start_datum <= stichtag,
                Zuweisung.end_datum >= stichtag
            )
            
            if filter_projekt_id:
                query = query.filter(Zuweisung.projekt_id == filter_projekt_id)
                
            aktive_zuweisungen = query.all()
            
            # Gruppieren nach Projekt und Mitarbeiter
            daten = {}
            for z in aktive_zuweisungen:
                if not z.projekt or not z.mitarbeiter: continue
                
                key = (z.projekt.projektname, f"{z.mitarbeiter.nachname}, {z.mitarbeiter.vorname}")
                if key not in daten:
                    # Wir merken uns, ob es einen EXPLIZITEN Ist-Eintrag gab
                    daten[key] = {"soll": 0.0, "ist": 0.0, "has_ist_record": False}
                    
                if z.typ in [ZuweisungsTyp.VERTRAG, ZuweisungsTyp.PLANUNG]:
                    daten[key]["soll"] += z.anteil_pct
                elif z.typ == ZuweisungsTyp.IST:
                    daten[key]["ist"] += z.anteil_pct
                    daten[key]["has_ist_record"] = True
                    
            # In die Tabelle einfügen
            for (p_name, m_name), werte in daten.items():
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                soll_pct = werte["soll"] * 100
                
                # DIE NEUE LOGIK: Wenn es keinen Ist-Zettel gibt, ist Ist = Soll!
                if werte["has_ist_record"]:
                    ist_pct = werte["ist"] * 100
                else:
                    ist_pct = soll_pct
                    
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
# MODUL 3: GRAFISCHES DASHBOARD (Burn-Down)
# ==========================================
class GraphControllingWidget(QWidget):
    def __init__(self, controlling_view_parent):
        super().__init__()
        self.main_view = controlling_view_parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("<b>Projekt auswählen:</b>"))
        self.combo_projekte = QComboBox()
        self.combo_projekte.currentIndexChanged.connect(self.zeichne_graph)
        toolbar.addWidget(self.combo_projekte)
        
        btn_refresh = QPushButton("🔄 Aktualisieren")
        btn_refresh.clicked.connect(self.lade_projekte)
        toolbar.addWidget(btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Matplotlib Canvas
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    def lade_projekte(self):
        self.combo_projekte.clear()
        # Wir bedienen uns einfach an den bereits geladenen Daten des Finanz-Widgets!
        for report in self.main_view.finanz_widget.aktuelle_reports:
            self.combo_projekte.addItem(report["projekt"], report)
        self.zeichne_graph()

    def zeichne_graph(self):
        self.figure.clear()
        report = self.combo_projekte.currentData()
        if not report or not report.get("monats_verlauf"):
            self.canvas.draw()
            return
            
        ax = self.figure.add_subplot(111)
        monate = [m["monat"] for m in report["monats_verlauf"]]
        budget = report["budget_gesamt"]
        
        # Laufende Abwärts-Rechnung für 3 getrennte Ebenen
        rest_ist = []
        rest_obligo = []
        rest_plan = []
        
        laufend_ist = budget
        laufend_obligo = budget
        laufend_plan = budget
        
        monats_kosten = []
        
        for m in report["monats_verlauf"]:
            kosten_gesamt_monat = m["ist_kosten"] + m["obligo"] + m["plan_kosten"]
            monats_kosten.append(kosten_gesamt_monat)
            
            # 1. Stufe: Nur harte Ist-Abflüsse
            laufend_ist -= m["ist_kosten"]
            # 2. Stufe: Ist + feste Verträge (Obligo)
            laufend_obligo -= (m["ist_kosten"] + m["obligo"])
            # 3. Stufe: Ist + Verträge + weiche Planung
            laufend_plan -= kosten_gesamt_monat
            
            rest_ist.append(laufend_ist)
            rest_obligo.append(laufend_obligo)
            rest_plan.append(laufend_plan)
            
        # Balkendiagramm für monatlichen Mittelabfluss im Hintergrund (2. Y-Achse)
        ax2 = ax.twinx()
        ax2.bar(monate, monats_kosten, alpha=0.15, color="#7F8C8D", label="Mtl. Belastung")
        ax2.set_ylabel("Monatlicher Abfluss (€)")
        ax2.set_ylim(0, max(monats_kosten + [1]) * 3) 
            
        # Linien zeichnen
        ax.plot(monate, [0]*len(monate), color="black", linewidth=1.5) 
        ax.plot([monate[0], monate[-1]], [budget, 0], label="Ideal-Verlauf (Linear)", color="gray", linestyle="--")
        
        # Die 3 Burn-Down-Szenarien
        ax.plot(monate, rest_ist, label="1. Nur Ist-Kosten gebucht", color="#27AE60", linewidth=3)
        ax.plot(monate, rest_obligo, label="2. Inkl. fester Verträge (Obligo)", color="#F39C12", linewidth=2.5, linestyle="-")
        ax.plot(monate, rest_plan, label="3. Inkl. unverbindl. Planung", color="#3498DB", linewidth=2, linestyle=":")
        
        # Fläche zwischen Obligo und Planung schraffieren (macht den Handlungsspielraum sichtbar)
        ax.fill_between(monate, rest_obligo, rest_plan, color="#3498DB", alpha=0.1)
        
        ax.set_title(f"Budget Burn-Down: {report['projekt']}")
        ax.set_ylabel("Restbudget (€)")
        
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper right")
        
        ax.grid(True, linestyle=":", alpha=0.7)
        if len(monate) > 12: 
            ax.set_xticks(range(0, len(monate), max(1, len(monate)//10)))
            
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
        
        # NEU: Auto-Refresh bei Tab-Wechsel
        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        if index == 0:
            self.finanz_widget.load_data()
        elif index == 1:
            self.personal_widget.load_controlling_data()
        elif index == 2:
            # Damit der Graph sofort die neusten Berechnungen aus dem Finanz-Tab holt
            self.finanz_widget.load_data() 
            self.graph_widget.lade_projekte()