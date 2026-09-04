from datetime import date, datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QDateEdit, 
                             QDoubleSpinBox, QDialogButtonBox, QTabWidget)
from PyQt6.QtCore import Qt, QDate

from core.database import get_session
from core.models import SystemParameter
from gui.views.view_tarife import TarifeView

# ==========================================
# DIALOG FÜR PARAMETER EINES ZEITRAUMS
# ==========================================
class ParameterBearbeitenDialog(QDialog):
    def __init__(self, ref_datum=None, parent=None, is_copy=False):
        super().__init__(parent)
        self.ref_datum = ref_datum
        self.is_copy = is_copy
        
        titel = "Systemparameter & Grenzen bearbeiten" if ref_datum and not is_copy else "Neue Systemparameter anlegen"
        self.setWindowTitle(titel)
        self.resize(500, 500)
        
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.date_ab = QDateEdit()
        self.date_ab.setCalendarPopup(True)
        self.date_ab.setDate(QDate.currentDate())
        layout.addRow("Gültig ab:", self.date_ab)
        
        lbl_bbg = QLabel("<b>Beitragsbemessungsgrenzen (monatlich)</b>")
        lbl_bbg.setStyleSheet("color: #2980B9; margin-top: 10px;")
        layout.addRow(lbl_bbg)
        
        self.spin_bbg_kv = self._create_euro_spinbox(5175.00)
        layout.addRow("BBG Kranken-/Pflegeversicherung:", self.spin_bbg_kv)
        
        self.spin_bbg_rv = self._create_euro_spinbox(7550.00)
        layout.addRow("BBG Renten-/Arbeitslosenvers.:", self.spin_bbg_rv)
        
        lbl_ag = QLabel("<b>Arbeitgeber-Anteile (%)</b>")
        lbl_ag.setStyleSheet("color: #2980B9; margin-top: 10px;")
        layout.addRow(lbl_ag)
        
        self.spin_rv = self._create_pct_spinbox(9.30)
        layout.addRow("AG-Anteil Rentenversicherung:", self.spin_rv)
        
        self.spin_av = self._create_pct_spinbox(1.30)
        layout.addRow("AG-Anteil Arbeitslosenvers.:", self.spin_av)
        
        self.spin_kv = self._create_pct_spinbox(7.30)
        layout.addRow("AG-Anteil Krankenvers. (Basis):", self.spin_kv)
        
        self.spin_pv = self._create_pct_spinbox(1.70)
        layout.addRow("AG-Anteil Pflegeversicherung:", self.spin_pv)
        
        lbl_sonst = QLabel("<b>Zusatz-Umlagen (%)</b>")
        lbl_sonst.setStyleSheet("color: #2980B9; margin-top: 10px;")
        layout.addRow(lbl_sonst)
        
        self.spin_vbl = self._create_pct_spinbox(6.45)
        layout.addRow("VBL-Satz (Arbeitgeber):", self.spin_vbl)
        
        self.spin_u2 = self._create_pct_spinbox(0.39)
        layout.addRow("U2-Umlage (Mutterschutz):", self.spin_u2)
        
        # NEU: LUK-Satz
        self.spin_luk = self._create_pct_spinbox(0.320) # Standard-Schätzwert
        layout.addRow("Landesunfallkasse (LUK):", self.spin_luk)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.daten_speichern)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        if self.ref_datum:
            self.lade_daten()

    def _create_euro_spinbox(self, default_val):
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 20000.0)
        spin.setDecimals(2)
        spin.setGroupSeparatorShown(True)
        spin.setSuffix(" €")
        spin.setValue(default_val)
        return spin
        
    def _create_pct_spinbox(self, default_val):
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 50.0)
        spin.setDecimals(4)
        spin.setSuffix(" %")
        spin.setValue(default_val)
        return spin

    def lade_daten(self):
        session = get_session()
        try:
            params = session.query(SystemParameter).filter_by(gueltig_ab=self.ref_datum).all()
            if not params: return
            
            if not self.is_copy:
                self.date_ab.setDate(QDate(self.ref_datum.year, self.ref_datum.month, self.ref_datum.day))
            
            mapping = {
                "bbg_kv_pv": self.spin_bbg_kv,
                "bbg_rv_av": self.spin_bbg_rv,
                "ag_rv": self.spin_rv,
                "ag_av": self.spin_av,
                "ag_kv_base": self.spin_kv,
                "ag_pv": self.spin_pv,
                "vbl_satz": self.spin_vbl,
                "u2_satz": self.spin_u2,
                "luk_satz": self.spin_luk # NEU
            }
            
            for p in params:
                if p.schluessel in mapping:
                    faktor = 100.0 if "bbg" not in p.schluessel else 1.0
                    mapping[p.schluessel].setValue(p.wert * faktor)
        finally:
            session.close()

    def daten_speichern(self):
        start_date = self.date_ab.date().toPyDate()
        session = get_session()
        try:
            if self.ref_datum and not self.is_copy:
                session.query(SystemParameter).filter_by(gueltig_ab=self.ref_datum).delete()
            elif session.query(SystemParameter).filter_by(gueltig_ab=start_date).first():
                if QMessageBox.warning(self, "Existiert", "Überschreiben?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                    session.query(SystemParameter).filter_by(gueltig_ab=start_date).delete()
                else:
                    return

            werte_dict = {
                "bbg_kv_pv": self.spin_bbg_kv.value(),
                "bbg_rv_av": self.spin_bbg_rv.value(),
                "ag_rv": self.spin_rv.value() / 100.0,
                "ag_av": self.spin_av.value() / 100.0,
                "ag_kv_base": self.spin_kv.value() / 100.0,
                "ag_pv": self.spin_pv.value() / 100.0,
                "vbl_satz": self.spin_vbl.value() / 100.0,
                "u2_satz": self.spin_u2.value() / 100.0,
                "luk_satz": self.spin_luk.value() / 100.0 # NEU
            }
            
            for k, v in werte_dict.items():
                session.add(SystemParameter(schluessel=k, wert=v, gueltig_ab=start_date))
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", f"Konnte nicht speichern:\n{str(e)}")
        finally:
            session.close()

class SystemParameterView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        info = QLabel("Definieren Sie hier historische SV-Anteile und Umlagen (inkl. LUK).")
        info.setStyleSheet("color: #7F8C8D; margin-bottom: 10px;")
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neue Epoche anlegen")
        btn_add.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self.hinzufuegen)
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.setStyleSheet("background-color: #2980B9; color: white; padding: 6px;")
        btn_edit.clicked.connect(self.bearbeiten)
        btn_copy = QPushButton("📑 Duplizieren (Neues Jahr)")
        btn_copy.setStyleSheet("background-color: #8E44AD; color: white; padding: 6px;")
        btn_copy.clicked.connect(self.duplizieren)
        
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_edit); toolbar.addWidget(btn_copy); toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        # NEU: LUK Spalte hinzugefügt
        self.spalten = ["Gültig ab", "BBG KV/PV", "BBG RV/AV", "SV (RV/AV/KV/PV)", "VBL", "U2", "LUK"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.bearbeiten)
        layout.addWidget(self.table)

    def load_data(self):
        session = get_session()
        self.table.setRowCount(0)
        try:
            dates = session.query(SystemParameter.gueltig_ab).distinct().order_by(SystemParameter.gueltig_ab.desc()).all()
            for (d,) in dates:
                params = session.query(SystemParameter).filter_by(gueltig_ab=d).all()
                p_dict = {p.schluessel: p.wert for p in params}
                
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(d.strftime('%d.%m.%Y')))
                self.table.setItem(row, 1, QTableWidgetItem(f"{p_dict.get('bbg_kv_pv', 0.0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")))
                self.table.setItem(row, 2, QTableWidgetItem(f"{p_dict.get('bbg_rv_av', 0.0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")))
                sv_str = f"RV {p_dict.get('ag_rv',0)*100:.1f}% | AV {p_dict.get('ag_av',0)*100:.1f}% | KV {p_dict.get('ag_kv_base',0)*100:.1f}% | PV {p_dict.get('ag_pv',0)*100:.1f}%"
                self.table.setItem(row, 3, QTableWidgetItem(sv_str))
                self.table.setItem(row, 4, QTableWidgetItem(f"{p_dict.get('vbl_satz',0)*100:.2f} %"))
                self.table.setItem(row, 5, QTableWidgetItem(f"{p_dict.get('u2_satz',0)*100:.2f} %"))
                # NEU: LUK Wert anzeigen
                self.table.setItem(row, 6, QTableWidgetItem(f"{p_dict.get('luk_satz',0)*100:.2f} %"))
        finally:
            session.close()

    def hinzufuegen(self):
        if ParameterBearbeitenDialog(parent=self).exec() == QDialog.DialogCode.Accepted: self.load_data()
    def bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        ref_datum = datetime.strptime(self.table.item(row, 0).text(), '%d.%m.%Y').date()
        if ParameterBearbeitenDialog(ref_datum=ref_datum, parent=self).exec() == QDialog.DialogCode.Accepted: self.load_data()
    def duplizieren(self):
        row = self.table.currentRow()
        if row < 0: return
        ref_datum = datetime.strptime(self.table.item(row, 0).text(), '%d.%m.%Y').date()
        if ParameterBearbeitenDialog(ref_datum=ref_datum, parent=self, is_copy=True).exec() == QDialog.DialogCode.Accepted: self.load_data()

class SystemAdminMainView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.tarife_view = TarifeView()
        self.param_view = SystemParameterView()
        self.tabs.addTab(self.tarife_view, "📊 TV-L Entgelttabellen & JSZ")
        self.tabs.addTab(self.param_view, "⚙️ Sozialversicherung & Systemgrenzen")