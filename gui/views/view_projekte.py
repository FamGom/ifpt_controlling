from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QLineEdit, QDateEdit, 
                             QComboBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
import datetime

from core.database import get_session
from core.models import Projekt, ProjektStatus, InstitutsKonto, OverheadRegel

class ProjektBearbeitenDialog(QDialog):
    def __init__(self, projekt_id=None, parent=None):
        super().__init__(parent)
        self.projekt_id = projekt_id
        self.setWindowTitle("Projekt bearbeiten" if projekt_id else "Neues Projekt anlegen")
        self.resize(600, 650)
        
        # 1. Standardwerte prüfen & laden
        self.lade_caches_und_standards()
        
        # 2. UI aufbauen
        self.setup_ui()
        
        # 3. Daten füllen
        if self.projekt_id:
            self.lade_projekt_daten()

    def lade_caches_und_standards(self):
        """Erzeugt automatisch Standard-Regeln, falls die Datenbank leer ist."""
        session = get_session()
        try:
            if session.query(OverheadRegel).count() == 0:
                session.add_all([
                    OverheadRegel(name="DFG Standard (22%)", gesamt_pct=22.0, institut_pct=12.0, verwaltung_pct=10.0),
                    OverheadRegel(name="BMBF Standard (20%)", gesamt_pct=20.0, institut_pct=12.0, verwaltung_pct=8.0),
                    OverheadRegel(name="Industrie / Keine (0%)", gesamt_pct=0.0, institut_pct=0.0, verwaltung_pct=0.0)
                ])
                session.commit()
                
            if session.query(InstitutsKonto).count() == 0:
                session.add_all([
                    InstitutsKonto(name="Zentrale Instituts-Rücklage"),
                    InstitutsKonto(name="Rücklage Berufungsmittel"),
                    InstitutsKonto(name="Freie Industrie-Rücklage")
                ])
                session.commit()
                
            self.regeln = session.query(OverheadRegel).order_by(OverheadRegel.id).all()
            self.konten = session.query(InstitutsKonto).order_by(InstitutsKonto.id).all()
        finally:
            session.close()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Basisdaten
        self.txt_name = QLineEdit()
        form.addRow("Projektname:", self.txt_name)

        self.combo_status = QComboBox()
        for status in ProjektStatus:
            self.combo_status.addItem(status.value, status)
        form.addRow("Status:", self.combo_status)
        
        # Pipeline-Gewichtung
        self.spin_wahrscheinlichkeit = QDoubleSpinBox()
        self.spin_wahrscheinlichkeit.setRange(0.0, 100.0)
        self.spin_wahrscheinlichkeit.setDecimals(1)
        self.spin_wahrscheinlichkeit.setSuffix(" %")
        self.spin_wahrscheinlichkeit.setValue(100.0)
        form.addRow("Bewilligungswahrscheinlichkeit:", self.spin_wahrscheinlichkeit)
        
        self.combo_status.currentIndexChanged.connect(self.auto_set_wahrscheinlichkeit)

        # Laufzeit
        self.date_beginn = QDateEdit()
        self.date_beginn.setCalendarPopup(True)
        self.date_beginn.setDate(QDate.currentDate())
        form.addRow("Projektbeginn:", self.date_beginn)

        self.date_ende = QDateEdit()
        self.date_ende.setCalendarPopup(True)
        self.date_ende.setDate(QDate.currentDate().addYears(3))
        form.addRow("Projektende:", self.date_ende)

        # Budgets
        self.spin_e13 = self._create_budget_spinbox()
        form.addRow("Budget E13-E15 (€):", self.spin_e13)
        self.spin_e1 = self._create_budget_spinbox()
        form.addRow("Budget E1-E12 (€):", self.spin_e1)
        self.spin_hiwi = self._create_budget_spinbox()
        form.addRow("Budget HiWi (€):", self.spin_hiwi)
        self.spin_sach = self._create_budget_spinbox()
        form.addRow("Budget Sachmittel (€):", self.spin_sach)
        
        # NEU: Overhead & Konten-Zuweisung
        form.addRow(QLabel("<b>Trennungsrechnung & Projektabschluss</b>"), None)
        
        self.combo_regel = QComboBox()
        self.combo_regel.addItem("Keine Regel", None)
        for r in self.regeln:
            self.combo_regel.addItem(f"{r.name} (Inst: {r.institut_pct}%)", r.id)
        form.addRow("Overhead-Regel:", self.combo_regel)
        
        self.combo_konto = QComboBox()
        self.combo_konto.addItem("Kein Zielkonto", None)
        for k in self.konten:
            self.combo_konto.addItem(k.name, k.id)
        form.addRow("Zielkonto (für Rücklagen):", self.combo_konto)
        
        self.spin_restmittel = QDoubleSpinBox()
        self.spin_restmittel.setRange(0.0, 100.0)
        self.spin_restmittel.setSuffix(" %")
        self.spin_restmittel.setToolTip("Wie viel Prozent des Restbudgets (ohne Overhead) dürfen bei Projektabschluss ins Institut überführt werden? (z.B. Industrie = 100%)")
        form.addRow("Verbleibende Restmittel für Institut:", self.spin_restmittel)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Speichern")
        btn_save.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        btn_save.clicked.connect(self.daten_speichern)
        
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _create_budget_spinbox(self):
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 99999999.0)
        spin.setDecimals(2)
        spin.setGroupSeparatorShown(True)
        return spin

    def auto_set_wahrscheinlichkeit(self):
        status = self.combo_status.currentData()
        if status == ProjektStatus.BEWILLIGT:
            self.spin_wahrscheinlichkeit.setValue(100.0)
        elif status == ProjektStatus.ABGELEHNT:
            self.spin_wahrscheinlichkeit.setValue(0.0)

    def lade_projekt_daten(self):
        session = get_session()
        try:
            p = session.query(Projekt).filter_by(id=self.projekt_id).first()
            if not p: return

            self.txt_name.setText(p.projektname)
            
            idx = self.combo_status.findData(p.status)
            if idx >= 0: self.combo_status.setCurrentIndex(idx)
                
            prob = getattr(p, "bewilligungswahrscheinlichkeit_pct", 100.0)
            self.spin_wahrscheinlichkeit.setValue(prob if prob is not None else 100.0)

            if p.projektbeginn:
                self.date_beginn.setDate(QDate(p.projektbeginn.year, p.projektbeginn.month, p.projektbeginn.day))
            if p.projektende:
                self.date_ende.setDate(QDate(p.projektende.year, p.projektende.month, p.projektende.day))

            self.spin_e13.setValue(p.personalbudget_e13_e15 or 0.0)
            self.spin_e1.setValue(p.personalbudget_e1_e12 or 0.0)
            self.spin_hiwi.setValue(p.personalbudget_besch_entgelt or 0.0)
            self.spin_sach.setValue(p.sachmittelbudget or 0.0)
            
            if getattr(p, "overhead_regel_id", None):
                idx_r = self.combo_regel.findData(p.overhead_regel_id)
                if idx_r >= 0: self.combo_regel.setCurrentIndex(idx_r)
                
            if getattr(p, "ziel_konto_id", None):
                idx_k = self.combo_konto.findData(p.ziel_konto_id)
                if idx_k >= 0: self.combo_konto.setCurrentIndex(idx_k)
                
            self.spin_restmittel.setValue(getattr(p, "restmittel_institut_pct", 0.0) or 0.0)

        finally:
            session.close()

    def daten_speichern(self):
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Fehler", "Der Projektname darf nicht leer sein.")
            return

        session = get_session()
        try:
            if self.projekt_id:
                p = session.query(Projekt).filter_by(id=self.projekt_id).first()
            else:
                p = Projekt()
                session.add(p)

            p.projektname = name
            p.status = self.combo_status.currentData()
            p.bewilligungswahrscheinlichkeit_pct = self.spin_wahrscheinlichkeit.value()
            p.projektbeginn = self.date_beginn.date().toPyDate()
            p.projektende = self.date_ende.date().toPyDate()

            p.personalbudget_e13_e15 = self.spin_e13.value()
            p.personalbudget_e1_e12 = self.spin_e1.value()
            p.personalbudget_besch_entgelt = self.spin_hiwi.value()
            p.sachmittelbudget = self.spin_sach.value()
            
            p.overhead_regel_id = self.combo_regel.currentData()
            p.ziel_konto_id = self.combo_konto.currentData()
            p.restmittel_institut_pct = self.spin_restmittel.value()

            if p.status == ProjektStatus.BEENDET:
                from core.calculations import schliesse_projekt_ab
                # Wir müssen erst flushen, damit die DB den aktuellen Status kennt
                session.flush() 
                schliesse_projekt_ab(session, p.id)
                        
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", str(e))
        finally:
            session.close()

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
        self.spalten = ["ID", "Projektname", "Status", "Chance", "Laufzeit", "Budget (Personal)", "Sachmittel", "Overhead & Konto"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.projekt_bearbeiten)
        
        main_layout.addWidget(self.table)

    def format_euro(self, val):
        if val == 0: return "-"
        return f"{val:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")

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
                
                regel_text = f"{p.overhead_pct}% (Keine Regel)"
                if getattr(p, "overhead_regel_id", None) and p.overhead_regel:
                    regel_text = f"{p.overhead_regel.name}"
                    if getattr(p, "ziel_konto_id", None) and p.ziel_konto:
                        regel_text += f"\n-> {p.ziel_konto.name}"
                
                self.table.setItem(row, 7, QTableWidgetItem(regel_text))
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
        
        reply = QMessageBox.question(self, 'Löschen bestätigen', 
                                     f'Soll das Projekt "{name}" wirklich gelöscht werden?\nAchtung: Das löscht auch alle Zuweisungen und Ausgaben!',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                projekt = session.query(Projekt).filter_by(id=p_id).first()
                if projekt:
                    session.delete(projekt)
                    session.commit()
                    self.load_projekte()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Fehler", f"Das Projekt konnte nicht gelöscht werden.\n\nDetails:\n{str(e)}")
            finally:
                session.close()