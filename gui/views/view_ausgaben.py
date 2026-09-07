from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QLineEdit, 
                             QDateEdit, QDoubleSpinBox, QDialogButtonBox, QComboBox, QSplitter)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models import (AusgabeKopf, AusgabePosition, Kostenart, AusgabenStatus, 
                         Projekt, ProjektStatus, Mitarbeiter)

class AusgabeBearbeitenDialog(QDialog):
    def __init__(self, kopf_id=None, copy_from_plan=False, parent=None):
        super().__init__(parent)
        self.kopf_id = kopf_id
        self.copy_from_plan = copy_from_plan
        self.projekte_cache = []
        self.mitarbeiter_cache = []
        
        titel = "Bestellung / Rechnung bearbeiten" if kopf_id and not copy_from_plan else "Neue Ausgabe / Plan-Budget erfassen"
        self.setWindowTitle(titel)
        self.resize(1000, 700)
        
        self.lade_caches()
        self.setup_ui()
        
        if self.kopf_id:
            self.lade_daten()
        else:
            self.add_position_row() # Eine leere Zeile zum Start

    def lade_caches(self):
        session = get_session()
        try:
            self.projekte_cache = session.query(Projekt).order_by(Projekt.projektname).all()
            self.mitarbeiter_cache = session.query(Mitarbeiter).order_by(Mitarbeiter.nachname).all()
        finally:
            session.close()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # --- KOPFDATEN ---
        widget_kopf = QWidget()
        layout_kopf = QFormLayout(widget_kopf)
        
        self.txt_titel = QLineEdit()
        layout_kopf.addRow("Titel / Verwendungszweck:", self.txt_titel)
        
        self.combo_status = QComboBox()
        for s in AusgabenStatus:
            self.combo_status.addItem(s.value, s)
        layout_kopf.addRow("Status:", self.combo_status)
        
        self.txt_lieferant = QLineEdit()
        layout_kopf.addRow("Lieferant / Kreditor:", self.txt_lieferant)
        
        self.txt_rechnung = QLineEdit()
        layout_kopf.addRow("Rechnungsnummer:", self.txt_rechnung)
        
        row_dates = QHBoxLayout()
        self.date_bestell = QDateEdit(); self.date_bestell.setCalendarPopup(True); self.date_bestell.setDate(QDate.currentDate())
        self.date_rech = QDateEdit(); self.date_rech.setCalendarPopup(True); self.date_rech.setSpecialValueText(" - ")
        self.date_rech.setDate(QDate(2099, 12, 31))
        row_dates.addWidget(QLabel("Bestelldatum:")); row_dates.addWidget(self.date_bestell)
        row_dates.addWidget(QLabel("   Rechnungsdatum:")); row_dates.addWidget(self.date_rech)
        layout_kopf.addRow("Daten:", row_dates)
        
        self.combo_ma = QComboBox()
        self.combo_ma.addItem("Kein spezifischer Mitarbeiter (Standard)", None)
        for m in self.mitarbeiter_cache:
            self.combo_ma.addItem(f"{m.nachname}, {m.vorname}", m.id)
        layout_kopf.addRow("Reisender / Begünstigter (Optional):", self.combo_ma)
        
        splitter.addWidget(widget_kopf)
        
        # --- POSITIONEN ---
        widget_pos = QWidget()
        layout_pos = QVBoxLayout(widget_pos)
        layout_pos.addWidget(QLabel("<b>Bestell-Positionen (Splitt-Buchungen möglich)</b>"))
        
        self.table_pos = QTableWidget()
        self.spalten = ["Projekt", "Kostenart (Kategorie)", "Bezeichnung", "Betrag (€)", "Lfd.Nr. (Invest)"]
        self.table_pos.setColumnCount(len(self.spalten))
        self.table_pos.setHorizontalHeaderLabels(self.spalten)
        self.table_pos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_pos.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout_pos.addWidget(self.table_pos)
        
        toolbar_pos = QHBoxLayout()
        btn_add = QPushButton("➕ Position hinzufügen")
        btn_add.clicked.connect(self.add_position_row)
        btn_del = QPushButton("🗑️ Zeile löschen")
        btn_del.clicked.connect(lambda: self.table_pos.removeRow(self.table_pos.currentRow()) if self.table_pos.currentRow() >= 0 else None)
        toolbar_pos.addWidget(btn_add); toolbar_pos.addWidget(btn_del); toolbar_pos.addStretch()
        layout_pos.addLayout(toolbar_pos)
        
        splitter.addWidget(widget_pos)
        splitter.setSizes([300, 400])
        main_layout.addWidget(splitter)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.daten_speichern)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def add_position_row(self, proj_id=None, kostenart=None, bez="", betrag=0.0, invest_nr=""):
        row = self.table_pos.rowCount()
        self.table_pos.insertRow(row)
        
        c_proj = QComboBox()
        for p in self.projekte_cache: c_proj.addItem(p.projektname, p.id)
        if proj_id: c_proj.setCurrentIndex(c_proj.findData(proj_id))
        self.table_pos.setCellWidget(row, 0, c_proj)
        
        c_art = QComboBox()
        for a in Kostenart: c_art.addItem(a.value, a)
        if kostenart: c_art.setCurrentIndex(c_art.findData(kostenart))
        self.table_pos.setCellWidget(row, 1, c_art)
        
        txt_bez = QLineEdit(bez)
        self.table_pos.setCellWidget(row, 2, txt_bez)
        
        spin_betrag = QDoubleSpinBox()
        spin_betrag.setRange(-999999.0, 999999.0)
        spin_betrag.setDecimals(2)
        spin_betrag.setGroupSeparatorShown(True)
        spin_betrag.setSuffix(" €")
        spin_betrag.setValue(betrag)
        self.table_pos.setCellWidget(row, 3, spin_betrag)
        
        txt_inv = QLineEdit(invest_nr if invest_nr else "")
        txt_inv.setPlaceholderText("Nur bei >800€")
        self.table_pos.setCellWidget(row, 4, txt_inv)

    def lade_daten(self):
        session = get_session()
        try:
            kopf = session.query(AusgabeKopf).filter_by(id=self.kopf_id).first()
            if not kopf: return
            
            self.txt_titel.setText(kopf.titel)
            self.txt_lieferant.setText(kopf.lieferant or "")
            self.txt_rechnung.setText(kopf.rechnungsnummer or "")
            
            if kopf.bestelldatum: self.date_bestell.setDate(QDate(kopf.bestelldatum.year, kopf.bestelldatum.month, kopf.bestelldatum.day))
            if kopf.rechnungsdatum: self.date_rech.setDate(QDate(kopf.rechnungsdatum.year, kopf.rechnungsdatum.month, kopf.rechnungsdatum.day))
            
            idx_s = self.combo_status.findData(kopf.status)
            if idx_s >= 0: self.combo_status.setCurrentIndex(idx_s)
            
            if kopf.beguenstigter_mitarbeiter_id:
                idx_m = self.combo_ma.findData(kopf.beguenstigter_mitarbeiter_id)
                if idx_m >= 0: self.combo_ma.setCurrentIndex(idx_m)
                
            # Bei Plan-Übernahme setzen wir den Status direkt auf Bestellt
            if self.copy_from_plan:
                idx_b = self.combo_status.findData(AusgabenStatus.BESTELLT)
                if idx_b >= 0: self.combo_status.setCurrentIndex(idx_b)
                self.txt_titel.setText(f"{kopf.titel} (Kopie aus Plan)")

            for pos in kopf.positionen:
                self.add_position_row(pos.projekt_id, pos.kostenart, pos.bezeichnung, pos.betrag_euro, pos.lfd_nr_invest)
        finally:
            session.close()

    def daten_speichern(self):
        if not self.txt_titel.text().strip():
            QMessageBox.warning(self, "Fehler", "Bitte einen Verwendungszweck eingeben.")
            return
            
        session = get_session()
        try:
            if self.kopf_id and not self.copy_from_plan:
                kopf = session.query(AusgabeKopf).filter_by(id=self.kopf_id).first()
                session.query(AusgabePosition).filter_by(kopf_id=kopf.id).delete() # Hard-Reset der Positionen
            else:
                kopf = AusgabeKopf()
                session.add(kopf)
                
            kopf.titel = self.txt_titel.text().strip()
            kopf.status = self.combo_status.currentData()
            kopf.lieferant = self.txt_lieferant.text().strip()
            kopf.rechnungsnummer = self.txt_rechnung.text().strip()
            kopf.bestelldatum = self.date_bestell.date().toPyDate()
            
            r_date = self.date_rech.date().toPyDate()
            kopf.rechnungsdatum = None if r_date.year == 2099 else r_date
            kopf.beguenstigter_mitarbeiter_id = self.combo_ma.currentData()
            
            for r in range(self.table_pos.rowCount()):
                p_id = self.table_pos.cellWidget(r, 0).currentData()
                k_art = self.table_pos.cellWidget(r, 1).currentData()
                bez = self.table_pos.cellWidget(r, 2).text().strip()
                betrag = self.table_pos.cellWidget(r, 3).value()
                inv_nr = self.table_pos.cellWidget(r, 4).text().strip()
                
                if p_id and k_art and betrag != 0:
                    pos = AusgabePosition(
                        kopf=kopf, projekt_id=p_id, kostenart=k_art, 
                        bezeichnung=bez if bez else kopf.titel, 
                        betrag_euro=betrag, lfd_nr_invest=inv_nr
                    )
                    session.add(pos)
                    
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", str(e))
        finally:
            session.close()

class AusgabenView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_data()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Ausgaben-Journal (Sachmittel & Rechnungen)")
        title.setProperty("title", "true")
        layout.addWidget(title)
        
        info = QLabel("Erfassen Sie hier alle kaufmännischen Bestellungen, Reisekosten und HiWi-Verträge, damit diese korrekt aus dem Projektbudget (Burn-Down) abfließen.")
        info.setStyleSheet("color: #7F8C8D; margin-bottom: 10px;")
        layout.addWidget(info)
        
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neue freie Ausgabe")
        btn_add.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self.neu_frei)
        
        btn_plan = QPushButton("🎯 Aus Plan-Budget bestellen")
        btn_plan.setStyleSheet("background-color: #8E44AD; color: white; font-weight: bold; padding: 6px;")
        btn_plan.clicked.connect(self.neu_aus_plan)
        
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.clicked.connect(self.bearbeiten)
        
        btn_del = QPushButton("🗑️ Löschen")
        btn_del.clicked.connect(self.loeschen)
        
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_plan); toolbar.addSpacing(20)
        toolbar.addWidget(btn_edit); toolbar.addWidget(btn_del); toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.table = QTableWidget()
        self.spalten = ["ID", "Status", "Titel / Zweck", "Datum", "Lieferant / MA", "Kostenarten (Auszug)", "Gesamtbetrag"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.bearbeiten)
        layout.addWidget(self.table)

    def load_data(self):
        session = get_session()
        self.table.setRowCount(0)
        try:
            koepfe = session.query(AusgabeKopf).order_by(AusgabeKopf.bestelldatum.desc()).all()
            for k in koepfe:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                self.table.setItem(row, 0, QTableWidgetItem(str(k.id)))
                
                status_item = QTableWidgetItem(k.status.value)
                if k.status == AusgabenStatus.PLAN: status_item.setForeground(QColor("#8E44AD"))
                elif k.status == AusgabenStatus.BESTELLT: status_item.setForeground(QColor("#F39C12"))
                elif k.status == AusgabenStatus.BEZAHLT: status_item.setForeground(QColor("#27AE60"))
                self.table.setItem(row, 1, status_item)
                
                self.table.setItem(row, 2, QTableWidgetItem(k.titel))
                
                d_str = k.bestelldatum.strftime('%d.%m.%Y') if k.bestelldatum else "-"
                self.table.setItem(row, 3, QTableWidgetItem(d_str))
                
                partner = k.lieferant or ""
                if k.beguenstigter_mitarbeiter_id and k.mitarbeiter:
                    partner = f"MA: {k.mitarbeiter.nachname}"
                self.table.setItem(row, 4, QTableWidgetItem(partner))
                
                arten = list(set([pos.kostenart.value.split(" - ")[0] for pos in k.positionen]))
                self.table.setItem(row, 5, QTableWidgetItem(", ".join(arten)))
                
                summe = sum([pos.betrag_euro for pos in k.positionen])
                sum_item = QTableWidgetItem(f"{summe:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
                sum_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 6, sum_item)
        finally:
            session.close()

    def neu_frei(self):
        if AusgabeBearbeitenDialog(parent=self).exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def neu_aus_plan(self):
        """Lässt den Nutzer einen Plan-Datensatz wählen und übernimmt ihn als echte Bestellung."""
        session = get_session()
        try:
            plaene = session.query(AusgabeKopf).filter_by(status=AusgabenStatus.PLAN).all()
            if not plaene:
                QMessageBox.information(self, "Leer", "Es gibt aktuell keine offenen Plan-Budgets im System.")
                return
        finally:
            session.close()
            
        # Wir nutzen einfach die Tabelle, der Nutzer soll einen Plan anklicken.
        row = self.table.currentRow()
        if row >= 0 and self.table.item(row, 1).text() == AusgabenStatus.PLAN.value:
            k_id = int(self.table.item(row, 0).text())
            if AusgabeBearbeitenDialog(kopf_id=k_id, copy_from_plan=True, parent=self).exec() == QDialog.DialogCode.Accepted:
                self.load_data()
        else:
            QMessageBox.information(self, "Hinweis", "Bitte markieren Sie zuerst eine Zeile mit Status 'Plan-Budget' in der Liste.")

    def bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        k_id = int(self.table.item(row, 0).text())
        if AusgabeBearbeitenDialog(kopf_id=k_id, parent=self).exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def loeschen(self):
        row = self.table.currentRow()
        if row < 0: return
        k_id = int(self.table.item(row, 0).text())
        titel = self.table.item(row, 2).text()
        
        if QMessageBox.question(self, "Löschen", f"Ausgabe '{titel}' samt aller Positionen unwiderruflich löschen?", 
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                kopf = session.query(AusgabeKopf).filter_by(id=k_id).first()
                if kopf: session.delete(kopf); session.commit(); self.load_data()
            finally:
                session.close()