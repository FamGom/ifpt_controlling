from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QLineEdit, 
                             QDoubleSpinBox, QDialogButtonBox, QGroupBox, QSplitter)
from PyQt6.QtCore import Qt
from sqlalchemy.exc import IntegrityError

from core.database import get_session
from core.models import InstitutsKonto, OverheadRegel

class KontoBearbeitenDialog(QDialog):
    def __init__(self, konto_id=None, parent=None):
        super().__init__(parent)
        self.konto_id = konto_id
        self.setWindowTitle("Instituts-Konto bearbeiten" if konto_id else "Neues Konto anlegen")
        self.resize(400, 200)
        self.setup_ui()
        if self.konto_id: self.lade_daten()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("z.B. Freie Drittmittel")
        form.addRow("Kontoname:", self.txt_name)
        
        self.txt_nummer = QLineEdit()
        self.txt_nummer.setPlaceholderText("Optional")
        form.addRow("Kontonummer / PSP-Element:", self.txt_nummer)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.speichern)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def lade_daten(self):
        session = get_session()
        try:
            k = session.query(InstitutsKonto).filter_by(id=self.konto_id).first()
            if k:
                self.txt_name.setText(k.name)
                self.txt_nummer.setText(k.kontonummer or "")
        finally:
            session.close()

    def speichern(self):
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Fehler", "Der Kontoname darf nicht leer sein.")
            return
            
        session = get_session()
        try:
            if self.konto_id:
                k = session.query(InstitutsKonto).filter_by(id=self.konto_id).first()
            else:
                k = InstitutsKonto()
                session.add(k)
                
            k.name = self.txt_name.text().strip()
            k.kontonummer = self.txt_nummer.text().strip()
            
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", str(e))
        finally:
            session.close()


class RegelBearbeitenDialog(QDialog):
    def __init__(self, regel_id=None, parent=None):
        super().__init__(parent)
        self.regel_id = regel_id
        self.setWindowTitle("Overhead-Regel bearbeiten" if regel_id else "Neue Regel anlegen")
        self.resize(450, 250)
        self.setup_ui()
        if self.regel_id: self.lade_daten()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("z.B. EU Horizon (25%)")
        form.addRow("Regel-Bezeichnung:", self.txt_name)
        
        self.spin_gesamt = QDoubleSpinBox(); self.spin_gesamt.setRange(0, 100); self.spin_gesamt.setSuffix(" %")
        form.addRow("Gesamter Overhead-Satz:", self.spin_gesamt)
        
        self.spin_inst = QDoubleSpinBox(); self.spin_inst.setRange(0, 100); self.spin_inst.setSuffix(" %")
        form.addRow("Davon Anteil für Institut:", self.spin_inst)
        
        self.spin_verw = QDoubleSpinBox(); self.spin_verw.setRange(0, 100); self.spin_verw.setSuffix(" %")
        form.addRow("Davon Anteil für Verwaltung:", self.spin_verw)
        
        layout.addLayout(form)
        
        info = QLabel("<i>Hinweis: Institut + Verwaltung = Gesamt.</i>")
        info.setStyleSheet("color: gray; font-size: 8pt;")
        layout.addWidget(info)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.speichern)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def lade_daten(self):
        session = get_session()
        try:
            r = session.query(OverheadRegel).filter_by(id=self.regel_id).first()
            if r:
                self.txt_name.setText(r.name)
                self.spin_gesamt.setValue(r.gesamt_pct)
                self.spin_inst.setValue(r.institut_pct)
                self.spin_verw.setValue(r.verwaltung_pct)
        finally:
            session.close()

    def speichern(self):
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Fehler", "Die Bezeichnung darf nicht leer sein.")
            return
            
        session = get_session()
        try:
            if self.regel_id:
                r = session.query(OverheadRegel).filter_by(id=self.regel_id).first()
            else:
                r = OverheadRegel()
                session.add(r)
                
            r.name = self.txt_name.text().strip()
            r.gesamt_pct = self.spin_gesamt.value()
            r.institut_pct = self.spin_inst.value()
            r.verwaltung_pct = self.spin_verw.value()
            
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", str(e))
        finally:
            session.close()


class StammdatenView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        title = QLabel("Stammdaten: Konten & Overhead-Regeln")
        title.setProperty("title", "true")
        main_layout.addWidget(title)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # --- KONTEN VERWALTUNG ---
        grp_konten = QGroupBox("Instituts-Konten / Rücklagen-Töpfe")
        lay_konten = QVBoxLayout(grp_konten)
        
        tool_k = QHBoxLayout()
        btn_k_neu = QPushButton("➕ Neues Konto"); btn_k_neu.clicked.connect(self.neu_konto)
        btn_k_edit = QPushButton("✏️ Bearbeiten"); btn_k_edit.clicked.connect(self.edit_konto)
        btn_k_del = QPushButton("🗑️ Löschen"); btn_k_del.clicked.connect(self.del_konto)
        tool_k.addWidget(btn_k_neu); tool_k.addWidget(btn_k_edit); tool_k.addWidget(btn_k_del); tool_k.addStretch()
        lay_konten.addLayout(tool_k)
        
        self.tab_konten = QTableWidget()
        self.tab_konten.setColumnCount(3)
        self.tab_konten.setHorizontalHeaderLabels(["ID", "Kontoname / Topf", "Kontonummer"])
        self.tab_konten.setColumnHidden(0, True)
        self.tab_konten.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tab_konten.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tab_konten.doubleClicked.connect(self.edit_konto)
        lay_konten.addWidget(self.tab_konten)
        
        splitter.addWidget(grp_konten)
        
        # --- REGEL VERWALTUNG ---
        grp_regeln = QGroupBox("Overhead-Regelsets")
        lay_regeln = QVBoxLayout(grp_regeln)
        
        tool_r = QHBoxLayout()
        btn_r_neu = QPushButton("➕ Neue Regel"); btn_r_neu.clicked.connect(self.neu_regel)
        btn_r_edit = QPushButton("✏️ Bearbeiten"); btn_r_edit.clicked.connect(self.edit_regel)
        btn_r_del = QPushButton("🗑️ Löschen"); btn_r_del.clicked.connect(self.del_regel)
        tool_r.addWidget(btn_r_neu); tool_r.addWidget(btn_r_edit); tool_r.addWidget(btn_r_del); tool_r.addStretch()
        lay_regeln.addLayout(tool_r)
        
        self.tab_regeln = QTableWidget()
        self.tab_regeln.setColumnCount(5)
        self.tab_regeln.setHorizontalHeaderLabels(["ID", "Regel-Bezeichnung", "Gesamt Overhead", "Anteil Institut", "Anteil Verwaltung"])
        self.tab_regeln.setColumnHidden(0, True)
        self.tab_regeln.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tab_regeln.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tab_regeln.doubleClicked.connect(self.edit_regel)
        lay_regeln.addWidget(self.tab_regeln)
        
        splitter.addWidget(grp_regeln)
        main_layout.addWidget(splitter)

    def load_data(self):
        session = get_session()
        try:
            self.tab_konten.setRowCount(0)
            for k in session.query(InstitutsKonto).order_by(InstitutsKonto.name).all():
                r = self.tab_konten.rowCount()
                self.tab_konten.insertRow(r)
                self.tab_konten.setItem(r, 0, QTableWidgetItem(str(k.id)))
                self.tab_konten.setItem(r, 1, QTableWidgetItem(k.name))
                self.tab_konten.setItem(r, 2, QTableWidgetItem(k.kontonummer or "-"))
                
            self.tab_regeln.setRowCount(0)
            for reg in session.query(OverheadRegel).order_by(OverheadRegel.name).all():
                r = self.tab_regeln.rowCount()
                self.tab_regeln.insertRow(r)
                self.tab_regeln.setItem(r, 0, QTableWidgetItem(str(reg.id)))
                self.tab_regeln.setItem(r, 1, QTableWidgetItem(reg.name))
                self.tab_regeln.setItem(r, 2, QTableWidgetItem(f"{reg.gesamt_pct}%"))
                self.tab_regeln.setItem(r, 3, QTableWidgetItem(f"{reg.institut_pct}%"))
                self.tab_regeln.setItem(r, 4, QTableWidgetItem(f"{reg.verwaltung_pct}%"))
        finally:
            session.close()

    def neu_konto(self):
        if KontoBearbeitenDialog(parent=self).exec() == QDialog.DialogCode.Accepted: self.load_data()
        
    def edit_konto(self):
        row = self.tab_konten.currentRow()
        if row >= 0:
            k_id = int(self.tab_konten.item(row, 0).text())
            if KontoBearbeitenDialog(k_id, self).exec() == QDialog.DialogCode.Accepted: self.load_data()
            
    def del_konto(self):
        row = self.tab_konten.currentRow()
        if row < 0: return
        k_id = int(self.tab_konten.item(row, 0).text())
        
        if QMessageBox.question(self, "Löschen", "Konto wirklich löschen?") == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                k = session.query(InstitutsKonto).filter_by(id=k_id).first()
                if k: session.delete(k); session.commit(); self.load_data()
            except IntegrityError:
                session.rollback()
                QMessageBox.warning(self, "Fehler", "Dieses Konto kann nicht gelöscht werden, da es noch Projekten zugewiesen ist.")
            finally:
                session.close()

    def neu_regel(self):
        if RegelBearbeitenDialog(parent=self).exec() == QDialog.DialogCode.Accepted: self.load_data()
        
    def edit_regel(self):
        row = self.tab_regeln.currentRow()
        if row >= 0:
            r_id = int(self.tab_regeln.item(row, 0).text())
            if RegelBearbeitenDialog(r_id, self).exec() == QDialog.DialogCode.Accepted: self.load_data()
            
    def del_regel(self):
        row = self.tab_regeln.currentRow()
        if row < 0: return
        r_id = int(self.tab_regeln.item(row, 0).text())
        
        if QMessageBox.question(self, "Löschen", "Regel wirklich löschen?") == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                r = session.query(OverheadRegel).filter_by(id=r_id).first()
                if r: session.delete(r); session.commit(); self.load_data()
            except IntegrityError:
                session.rollback()
                QMessageBox.warning(self, "Fehler", "Diese Regel kann nicht gelöscht werden, da sie noch in Projekten verwendet wird.")
            finally:
                session.close()