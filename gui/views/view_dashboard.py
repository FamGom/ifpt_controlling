from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from core.database import get_session
from core.calculations import generiere_instituts_controlling

class KPIFrame(QFrame):
    def __init__(self, title, val_base, val_opt, color="#2C3E50"):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{ background-color: white; border-radius: 8px; border-left: 5px solid {color}; padding: 12px; }}
        """)
        layout = QVBoxLayout(self)
        
        lbl_t = QLabel(title.upper())
        lbl_t.setStyleSheet("color: #7F8C8D; font-weight: bold; font-size: 10px;")
        
        lbl_b = QLabel(f"Garantiert: {val_base}")
        lbl_b.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 18px;")
        
        lbl_o = QLabel(f"Inkl. Planung: {val_opt}")
        lbl_o.setStyleSheet("color: #7F8C8D; font-size: 12px; font-style: italic;")
        
        layout.addWidget(lbl_t); layout.addWidget(lbl_b); layout.addWidget(lbl_o); layout.addStretch()

class InstitutsDashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        header_layout = QHBoxLayout()
        title = QLabel("Instituts-Leitung: Personal- & Liquiditäts-Forecast")
        title.setProperty("title", "true")
        header_layout.addWidget(title)
        
        btn_refresh = QPushButton("🔄 Daten aktualisieren")
        btn_refresh.setStyleSheet("background-color: #2980B9; color: white; padding: 6px; font-weight: bold;")
        btn_refresh.clicked.connect(self.load_data)
        header_layout.addStretch(); header_layout.addWidget(btn_refresh)
        
        main_layout.addLayout(header_layout)
        
        # --- KPI KACHELN ---
        self.kpi_layout = QHBoxLayout()
        main_layout.addLayout(self.kpi_layout)
        
        # --- TABELLE ---
        lbl_watch = QLabel("Projekt-Analyse (Personalbudgets x Wahrscheinlichkeit)")
        lbl_watch.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 15px;")
        main_layout.addWidget(lbl_watch)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Projekt", "Status", "Wahrsch.", "HR-Budget (Gewichtet)", 
            "HR-Rest (Aktuell)", "Finanzieller Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.table)

    def format_euro(self, value):
        return f"{value:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    def format_gap(self, value):
        if value < 0:
            return f"🟢 Überschuss: {abs(value):,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        elif value == 0:
            return "Ausgeglichen: 0 €"
        else:
            return f"🔴 Lücke: {value:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    def load_data(self):
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        session = get_session()
        try:
            data = generiere_instituts_controlling(session)
            
            # KPI 1: Runway Strikt
            rs_b = f"{data['runway_base_strict']:.1f} M" if data['runway_base_strict'] < 72 else "> 6 J"
            rs_o = f"{data['runway_opt_strict']:.1f} M" if data['runway_opt_strict'] < 72 else "> 6 J"
            color_rs = "#E74C3C" if data['runway_base_strict'] < 12 else "#27AE60"
            self.kpi_layout.addWidget(KPIFrame("HR-Runway (Strikt)", rs_b, rs_o, color_rs))
            
            # KPI 2: Runway Flex
            rf_b = f"{data['runway_base_flex']:.1f} M" if data['runway_base_flex'] < 72 else "> 6 J"
            rf_o = f"{data['runway_opt_flex']:.1f} M" if data['runway_opt_flex'] < 72 else "> 6 J"
            color_rf = "#E74C3C" if data['runway_base_flex'] < 12 else "#2980B9"
            self.kpi_layout.addWidget(KPIFrame("HR-Runway (20% Überziehen)", rf_b, rf_o, color_rf))
            
            # KPI 3: Lücke STRIKT
            ls_b = self.format_gap(data["gap_base_strict"])
            ls_o = self.format_gap(data["gap_opt_strict"])
            color_ls = "#E74C3C" if data["gap_base_strict"] > 0 else "#27AE60"
            self.kpi_layout.addWidget(KPIFrame("12M-Bilanz (Strikt)", ls_b, ls_o, color_ls))
            
            # KPI 4: Lücke FLEX
            lf_b = self.format_gap(data["gap_base_flex"])
            lf_o = self.format_gap(data["gap_opt_flex"])
            color_lf = "#E74C3C" if data["gap_base_flex"] > 0 else "#27AE60"
            self.kpi_layout.addWidget(KPIFrame("12M-Bilanz (20% Überziehen)", lf_b, lf_o, color_lf))
            
            # Tabelle befüllen
            self.table.setRowCount(0)
            for p in data["analysen"]:
                r = self.table.rowCount()
                self.table.insertRow(r)
                
                self.table.setItem(r, 0, QTableWidgetItem(p["name"]))
                self.table.setItem(r, 1, QTableWidgetItem(p["status"]))
                self.table.setItem(r, 2, QTableWidgetItem(f"{p['prob']*100:.0f}%"))
                self.table.setItem(r, 3, QTableWidgetItem(self.format_euro(p["hr_budget"])))
                
                item_rest = QTableWidgetItem(self.format_euro(p["hr_remaining"]))
                if p["hr_remaining"] < 0: 
                    item_rest.setForeground(QColor("red"))
                    font = QFont(); font.setBold(True); item_rest.setFont(font)
                self.table.setItem(r, 4, item_rest)
                self.table.setItem(r, 5, QTableWidgetItem(p["status_text"]))
                
            self.table.resizeRowsToContents()
        finally:
            session.close()