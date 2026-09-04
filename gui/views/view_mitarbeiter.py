from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QLineEdit, 
                             QDateEdit, QSpinBox, QDoubleSpinBox, QDialogButtonBox, 
                             QComboBox, QFileDialog, QTabWidget)
from PyQt6.QtCore import Qt, QDate, QRectF, QMarginsF
from PyQt6.QtGui import (QColor, QPdfWriter, QTextDocument, QPageLayout, 
                         QPageSize, QPainter, QAbstractTextDocumentLayout, QFont, QPen)

from core.database import get_session
from core.models import Mitarbeiter, Gehaltsverlauf, Sonderzahlung, Arbeitszeitverlauf, KVZusatzVerlauf
from utils.theme import get_pdf_css

class GehaltSchrittDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stufensprung / Gehaltsverlauf hinzufügen")
        self.resize(350, 250)
        
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.combo_eg = QComboBox()
        self.combo_eg.addItems([f"E{i}" for i in range(1, 16)])
        self.combo_eg.setCurrentText("E13")
        layout.addRow("Entgeltgruppe:", self.combo_eg)
        
        self.combo_stufe = QComboBox()
        self.combo_stufe.addItems([str(i) for i in range(1, 7)])
        layout.addRow("Stufe:", self.combo_stufe)
        
        self.date_ab = QDateEdit()
        self.date_ab.setDate(QDate.currentDate())
        self.date_ab.setCalendarPopup(True)
        layout.addRow("Gültig ab:", self.date_ab)
        
        self.date_bis = QDateEdit()
        self.date_bis.setDate(QDate(2099, 12, 31))
        self.date_bis.setCalendarPopup(True)
        layout.addRow("Gültig bis (optional):", self.date_bis)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return {
            "entgeltgruppe": self.combo_eg.currentText(),
            "stufe": self.combo_stufe.currentText(),
            "gueltig_ab": self.date_ab.date().toPyDate(),
            "gueltig_bis": self.date_bis.date().toPyDate()
        }

class MitarbeiterBearbeitenDialog(QDialog):
    def __init__(self, mitarbeiter_id=None, parent=None):
        super().__init__(parent)
        self.mitarbeiter_id = mitarbeiter_id
        self.setWindowTitle("Mitarbeiter bearbeiten" if mitarbeiter_id else "Neuen Mitarbeiter anlegen")
        self.resize(650, 550)
        
        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        self.tab_stamm = QWidget()
        self.tab_gehalt = QWidget()
        self.tab_arbeitszeit = QWidget()
        self.tab_kv = QWidget() # NEU
        
        self.tabs.addTab(self.tab_stamm, "👤 Stammdaten")
        self.tabs.addTab(self.tab_gehalt, "💶 TV-L Gehaltsverlauf")
        self.tabs.addTab(self.tab_arbeitszeit, "⏱️ Arbeitszeit & Teilzeit")
        self.tabs.addTab(self.tab_kv, "🏥 KV-Zusatz") # NEU
        
        self.setup_stamm_tab()
        self.setup_gehalt_tab()
        self.setup_arbeitszeit_tab()
        self.setup_kv_tab()
        
        buttons = QHBoxLayout()
        btn_save = QPushButton("💾 Speichern")
        btn_save.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 8px;")
        btn_save.clicked.connect(self.daten_speichern)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_save)
        self.layout.addLayout(buttons)
        
        if self.mitarbeiter_id:
            self.lade_daten()
        else:
            self.generiere_tvl_laufbahn()
            self.add_az_row(pct=100.0)
            self.add_kv_row(pct=1.7) # Standard KV-Zusatz bei neuen MA

    def setup_stamm_tab(self):
        layout = QFormLayout(self.tab_stamm)
        layout.setVerticalSpacing(8)
        
        self.txt_vorname = QLineEdit()
        self.txt_nachname = QLineEdit()
        self.date_geburt = QDateEdit()
        self.date_geburt.setDate(QDate(1990, 1, 1))
        self.date_geburt.setCalendarPopup(True)
        self.date_ifpt_seit = QDateEdit()
        self.date_ifpt_seit.setDate(QDate.currentDate())
        self.date_ifpt_seit.setCalendarPopup(True)
        self.date_abgang = QDateEdit()
        self.date_abgang.setDate(QDate(2099, 12, 31))
        self.date_abgang.setCalendarPopup(True)
        
        self.spin_kinder = QSpinBox()
        self.spin_kinder.setRange(0, 10)
        self.spin_vl = QDoubleSpinBox()
        self.spin_vl.setRange(0.0, 500.0)
        self.spin_vl.setSingleStep(0.5)
        self.spin_vl.setValue(6.65)
        self.spin_vl.setSuffix(" €")
        
        layout.addRow("Vorname:", self.txt_vorname)
        layout.addRow("Nachname:", self.txt_nachname)
        layout.addRow("Geburtsdatum:", self.date_geburt)
        layout.addRow("Am IFPT seit:", self.date_ifpt_seit)
        layout.addRow("Geplanter Abgang:", self.date_abgang)
        layout.addRow(QLabel(""))
        layout.addRow(QLabel("<b>Individuelle Parameter</b>"))
        layout.addRow("Anzahl Kinder (für PV):", self.spin_kinder)
        layout.addRow("VWL (AG-Anteil mtl.):", self.spin_vl)
        # KV Spinbox ist hier weg, da es nun einen eigenen Tab hat!

    def setup_gehalt_tab(self):
        layout = QVBoxLayout(self.tab_gehalt)
        btn_magic = QPushButton("✨ Automatische TV-L Stufenlaufbahn generieren")
        btn_magic.setStyleSheet("background-color: #8E44AD; color: white; padding: 5px;")
        btn_magic.clicked.connect(self.generiere_tvl_laufbahn)
        layout.addWidget(btn_magic)
        
        self.table_gehalt = QTableWidget()
        self.table_gehalt.setColumnCount(4)
        self.table_gehalt.setHorizontalHeaderLabels(["Gültig ab", "Gültig bis", "Entgeltgruppe", "Stufe"])
        self.table_gehalt.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_gehalt)
        
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Manuell hinzufügen"); btn_add.clicked.connect(self.gehaltsschritt_hinzufuegen)
        btn_del = QPushButton("🗑️ Zeile löschen"); btn_del.clicked.connect(self.gehaltsschritt_loeschen)
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_del); toolbar.addStretch()
        layout.addLayout(toolbar)

    def setup_arbeitszeit_tab(self):
        layout = QVBoxLayout(self.tab_arbeitszeit)
        info = QLabel("Definieren Sie hier, wann der Mitarbeiter zu wie viel Prozent arbeitet.")
        info.setStyleSheet("color: #7F8C8D;")
        layout.addWidget(info)
        
        self.table_az = QTableWidget()
        self.table_az.setColumnCount(3)
        self.table_az.setHorizontalHeaderLabels(["Gültig ab", "Gültig bis", "Arbeitszeit (%)"])
        self.table_az.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_az)
        
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Eintrag hinzufügen"); btn_add.clicked.connect(self.add_az_row)
        btn_del = QPushButton("🗑️ Zeile löschen"); btn_del.clicked.connect(self.del_az_row)
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_del); toolbar.addStretch()
        layout.addLayout(toolbar)

    # NEU: Setup KV Tab
    def setup_kv_tab(self):
        layout = QVBoxLayout(self.tab_kv)
        info = QLabel("Gesamter kassenindividueller Zusatzbeitrag (AG + AN zusammen).\nÄndert sich meist jährlich zum 01.01. (z.B. 1,7 % auf 2,45 %).")
        info.setStyleSheet("color: #7F8C8D;")
        layout.addWidget(info)
        
        self.table_kv = QTableWidget()
        self.table_kv.setColumnCount(3)
        self.table_kv.setHorizontalHeaderLabels(["Gültig ab", "Gültig bis", "Beitrag (%)"])
        self.table_kv.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_kv)
        
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Eintrag hinzufügen"); btn_add.clicked.connect(self.add_kv_row)
        btn_del = QPushButton("🗑️ Zeile löschen"); btn_del.clicked.connect(self.del_kv_row)
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_del); toolbar.addStretch()
        layout.addLayout(toolbar)

    def add_jahre(self, d: date, jahre: int) -> date:
        try: return d.replace(year=d.year + jahre)
        except ValueError: return d.replace(year=d.year + jahre, day=d.day - 1)

    def generiere_tvl_laufbahn(self):
        start_date = self.date_ifpt_seit.date().toPyDate()
        self.table_gehalt.setRowCount(0)
        stufen_plan = [("1", 1), ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", None)]
        akt_datum = start_date
        for stufe_nr, dauer in stufen_plan:
            row = self.table_gehalt.rowCount()
            self.table_gehalt.insertRow(row)
            date_ab = QDateEdit(); date_ab.setCalendarPopup(True); date_ab.setDate(QDate(akt_datum.year, akt_datum.month, akt_datum.day))
            date_bis = QDateEdit(); date_bis.setCalendarPopup(True); date_bis.setSpecialValueText(" - ")
            
            if dauer is not None:
                naechster_start = self.add_jahre(akt_datum, dauer)
                end_date = naechster_start - timedelta(days=1)
                date_bis.setDate(QDate(end_date.year, end_date.month, end_date.day))
                akt_datum = naechster_start
            else:
                date_bis.setDate(QDate(2099, 12, 31))
                
            self.table_gehalt.setCellWidget(row, 0, date_ab)
            self.table_gehalt.setCellWidget(row, 1, date_bis)
            self.table_gehalt.setCellWidget(row, 2, QLineEdit("13"))
            self.table_gehalt.setCellWidget(row, 3, QLineEdit(stufe_nr))

    def gehaltsschritt_hinzufuegen(self):
        dialog = GehaltSchrittDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            row = self.table_gehalt.rowCount()
            self.table_gehalt.insertRow(row)
            date_ab = QDateEdit(); date_ab.setCalendarPopup(True); date_ab.setDate(QDate(data["gueltig_ab"].year, data["gueltig_ab"].month, data["gueltig_ab"].day))
            date_bis = QDateEdit(); date_bis.setCalendarPopup(True)
            if data["gueltig_bis"]: date_bis.setDate(QDate(data["gueltig_bis"].year, data["gueltig_bis"].month, data["gueltig_bis"].day))
            self.table_gehalt.setCellWidget(row, 0, date_ab)
            self.table_gehalt.setCellWidget(row, 1, date_bis)
            self.table_gehalt.setCellWidget(row, 2, QLineEdit(data["entgeltgruppe"]))
            self.table_gehalt.setCellWidget(row, 3, QLineEdit(data["stufe"]))

    def gehaltsschritt_loeschen(self):
        if self.table_gehalt.currentRow() >= 0: self.table_gehalt.removeRow(self.table_gehalt.currentRow())

    def add_az_row(self, ab=None, bis=None, pct=100.0):
        r = self.table_az.rowCount()
        self.table_az.insertRow(r)
        date_ab = QDateEdit(); date_ab.setCalendarPopup(True)
        if ab: date_ab.setDate(QDate(ab.year, ab.month, ab.day))
        else: date_ab.setDate(QDate.currentDate())
        date_bis = QDateEdit(); date_bis.setCalendarPopup(True); date_bis.setSpecialValueText(" - ")
        if bis: date_bis.setDate(QDate(bis.year, bis.month, bis.day))
        else: date_bis.setDate(QDate(2099, 12, 31))
        spin_pct = QDoubleSpinBox(); spin_pct.setRange(0.0, 100.0); spin_pct.setValue(pct); spin_pct.setSuffix(" %")
        self.table_az.setCellWidget(r, 0, date_ab)
        self.table_az.setCellWidget(r, 1, date_bis)
        self.table_az.setCellWidget(r, 2, spin_pct)

    def del_az_row(self):
        if self.table_az.currentRow() >= 0: self.table_az.removeRow(self.table_az.currentRow())

    # NEU: KV Row Logik
    def add_kv_row(self, ab=None, bis=None, pct=1.7):
        r = self.table_kv.rowCount()
        self.table_kv.insertRow(r)
        date_ab = QDateEdit(); date_ab.setCalendarPopup(True)
        if ab: date_ab.setDate(QDate(ab.year, ab.month, ab.day))
        else: date_ab.setDate(QDate(date.today().year, 1, 1))
        date_bis = QDateEdit(); date_bis.setCalendarPopup(True); date_bis.setSpecialValueText(" - ")
        if bis: date_bis.setDate(QDate(bis.year, bis.month, bis.day))
        else: date_bis.setDate(QDate(2099, 12, 31))
        spin_pct = QDoubleSpinBox(); spin_pct.setRange(0.0, 10.0); spin_pct.setSingleStep(0.1); spin_pct.setValue(pct); spin_pct.setSuffix(" %")
        self.table_kv.setCellWidget(r, 0, date_ab)
        self.table_kv.setCellWidget(r, 1, date_bis)
        self.table_kv.setCellWidget(r, 2, spin_pct)

    def del_kv_row(self):
        if self.table_kv.currentRow() >= 0: self.table_kv.removeRow(self.table_kv.currentRow())

    def lade_daten(self):
        session = get_session()
        try:
            m = session.query(Mitarbeiter).filter_by(id=self.mitarbeiter_id).first()
            if m:
                self.txt_vorname.setText(m.vorname or "")
                self.txt_nachname.setText(m.nachname or "")
                if m.geburtsdatum: self.date_geburt.setDate(QDate(m.geburtsdatum.year, m.geburtsdatum.month, m.geburtsdatum.day))
                if m.am_ifpt_seit: self.date_ifpt_seit.setDate(QDate(m.am_ifpt_seit.year, m.am_ifpt_seit.month, m.am_ifpt_seit.day))
                if m.geplanter_abgang: self.date_abgang.setDate(QDate(m.geplanter_abgang.year, m.geplanter_abgang.month, m.geplanter_abgang.day))
                self.spin_kinder.setValue(m.kinder_anzahl if m.kinder_anzahl else 0)
                self.spin_vl.setValue(m.vl_betrag_euro if m.vl_betrag_euro else 6.65)
                
                self.table_gehalt.setRowCount(0)
                for gv in m.gehaltsverlauf:
                    row = self.table_gehalt.rowCount()
                    self.table_gehalt.insertRow(row)
                    date_ab = QDateEdit(); date_ab.setCalendarPopup(True); date_ab.setDate(QDate(gv.gueltig_ab.year, gv.gueltig_ab.month, gv.gueltig_ab.day))
                    date_bis = QDateEdit(); date_bis.setCalendarPopup(True); date_bis.setSpecialValueText(" - ")
                    if gv.gueltig_bis: date_bis.setDate(QDate(gv.gueltig_bis.year, gv.gueltig_bis.month, gv.gueltig_bis.day))
                    else: date_bis.setDate(QDate(2099, 12, 31))
                    self.table_gehalt.setCellWidget(row, 0, date_ab)
                    self.table_gehalt.setCellWidget(row, 1, date_bis)
                    self.table_gehalt.setCellWidget(row, 2, QLineEdit(gv.entgeltgruppe))
                    self.table_gehalt.setCellWidget(row, 3, QLineEdit(str(gv.stufe)))
                    
                self.table_az.setRowCount(0)
                for az in m.arbeitszeiten:
                    self.add_az_row(az.gueltig_ab, az.gueltig_bis, az.anteil_pct * 100.0)
                if self.table_az.rowCount() == 0: self.add_az_row(pct=100.0)
                
                # NEU: KV-Zusatz laden
                self.table_kv.setRowCount(0)
                for kvz in m.kv_zusatz_verlauf:
                    self.add_kv_row(kvz.gueltig_ab, kvz.gueltig_bis, kvz.beitrag_pct)
                if self.table_kv.rowCount() == 0: self.add_kv_row(pct=1.7)
        finally:
            session.close()

    def daten_speichern(self):
        if not self.txt_vorname.text().strip() or not self.txt_nachname.text().strip():
            QMessageBox.warning(self, "Unvollständig", "Bitte Vor- und Nachnamen eingeben.")
            return

        session = get_session()
        try:
            if self.mitarbeiter_id:
                m = session.query(Mitarbeiter).filter_by(id=self.mitarbeiter_id).first()
                session.query(Gehaltsverlauf).filter_by(mitarbeiter_id=m.id).delete()
                session.query(Arbeitszeitverlauf).filter_by(mitarbeiter_id=m.id).delete()
                session.query(KVZusatzVerlauf).filter_by(mitarbeiter_id=m.id).delete() # NEU
            else:
                m = Mitarbeiter()
                session.add(m)
            
            m.vorname = self.txt_vorname.text().strip()
            m.nachname = self.txt_nachname.text().strip()
            m.geburtsdatum = self.date_geburt.date().toPyDate()
            m.am_ifpt_seit = self.date_ifpt_seit.date().toPyDate()
            abgang = self.date_abgang.date().toPyDate()
            m.geplanter_abgang = None if abgang.year == 2099 else abgang
            
            m.kinder_anzahl = self.spin_kinder.value()
            m.vl_betrag_euro = self.spin_vl.value()
            
            for r in range(self.table_gehalt.rowCount()):
                g_ab = self.table_gehalt.cellWidget(r, 0).date().toPyDate()
                g_bis = self.table_gehalt.cellWidget(r, 1).date().toPyDate()
                eg = self.table_gehalt.cellWidget(r, 2).text()
                st = self.table_gehalt.cellWidget(r, 3).text()
                g_bis_val = None if g_bis.year == 2099 else g_bis
                if eg and st:
                    session.add(Gehaltsverlauf(mitarbeiter=m, entgeltgruppe=eg, stufe=int(st), gueltig_ab=g_ab, gueltig_bis=g_bis_val))
            
            for r in range(self.table_az.rowCount()):
                az_ab = self.table_az.cellWidget(r, 0).date().toPyDate()
                az_bis = self.table_az.cellWidget(r, 1).date().toPyDate()
                pct = self.table_az.cellWidget(r, 2).value() / 100.0
                az_bis_val = None if az_bis.year == 2099 else az_bis
                session.add(Arbeitszeitverlauf(mitarbeiter=m, anteil_pct=pct, gueltig_ab=az_ab, gueltig_bis=az_bis_val))

            # NEU: KV-Zusatz speichern
            for r in range(self.table_kv.rowCount()):
                kv_ab = self.table_kv.cellWidget(r, 0).date().toPyDate()
                kv_bis = self.table_kv.cellWidget(r, 1).date().toPyDate()
                pct = self.table_kv.cellWidget(r, 2).value()
                kv_bis_val = None if kv_bis.year == 2099 else kv_bis
                session.add(KVZusatzVerlauf(mitarbeiter=m, beitrag_pct=pct, gueltig_ab=kv_ab, gueltig_bis=kv_bis_val))

            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", f"Fehler:\n{str(e)}")
        finally:
            session.close()

class LohnjournalDialog(QDialog):
    """Dialog zur Anzeige des detaillierten Lohnjournals inkl. PDF Export"""
    def __init__(self, mitarbeiter_id, parent=None):
        super().__init__(parent)
        self.mitarbeiter_id = mitarbeiter_id
        self.setWindowTitle("Detailliertes Lohnjournal & Arbeitgeberkosten")
        self.resize(1300, 800)
        
        layout = QVBoxLayout(self)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Von Jahr:"))
        self.spin_start_jahr = QSpinBox(); self.spin_start_jahr.setRange(2020, 2035); self.spin_start_jahr.setValue(date.today().year)
        filter_layout.addWidget(self.spin_start_jahr)
        filter_layout.addWidget(QLabel("Monat:"))
        self.spin_start_monat = QSpinBox(); self.spin_start_monat.setRange(1, 12); self.spin_start_monat.setValue(1)
        filter_layout.addWidget(self.spin_start_monat)
        filter_layout.addWidget(QLabel("   Bis Jahr:"))
        self.spin_end_jahr = QSpinBox(); self.spin_end_jahr.setRange(2020, 2035); self.spin_end_jahr.setValue(date.today().year)
        filter_layout.addWidget(self.spin_end_jahr)
        filter_layout.addWidget(QLabel("Monat:"))
        self.spin_end_monat = QSpinBox(); self.spin_end_monat.setRange(1, 12); self.spin_end_monat.setValue(12)
        filter_layout.addWidget(self.spin_end_monat)
        
        btn_generieren = QPushButton("🔄 Journal berechnen")
        btn_generieren.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold; padding: 5px;")
        btn_generieren.clicked.connect(self.lade_journal)
        filter_layout.addWidget(btn_generieren)
        filter_layout.addStretch()
        
        btn_pdf = QPushButton("📄 Professionelles PDF Erzeugen")
        btn_pdf.setStyleSheet("background-color: #D35400; color: white; font-weight: bold; padding: 5px;")
        btn_pdf.clicked.connect(self.export_pdf)
        filter_layout.addWidget(btn_pdf)
        layout.addLayout(filter_layout)
        
        lbl_main = QLabel("<b>Monatlicher Verlauf</b>")
        layout.addWidget(lbl_main)
        
        self.table = QTableWidget()
        self.spalten = ["Monat", "EG", "Brutto", "dav. JSZ", "Rückstellungen", "VWL", "VBL", "AG-KV", "ZKV", "AG-PV", "AG-RV", "AG-AV", "U2", "LUK", "Ist-Kosten", "Kosten (inkl. Rückst.)"]
        self.col_keys = ["monat", "entgeltgruppe", "brutto_gesamt", "davon_jsz", "obligo_jsz", "vl", "versorgungszuschlag", "ag_kv", "ag_zkv", "ag_pv", "ag_rv", "ag_av", "ag_u2", "ag_luk", "gesamtkosten_ist", "gesamtkosten_inkl_rueck"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        lbl_sum = QLabel("<b>Jahreszusammenfassung & Gesamtsummen</b>")
        lbl_sum.setStyleSheet("margin-top: 10px;")
        layout.addWidget(lbl_sum)
        
        self.table_summary = QTableWidget()
        self.table_summary.setColumnCount(len(self.spalten) - 1)
        self.table_summary.setHorizontalHeaderLabels(["Jahr"] + self.spalten[2:])
        self.table_summary.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_summary.setAlternatingRowColors(True)
        self.table_summary.setMaximumHeight(200)
        layout.addWidget(self.table_summary)
        
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        self.lade_journal()

    def fmt(self, val):
        return f"{val:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    def lade_journal(self):
        from core.journal import generiere_mitarbeiter_lohnjournal
        session = get_session()
        try:
            eintraege = generiere_mitarbeiter_lohnjournal(
                session, self.mitarbeiter_id,
                self.spin_start_jahr.value(), self.spin_start_monat.value(),
                self.spin_end_jahr.value(), self.spin_end_monat.value()
            )
            self.table.setRowCount(0)
            self.table_summary.setRowCount(0)
            if not eintraege: return

            jahre_daten = {}
            for e in eintraege:
                jahr = e["monat"].split("/")[1]
                if jahr not in jahre_daten: jahre_daten[jahr] = []
                jahre_daten[jahr].append(e)
                
            gesamt_summen = {k: 0.0 for k in self.col_keys[2:]}
            
            for jahr, monats_liste in jahre_daten.items():
                jahr_summen = {k: 0.0 for k in self.col_keys[2:]}
                
                erfasst_bis_jahresende = any(e["monat"].startswith("11/") or e["monat"].startswith("12/") for e in monats_liste)
                
                for e in monats_liste:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    for c, key in enumerate(self.col_keys):
                        if c < 2:
                            self.table.setItem(row, c, QTableWidgetItem(str(e[key])))
                        else:
                            val = e[key]
                            jahr_summen[key] += val
                            self.table.setItem(row, c, QTableWidgetItem(self.fmt(val)))
                    
                    # Ist-Kosten (hellgrün)
                    ist_item = self.table.item(row, len(self.col_keys)-2)
                    ist_item.setBackground(QColor("#E8F8F5"))
                    ist_item.setForeground(QColor("#000000")) 
                    
                    # Kosten inkl. Rückstellungen (hellgelb für den Kontrast)
                    rueck_item = self.table.item(row, len(self.col_keys)-1)
                    rueck_item.setBackground(QColor("#FCF3CF"))
                    rueck_item.setForeground(QColor("#000000"))
                
                if erfasst_bis_jahresende:
                    jahr_summen["obligo_jsz"] = 0.0
                    
                for k in self.col_keys[2:]:
                    gesamt_summen[k] += jahr_summen[k]
                    
                if len(jahre_daten) >= 1:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    item_jahr = QTableWidgetItem(f"Summe {jahr}")
                    font = item_jahr.font(); font.setBold(True); item_jahr.setFont(font)
                    item_jahr.setBackground(QColor("#D6EAF8"))
                    item_jahr.setForeground(QColor("#000000"))
                    self.table.setItem(row, 0, item_jahr)
                    self.table.setItem(row, 1, QTableWidgetItem(""))
                    for c, key in enumerate(self.col_keys[2:], start=2):
                        val = jahr_summen[key]
                        item = QTableWidgetItem(self.fmt(val))
                        item.setFont(font)
                        item.setBackground(QColor("#D6EAF8"))
                        item.setForeground(QColor("#000000"))
                        self.table.setItem(row, c, item)
                        
                r_sum = self.table_summary.rowCount()
                self.table_summary.insertRow(r_sum)
                self.table_summary.setItem(r_sum, 0, QTableWidgetItem(jahr))
                for c, key in enumerate(self.col_keys[2:], start=1):
                    val = jahr_summen[key]
                    self.table_summary.setItem(r_sum, c, QTableWidgetItem(self.fmt(val)))
                    
            row = self.table.rowCount()
            self.table.insertRow(row)
            item_ges = QTableWidgetItem("Gesamtsumme")
            font = item_ges.font(); font.setBold(True); item_ges.setFont(font)
            item_ges.setBackground(QColor("#AED6F1"))
            item_ges.setForeground(QColor("#000000"))
            self.table.setItem(row, 0, item_ges)
            self.table.setItem(row, 1, QTableWidgetItem(""))
            for c, key in enumerate(self.col_keys[2:], start=2):
                val = gesamt_summen[key]
                item = QTableWidgetItem(self.fmt(val))
                item.setFont(font)
                item.setBackground(QColor("#AED6F1"))
                item.setForeground(QColor("#000000"))
                self.table.setItem(row, c, item)
                
            r_sum = self.table_summary.rowCount()
            self.table_summary.insertRow(r_sum)
            item_ges2 = QTableWidgetItem("Gesamt")
            item_ges2.setFont(font)
            item_ges2.setBackground(QColor("#AED6F1"))
            item_ges2.setForeground(QColor("#000000"))
            self.table_summary.setItem(r_sum, 0, item_ges2)
            for c, key in enumerate(self.col_keys[2:], start=1):
                val = gesamt_summen[key]
                item = QTableWidgetItem(self.fmt(val))
                item.setFont(font)
                item.setBackground(QColor("#AED6F1"))
                item.setForeground(QColor("#000000"))
                self.table_summary.setItem(r_sum, c, item)
        finally:
            session.close()

    def export_pdf(self):
        session = get_session()
        try:
            ma = session.query(Mitarbeiter).filter_by(id=self.mitarbeiter_id).first()
            if not ma: return
            
            start_j = self.spin_start_jahr.value()
            end_j = self.spin_end_jahr.value()
            heute = datetime.now()
            heute_str = heute.strftime('%d.%m.%Y %H:%M')
            file_heute = heute.strftime('%Y%m%d')
            
            default_name = f"Lohnjournal_{ma.vorname}_{ma.nachname}_{start_j}-{end_j}_{file_heute}.pdf"
            filepath, _ = QFileDialog.getSaveFileName(self, "PDF speichern", default_name, "PDF Dateien (*.pdf)", options=QFileDialog.Option.DontUseNativeDialog)
            if not filepath: return
            
            try:
                with open(filepath, 'a'):
                    pass
            except PermissionError:
                QMessageBox.warning(self, "Datei ist gesperrt", f"Die Datei kann nicht überschrieben werden, da sie noch geöffnet ist!\n\nBitte schließen Sie die Datei '{filepath}' und versuchen Sie es erneut.")
                return
            
            writer = QPdfWriter(filepath)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageOrientation(QPageLayout.Orientation.Landscape)
            writer.setResolution(300)
            
            layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
            writer.setPageLayout(layout)
            
            html = """
            <html>
            <head>
            <style>
                body { font-family: Arial, sans-serif; color: #000000; font-size: 10pt; }
                h1 { color: #2C3E50; font-size: 16pt; margin-bottom: 5px; }
                .info-box { font-size: 10pt; padding: 10px; border: 1px solid #34495E; background-color: #F8F9F9; margin-bottom: 20px; }
                table { width: 100%; border-collapse: collapse; font-size: 9.5pt; margin-bottom: 20px; page-break-inside: avoid; }
                th { background-color: #EAEDED; font-weight: bold; border: 1px solid #777; padding: 5px; text-align: right; }
                th.left { text-align: left; }
                td { border: 1px solid #777; padding: 5px; text-align: right; }
                td.left { text-align: left; }
                .sum-row td { background-color: #D6EAF8; font-weight: bold; }
                .total-row td { background-color: #AED6F1; font-weight: bold; }
                h2 { color: #2980B9; font-size: 12pt; margin-top: 15px; margin-bottom: 5px; page-break-after: avoid; }
            </style>
            </head>
            <body>
            """
            
            geb = ma.geburtsdatum.strftime('%d.%m.%Y') if ma.geburtsdatum else "-"
            seit = ma.am_ifpt_seit.strftime('%d.%m.%Y') if ma.am_ifpt_seit else "-"
            kinder = ma.kinder_anzahl if ma.kinder_anzahl else 0
            vwl = ma.vl_betrag_euro if ma.vl_betrag_euro else 0.0
            
            # Hole den aktuellen KV-Satz für das PDF Info-Feld
            akt_kv = 1.7
            for kvz in ma.kv_zusatz_verlauf:
                if kvz.gueltig_ab <= date.today() and (not kvz.gueltig_bis or kvz.gueltig_bis >= date.today()):
                    akt_kv = kvz.beitrag_pct
                    break

            html += f"""
            <h1>Detailliertes Lohnjournal & AG-Kostenverlauf</h1>
            <div class="info-box">
                <b>Mitarbeiter:</b> {ma.vorname} {ma.nachname} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Geboren:</b> {geb} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Eintritt:</b> {seit}<br>
                <b>Faktoren:</b> {kinder} Kind(er), KV-Zusatz (heute): {akt_kv}%, VWL: {vwl} € &nbsp;&nbsp;|&nbsp;&nbsp; <b>Zeitraum:</b> {self.spin_start_monat.value():02d}/{start_j} - {self.spin_end_monat.value():02d}/{end_j}
            </div>
            """
            
            jahre_html = {}
            current_jahr = ""
            for r in range(self.table.rowCount()):
                monat_text = self.table.item(r, 0).text()
                if "Gesamtsumme" in monat_text:
                    if current_jahr not in jahre_html: jahre_html[current_jahr] = []
                    jahre_html[current_jahr].append((r, 'total'))
                    continue
                if "Summe" in monat_text:
                    jahr_str = monat_text.split(" ")[-1]
                    if jahr_str not in jahre_html: jahre_html[jahr_str] = []
                    jahre_html[jahr_str].append((r, 'sum'))
                    continue
                    
                jahr_str = monat_text.split("/")[1]
                if jahr_str not in jahre_html: jahre_html[jahr_str] = []
                current_jahr = jahr_str
                jahre_html[jahr_str].append((r, 'normal'))

            for jahr in jahre_html.keys():
                html += f"<h2>Lohnjournal für das Jahr {jahr}</h2>"
                html += "<table><thead><tr>"
                for c in range(self.table.columnCount()): 
                    align = " class='left'" if c < 2 else ""
                    html += f"<th{align}>{self.table.horizontalHeaderItem(c).text()}</th>"
                html += "</tr></thead><tbody>"

                for r, r_type in jahre_html[jahr]:
                    row_cls = ' class="sum-row"' if r_type == 'sum' else ' class="total-row"' if r_type == 'total' else ''
                    html += f"<tr{row_cls}>"
                    for c in range(self.table.columnCount()):
                        item = self.table.item(r, c)
                        text = item.text() if item else ""
                        align = " class='left'" if c < 2 else ""
                        html += f"<td{align}>{text}</td>"
                    html += "</tr>"
                html += "</tbody></table>"
            
            html += "<h2>Jahreszusammenfassung & Gesamtsummen</h2>"
            html += "<table><thead><tr>"
            for c in range(self.table_summary.columnCount()): 
                align = " class='left'" if c == 0 else ""
                html += f"<th{align}>{self.table_summary.horizontalHeaderItem(c).text()}</th>"
            html += "</tr></thead><tbody>"
            
            for r in range(self.table_summary.rowCount()):
                row_cls = ' class="total-row"' if r == self.table_summary.rowCount()-1 else ''
                html += f"<tr{row_cls}>"
                for c in range(self.table_summary.columnCount()):
                    item = self.table_summary.item(r, c)
                    text = item.text() if item else ""
                    align = " class='left'" if c == 0 else ""
                    html += f"<td{align}>{text}</td>"
                html += "</tr>"
            html += "</tbody></table>"
            
            html += f"<div style='text-align: right; font-size: 8pt; color: #7F8C8D; margin-top: 30px;'>Erstellt am: {heute_str}</div>"
            html += "</body></html>"

            doc = QTextDocument()
            doc.setHtml(html)
            
            doc.print(writer)
            
            QMessageBox.information(self, "Erfolg", f"Das Lohnjournal wurde perfekt als A4 Querformat-PDF exportiert:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim PDF-Export:\n{str(e)}")
        finally:
            session.close()

class MitarbeiterView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        title = QLabel("Mitarbeiter-Stammdaten & Verträge")
        title.setProperty("title", "true")
        main_layout.addWidget(title)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neuer Mitarbeiter")
        btn_add.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self.mitarbeiter_hinzufuegen)
        
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.clicked.connect(self.mitarbeiter_bearbeiten)
        
        btn_journal = QPushButton("📋 Lohnjournal")
        btn_journal.clicked.connect(self.lohnjournal_oeffnen)
        
        btn_del = QPushButton("🗑️ Löschen")
        btn_del.clicked.connect(self.mitarbeiter_loeschen)
        
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["Nur Aktive", "Alle Mitarbeiter", "Ausgeschieden"])
        self.combo_filter.currentIndexChanged.connect(self.load_data)
        
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_edit); toolbar.addWidget(btn_journal); toolbar.addWidget(btn_del)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Filter:"))
        toolbar.addWidget(self.combo_filter)
        main_layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.spalten = ["ID", "Nachname", "Vorname", "Eintritt", "Geplanter Abgang", "Restlaufzeit", "Aktion", "KV-Zusatz", "VWL", "AZ"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.mitarbeiter_bearbeiten)
        main_layout.addWidget(self.table)

    def load_data(self):
        session = get_session()
        self.table.setRowCount(0)
        heute = date.today()
        filter_idx = self.combo_filter.currentIndex()
        
        try:
            mitarbeiter = session.query(Mitarbeiter).order_by(Mitarbeiter.nachname).all()
            for m in mitarbeiter:
                is_active = not m.geplanter_abgang or m.geplanter_abgang >= heute
                if filter_idx == 0 and not is_active: continue
                if filter_idx == 2 and is_active: continue

                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(m.id)))
                self.table.setItem(row, 1, QTableWidgetItem(m.nachname))
                self.table.setItem(row, 2, QTableWidgetItem(m.vorname))
                self.table.setItem(row, 3, QTableWidgetItem(m.am_ifpt_seit.strftime("%d.%m.%Y") if m.am_ifpt_seit else "-"))
                
                abgang_str = m.geplanter_abgang.strftime("%d.%m.%Y") if m.geplanter_abgang else "Unbefristet"
                self.table.setItem(row, 4, QTableWidgetItem(abgang_str))
                
                # Restlaufzeit & Ampel
                rest_item = QTableWidgetItem("-")
                rest_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if m.geplanter_abgang:
                    monate_rest = (m.geplanter_abgang.year - heute.year) * 12 + (m.geplanter_abgang.month - heute.month)
                    if monate_rest < 0:
                        rest_item.setText("Abgelaufen")
                        rest_item.setForeground(QColor("#7F8C8D"))
                    else:
                        rest_item.setText(f"{monate_rest} Monate")
                        if monate_rest <= 3:
                            rest_item.setBackground(QColor("#F5B7B1")) # Rot
                            rest_item.setForeground(QColor("#000000"))
                        elif monate_rest <= 12:
                            rest_item.setBackground(QColor("#F9E79F")) # Gelb
                            rest_item.setForeground(QColor("#000000"))
                self.table.setItem(row, 5, rest_item)
                
                # Aktion: +1 Jahr Button
                btn_plus = QPushButton("+1 Jahr")
                btn_plus.setStyleSheet("background-color: #3498DB; color: white; padding: 2px;")
                btn_plus.clicked.connect(lambda checked, m_id=m.id: self.verlaengere_vertrag(m_id))
                self.table.setCellWidget(row, 6, btn_plus)
                
                akt_kv = next((kvz.beitrag_pct for kvz in m.kv_zusatz_verlauf if kvz.gueltig_ab <= heute and (not kvz.gueltig_bis or kvz.gueltig_bis >= heute)), 1.7)
                self.table.setItem(row, 7, QTableWidgetItem(f"{akt_kv:.2f} %"))
                self.table.setItem(row, 8, QTableWidgetItem(f"{m.vl_betrag_euro or 0.0:,.2f} €"))
                
                akt_az = next((az.anteil_pct for az in m.arbeitszeiten if az.gueltig_ab <= heute and (not az.gueltig_bis or az.gueltig_bis >= heute)), 1.0)
                self.table.setItem(row, 9, QTableWidgetItem(f"{akt_az * 100:.1f} %"))
        finally:
            session.close()

    def verlaengere_vertrag(self, m_id):
        session = get_session()
        try:
            m = session.query(Mitarbeiter).filter_by(id=m_id).first()
            if m and m.geplanter_abgang:
                try:
                    m.geplanter_abgang = m.geplanter_abgang.replace(year=m.geplanter_abgang.year + 1)
                except ValueError:
                    m.geplanter_abgang = m.geplanter_abgang.replace(year=m.geplanter_abgang.year + 1, day=28)
                session.commit()
                self.load_data()
        finally:
            session.close()

    def mitarbeiter_hinzufuegen(self):
        dialog = MitarbeiterBearbeitenDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted: 
            self.load_data()

    def mitarbeiter_bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        dialog = MitarbeiterBearbeitenDialog(mitarbeiter_id=int(self.table.item(row, 0).text()), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted: 
            self.load_data()
        
    def lohnjournal_oeffnen(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Hinweis", "Bitte wählen Sie einen Mitarbeiter aus der Tabelle aus.")
            return
        ma_id = int(self.table.item(row, 0).text())
        dialog = LohnjournalDialog(ma_id, parent=self)
        dialog.exec()

    def mitarbeiter_loeschen(self):
        row = self.table.currentRow()
        if row < 0: return
        name = f"{self.table.item(row, 2).text()} {self.table.item(row, 1).text()}"
        if QMessageBox.question(self, "Löschen", f"Mitarbeiter {name} samt Historie löschen?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                m = session.query(Mitarbeiter).filter_by(id=int(self.table.item(row, 0).text())).first()
                if m: 
                    session.delete(m)
                    session.commit()
                    self.load_data()
            finally:
                session.close()