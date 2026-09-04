import calendar
from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QComboBox, 
                             QHeaderView, QLabel, QMessageBox, QDialog, QFormLayout, 
                             QDateEdit, QDoubleSpinBox, QDialogButtonBox)
from PyQt6.QtCore import Qt, QDate
from core.database import get_session
from core.models import Mitarbeiter, Projekt, Zuweisung, ZuweisungsTyp

class IstAbweichungDialog(QDialog):
    """Dialog zum Erfassen von abweichenden Stundenzetteln (IST-Zeiten)"""
    def __init__(self, zuweisung_id=None, parent=None):
        super().__init__(parent)
        self.zuweisung_id = zuweisung_id
        self.setWindowTitle("Ist-Abweichung (Stundenzettel) erfassen")
        self.resize(450, 300)
        
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.combo_projekt = QComboBox()
        layout.addRow("Projekt:", self.combo_projekt)
        
        self.combo_mitarbeiter = QComboBox()
        layout.addRow("Mitarbeiter:", self.combo_mitarbeiter)
        
        # Standardmäßig den aktuellen Monat vorauswählen
        heute = date.today()
        erster_tag = date(heute.year, heute.month, 1)
        letzter_tag = date(heute.year, heute.month, calendar.monthrange(heute.year, heute.month)[1])
        
        self.date_start = QDateEdit()
        self.date_start.setDate(QDate(erster_tag.year, erster_tag.month, erster_tag.day))
        self.date_start.setCalendarPopup(True)
        layout.addRow("Gültig von:", self.date_start)
        
        self.date_ende = QDateEdit()
        self.date_ende.setDate(QDate(letzter_tag.year, letzter_tag.month, letzter_tag.day))
        self.date_ende.setCalendarPopup(True)
        layout.addRow("Gültig bis:", self.date_ende)
        
        self.spin_anteil = QDoubleSpinBox()
        self.spin_anteil.setRange(0.0, 100.0)
        self.spin_anteil.setSingleStep(5.0)
        self.spin_anteil.setValue(0.0)
        self.spin_anteil.setSuffix(" %")
        layout.addRow("Tatsächlicher IST-Anteil:", self.spin_anteil)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.daten_speichern)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.lade_dropdowns()
        if self.zuweisung_id:
            self.lade_daten()

    def lade_dropdowns(self):
        session = get_session()
        try:
            for p in session.query(Projekt).order_by(Projekt.projektname).all():
                self.combo_projekt.addItem(p.projektname, p.id)
            for m in session.query(Mitarbeiter).order_by(Mitarbeiter.nachname).all():
                self.combo_mitarbeiter.addItem(f"{m.nachname}, {m.vorname}", m.id)
        finally:
            session.close()

    def lade_daten(self):
        session = get_session()
        try:
            z = session.query(Zuweisung).filter_by(id=self.zuweisung_id).first()
            if z:
                idx_p = self.combo_projekt.findData(z.projekt_id)
                if idx_p >= 0: self.combo_projekt.setCurrentIndex(idx_p)
                idx_m = self.combo_mitarbeiter.findData(z.mitarbeiter_id)
                if idx_m >= 0: self.combo_mitarbeiter.setCurrentIndex(idx_m)
                
                self.date_start.setDate(QDate(z.start_datum.year, z.start_datum.month, z.start_datum.day))
                self.date_ende.setDate(QDate(z.end_datum.year, z.end_datum.month, z.end_datum.day))
                self.spin_anteil.setValue(z.anteil_pct * 100.0)
        finally:
            session.close()

    def daten_speichern(self):
        start_date = self.date_start.date().toPyDate()
        end_date = self.date_ende.date().toPyDate()
        
        if end_date < start_date:
            QMessageBox.warning(self, "Fehler", "Enddatum darf nicht vor Startdatum liegen.")
            return

        session = get_session()
        try:
            if self.zuweisung_id:
                z = session.query(Zuweisung).filter_by(id=self.zuweisung_id).first()
            else:
                z = Zuweisung()
                session.add(z)
                
            z.projekt_id = self.combo_projekt.currentData()
            z.mitarbeiter_id = self.combo_mitarbeiter.currentData()
            z.start_datum = start_date
            z.end_datum = end_date
            z.anteil_pct = self.spin_anteil.value() / 100.0
            
            # WICHTIG: Hier wird das Typen-Feld hart auf IST gesetzt!
            z.typ = ZuweisungsTyp.IST
            
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", f"Fehler:\n{str(e)}")
        finally:
            session.close()


class IstAbweichungenView(QWidget):
    """Hauptansicht für das Management by Exception (Erfassung von IST-Abweichungen)"""
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("Erfassung von Ist-Abweichungen (Stundenzettel)")
        title.setProperty("title", "true")
        layout.addWidget(title)
        
        info = QLabel("<i>Hinweis: Das System geht davon aus, dass Plan = Ist ist. Erfassen Sie hier <b>nur</b> Abweichungen, "
                      "wenn ein Mitarbeiter in einem Monat real mehr oder weniger auf einem Projekt gearbeitet hat als geplant.</i>")
        info.setStyleSheet("color: #7F8C8D; margin-bottom: 10px;")
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neue Abweichung erfassen")
        btn_add.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self.hinzufuegen)
        
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.setStyleSheet("background-color: #2980B9; color: white; padding: 6px;")
        btn_edit.clicked.connect(self.bearbeiten)
        
        btn_del = QPushButton("🗑️ Löschen")
        btn_del.setStyleSheet("background-color: #C0392B; color: white; padding: 6px;")
        btn_del.clicked.connect(self.loeschen)
        
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_del)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.spalten = ["ID", "Projekt", "Mitarbeiter", "Abweichender Zeitraum", "Gebuchter Ist-Anteil (%)"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.bearbeiten)
        layout.addWidget(self.table)

    def load_data(self):
        session = get_session()
        self.table.setRowCount(0)
        try:
            # Wir laden NUR die echten IST-Werte (Abweichungen)
            ist_werte = session.query(Zuweisung).filter(Zuweisung.typ == ZuweisungsTyp.IST).all()
            
            for z in ist_werte:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                self.table.setItem(row, 0, QTableWidgetItem(str(z.id)))
                self.table.setItem(row, 1, QTableWidgetItem(z.projekt.projektname if z.projekt else "Gelöscht"))
                self.table.setItem(row, 2, QTableWidgetItem(f"{z.mitarbeiter.nachname}, {z.mitarbeiter.vorname}" if z.mitarbeiter else "Gelöscht"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{z.start_datum.strftime('%d.%m.%Y')} - {z.end_datum.strftime('%d.%m.%Y')}"))
                
                item_pct = QTableWidgetItem(f"{z.anteil_pct * 100:.1f} %")
                font = item_pct.font()
                font.setBold(True)
                item_pct.setFont(font)
                self.table.setItem(row, 4, item_pct)
        finally:
            session.close()

    def hinzufuegen(self):
        dialog = IstAbweichungDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        dialog = IstAbweichungDialog(zuweisung_id=int(self.table.item(row, 0).text()), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def loeschen(self):
        row = self.table.currentRow()
        if row < 0: return
        z_id = int(self.table.item(row, 0).text())
        if QMessageBox.question(self, "Löschen", "Diese Abweichung löschen? Danach gilt wieder der Plan-Wert.", 
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                z = session.query(Zuweisung).filter_by(id=z_id).first()
                if z:
                    session.delete(z)
                    session.commit()
                    self.load_data()
            finally:
                session.close()