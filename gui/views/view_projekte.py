from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QLineEdit, 
                             QDateEdit, QDoubleSpinBox, QDialogButtonBox, QComboBox)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models import Projekt, ProjektStatus, Abrechnungsart

class ProjektBearbeitenDialog(QDialog):
    def __init__(self, projekt_id=None, parent=None):
        super().__init__(parent)
        self.projekt_id = projekt_id
        
        titel = "Projekt bearbeiten" if projekt_id else "Neues Projekt anlegen"
        self.setWindowTitle(titel)
        self.resize(500, 600)
        
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setVerticalSpacing(12)
        
        self.txt_name = QLineEdit()
        layout.addRow("Projektname:", self.txt_name)
        
        self.combo_status = QComboBox()
        for s in ProjektStatus:
            self.combo_status.addItem(s.value, s)
        layout.addRow("Projekt-Status:", self.combo_status)

        self.spin_wahrscheinlichkeit = QDoubleSpinBox()
        self.spin_wahrscheinlichkeit.setRange(0.0, 100.0)
        self.spin_wahrscheinlichkeit.setDecimals(1)
        self.spin_wahrscheinlichkeit.setSuffix(" %")
        layout.addRow("Bewilligungswahrscheinlichkeit:", self.spin_wahrscheinlichkeit)
        
        # Komfort-Automatik: Status ändert Wahrscheinlichkeit
        self.combo_status.currentIndexChanged.connect(self.auto_set_wahrscheinlichkeit)
        
        self.combo_abrechnung = QComboBox()
        for a in Abrechnungsart:
            self.combo_abrechnung.addItem(a.value, a)
        layout.addRow("Abrechnungsart:", self.combo_abrechnung)
        
        self.spin_overhead = QDoubleSpinBox()
        self.spin_overhead.setRange(0.0, 100.0)
        self.spin_overhead.setSuffix(" %")
        layout.addRow("Overhead (Gemeinkosten):", self.spin_overhead)
        
        self.date_start = QDateEdit()
        self.date_start.setDate(QDate.currentDate())
        self.date_start.setCalendarPopup(True)
        layout.addRow("Projektbeginn:", self.date_start)
        
        self.date_ende = QDateEdit()
        self.date_ende.setDate(QDate.currentDate().addYears(3))
        self.date_ende.setCalendarPopup(True)
        layout.addRow("Projektende:", self.date_ende)
        
        sep_budget = QLabel("<b>Personal- & Sachmittelbudgets</b>")
        sep_budget.setStyleSheet("margin-top: 10px; color: #2980B9;")
        layout.addRow(sep_budget)
        
        self.spin_bud_e1_e12 = QDoubleSpinBox()
        self.setup_spinbox(self.spin_bud_e1_e12)
        layout.addRow("Budget E1-E12:", self.spin_bud_e1_e12)
        
        self.spin_bud_e13_e15 = QDoubleSpinBox()
        self.setup_spinbox(self.spin_bud_e13_e15)
        layout.addRow("Budget E13-E15:", self.spin_bud_e13_e15)
        
        self.spin_bud_besch = QDoubleSpinBox()
        self.setup_spinbox(self.spin_bud_besch)
        layout.addRow("Beschäftigtenentgelt:", self.spin_bud_besch)
        
        self.spin_bud_sach = QDoubleSpinBox()
        self.setup_spinbox(self.spin_bud_sach)
        layout.addRow("Sachmittelbudget:", self.spin_bud_sach)

        sep_ende = QLabel("<b>Kaufmännischer Projektabschluss</b>")
        sep_ende.setStyleSheet("margin-top: 10px; color: #2980B9;")
        layout.addRow(sep_ende)

        self.spin_rueckzahlung = QDoubleSpinBox()
        self.setup_spinbox(self.spin_rueckzahlung)
        layout.addRow("Nachträgliche Rückzahlung / Beanstandung:", self.spin_rueckzahlung)

        self.combo_verbleib = QComboBox()
        self.combo_verbleib.addItems([
            "Rückzahlung an Zuwendungsgeber",
            "Verfallen (Standard)",
            "Ausnahmsweise übertragen"
        ])
        layout.addRow("Verbleib der Restmittel am Ende:", self.combo_verbleib)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.daten_speichern)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        if self.projekt_id:
            self.lade_projekt_daten()

    def setup_spinbox(self, spinbox):
        spinbox.setRange(0.0, 99999999.0)
        spinbox.setSingleStep(1000.0)
        spinbox.setSuffix(" €")
        spinbox.setGroupSeparatorShown(True)

    def lade_projekt_daten(self):
        session = get_session()
        try:
            p = session.query(Projekt).filter_by(id=self.projekt_id).first()
            if p:
                self.txt_name.setText(p.projektname)
                
                idx_s = self.combo_status.findData(p.status)
                if idx_s >= 0: self.combo_status.setCurrentIndex(idx_s)
                
                idx_a = self.combo_abrechnung.findData(p.abrechnungsart)
                if idx_a >= 0: self.combo_abrechnung.setCurrentIndex(idx_a)
                
                self.spin_overhead.setValue(p.overhead_pct)
                
                self.date_start.setDate(QDate(p.projektbeginn.year, p.projektbeginn.month, p.projektbeginn.day))
                self.date_ende.setDate(QDate(p.projektende.year, p.projektende.month, p.projektende.day))
                
                self.spin_bud_e1_e12.setValue(p.personalbudget_e1_e12 or 0.0)
                self.spin_bud_e13_e15.setValue(p.personalbudget_e13_e15 or 0.0)
                self.spin_bud_besch.setValue(p.personalbudget_besch_entgelt or 0.0)
                self.spin_bud_sach.setValue(p.sachmittelbudget or 0.0)

                self.spin_rueckzahlung.setValue(getattr(p, "tatsaechliche_rueckzahlung", 0.0) or 0.0)
                verbleib = getattr(p, "restmittel_verbleib_typ", "Rückzahlung an Zuwendungsgeber")
                idx_v = self.combo_verbleib.findText(verbleib)
                if idx_v >= 0: self.combo_verbleib.setCurrentIndex(idx_v)

                # Beim Laden auslesen (Harter Absturz-Schutz, falls None)
                prob = getattr(p, "bewilligungswahrscheinlichkeit_pct", 100.0)
                if prob is None: prob = 100.0
                self.spin_wahrscheinlichkeit.setValue(prob)
        finally:
            session.close()

    def daten_speichern(self):
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Fehler", "Bitte einen Projektnamen eingeben.")
            return
            
        session = get_session()
        try:
            if self.projekt_id:
                p = session.query(Projekt).filter_by(id=self.projekt_id).first()
            else:
                p = Projekt()
                session.add(p)
                
            p.projektname = self.txt_name.text().strip()
            p.status = self.combo_status.currentData()
            p.abrechnungsart = self.combo_abrechnung.currentData()
            p.overhead_pct = self.spin_overhead.value()
            p.projektbeginn = self.date_start.date().toPyDate()
            p.projektende = self.date_ende.date().toPyDate()
            
            p.personalbudget_e1_e12 = self.spin_bud_e1_e12.value()
            p.personalbudget_e13_e15 = self.spin_bud_e13_e15.value()
            p.personalbudget_besch_entgelt = self.spin_bud_besch.value()
            p.sachmittelbudget = self.spin_bud_sach.value()
            
            p.tatsaechliche_rueckzahlung = self.spin_rueckzahlung.value()
            p.restmittel_verbleib_typ = self.combo_verbleib.currentText()
            p.bewilligungswahrscheinlichkeit_pct = self.spin_wahrscheinlichkeit.value()
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", f"Konnte Projekt nicht speichern:\n{str(e)}")
        finally:
            session.close()

    def auto_set_wahrscheinlichkeit(self):  
        status = self.combo_status.currentData()
        if status == ProjektStatus.BEWILLIGT:
            self.spin_wahrscheinlichkeit.setValue(100.0)
        elif status == ProjektStatus.ABGELEHNT:
            self.spin_wahrscheinlichkeit.setValue(0.0)
        elif status == ProjektStatus.BEANTRAGT:
            self.spin_wahrscheinlichkeit.setValue(50.0)
        else:
            self.spin_wahrscheinlichkeit.setValue(100.0)  # Default

class ProjekteView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_projekte()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        title = QLabel("Projekt- & Budgetverwaltung")
        title.setProperty("title", "true")
        main_layout.addWidget(title)
        
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neues Projekt")
        btn_add.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self.projekt_hinzufuegen)
        
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.setStyleSheet("background-color: #2980B9; color: white; padding: 6px;")
        btn_edit.clicked.connect(self.projekt_bearbeiten)
        
        btn_del = QPushButton("🗑️ Löschen")
        btn_del.setStyleSheet("background-color: #C0392B; color: white; padding: 6px;")
        btn_del.clicked.connect(self.projekt_loeschen)
        
        btn_refresh = QPushButton("🔄 Aktualisieren")
        btn_refresh.clicked.connect(self.load_projekte)
        
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_del)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        main_layout.addLayout(toolbar)
        
        self.table = QTableWidget()
        # NEU: Spalte "Chance" eingefügt
        self.spalten = ["ID", "Projektname", "Status", "Chance", "Laufzeit", "Budget (Personal)", "Sachmittel", "Overhead"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.projekt_bearbeiten)
        
        main_layout.addWidget(self.table)

    def format_euro(self, amount):
        return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


    def load_projekte(self):
        session = get_session()
        self.table.setRowCount(0)
        try:
            projekte_liste = session.query(Projekt).order_by(Projekt.projektbeginn.desc()).all()
            for p in projekte_liste:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                self.table.setItem(row, 0, QTableWidgetItem(str(p.id)))
                self.table.setItem(row, 1, QTableWidgetItem(p.projektname))
                
                status_item = QTableWidgetItem(p.status.value if p.status else "-")
                if p.status == ProjektStatus.BEWILLIGT:
                    status_item.setForeground(Qt.GlobalColor.green)
                elif p.status == ProjektStatus.ABGELEHNT:
                    status_item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(row, 2, status_item)
                
                # NEU: Wahrscheinlichkeit anzeigen
                prob = getattr(p, "bewilligungswahrscheinlichkeit_pct", 100.0)
                if prob is None: prob = 100.0
                prob_item = QTableWidgetItem(f"{prob:.0f} %")
                prob_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if prob < 100.0: prob_item.setForeground(QColor("#8E44AD"))
                self.table.setItem(row, 3, prob_item)
                
                laufzeit = f"{p.projektbeginn.strftime('%m/%Y')} - {p.projektende.strftime('%m/%Y')}"
                self.table.setItem(row, 4, QTableWidgetItem(laufzeit))
                
                pers_bud = (p.personalbudget_e1_e12 or 0) + (p.personalbudget_e13_e15 or 0) + (p.personalbudget_besch_entgelt or 0)
                self.table.setItem(row, 5, QTableWidgetItem(self.format_euro(pers_bud)))
                self.table.setItem(row, 6, QTableWidgetItem(self.format_euro(p.sachmittelbudget or 0)))
                self.table.setItem(row, 7, QTableWidgetItem(f"{p.overhead_pct} %"))
        finally:
            session.close()

    def projekt_hinzufuegen(self):
        dialog = ProjektBearbeitenDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_projekte()

    def projekt_bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        p_id = int(self.table.item(row, 0).text())
        dialog = ProjektBearbeitenDialog(projekt_id=p_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_projekte()

    def projekt_loeschen(self):
        row = self.table.currentRow()
        if row < 0: return
        p_id = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()
        antwort = QMessageBox.question(self, "Löschen bestätigen", 
            f"Möchten Sie das Projekt '{name}' und alle zugehörigen Personal-Zuweisungen wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if antwort == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                p = session.query(Projekt).filter_by(id=p_id).first()
                if p:
                    session.delete(p)
                    session.commit()
                    self.load_projekte()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Fehler", f"Fehler beim Löschen:\n{str(e)}")
            finally:
                session.close()