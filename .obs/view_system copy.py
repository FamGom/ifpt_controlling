from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QPushButton, QLabel, QMessageBox, QDialog, 
                             QFormLayout, QDoubleSpinBox, QDateEdit, QComboBox, QDialogButtonBox)
from PyQt6.QtCore import Qt, QDate
from core.database import get_session
from core.models_old import TarifTabelle, SystemParameter

class TarifHinzufuegenDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Neuen TV-L Tarif einpflegen")
        self.resize(380, 280)
        
        layout = QFormLayout(self)
        self.combo_eg = QComboBox()
        self.combo_eg.addItems([f"E{i}" for i in range(1, 16)])
        layout.addRow("Entgeltgruppe:", self.combo_eg)
        
        self.combo_stufe = QComboBox()
        self.combo_stufe.addItems([str(i) for i in range(1, 7)])
        layout.addRow("Stufe:", self.combo_stufe)
        
        self.spin_betrag = QDoubleSpinBox()
        self.spin_betrag.setRange(1000.0, 15000.0)
        self.spin_betrag.setValue(4500.0)
        self.spin_betrag.setSingleStep(50.0)
        layout.addRow("Monatsbrutto (€):", self.spin_betrag)

        self.spin_jsz = QDoubleSpinBox()
        self.spin_jsz.setRange(0.0, 1.0)
        self.spin_jsz.setSingleStep(0.01)
        self.spin_jsz.setValue(0.5634)  # Standard für E13-E15
        layout.addRow("JSZ-Faktor (z.B. 0.5634):", self.spin_jsz)
        
        self.date_gueltig_ab = QDateEdit()
        self.date_gueltig_ab.setDate(QDate.currentDate())
        self.date_gueltig_ab.setCalendarPopup(True)
        layout.addRow("Gültig ab:", self.date_gueltig_ab)

        self.date_gueltig_bis = QDateEdit()
        self.date_gueltig_bis.setDate(QDate(2099, 12, 31))
        self.date_gueltig_bis.setCalendarPopup(True)
        layout.addRow("Gültig bis (optional):", self.date_gueltig_bis)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return {
            "entgeltgruppe": self.combo_eg.currentText(),
            "stufe": self.combo_stufe.currentText(),
            "betrag": self.spin_betrag.value(),
            "jsz": self.spin_jsz.value(),
            "gueltig_ab": self.date_gueltig_ab.date().toPyDate(),
            "gueltig_bis": self.date_gueltig_bis.date().toPyDate()
        }


class ParameterHinzufuegenDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Systemparameter hinzufügen / anpassen")
        self.resize(380, 220)
        
        layout = QFormLayout(self)
        self.combo_schluessel = QComboBox()
        self.combo_schluessel.addItems(["BBG_KV", "BBG_RV"])
        self.combo_schluessel.setEditable(True)
        layout.addRow("Schlüssel:", self.combo_schluessel)
        
        self.spin_wert = QDoubleSpinBox()
        self.spin_wert.setRange(0.0, 50000.0)
        self.spin_wert.setSingleStep(50.0)
        self.spin_wert.setValue(5175.0)
        layout.addRow("Wert (€):", self.spin_wert)
        
        self.date_gueltig_ab = QDateEdit()
        self.date_gueltig_ab.setDate(QDate(2026, 1, 1))
        self.date_gueltig_ab.setCalendarPopup(True)
        layout.addRow("Gültig ab:", self.date_gueltig_ab)

        self.date_gueltig_bis = QDateEdit()
        self.date_gueltig_bis.setDate(QDate(2099, 12, 31))
        self.date_gueltig_bis.setCalendarPopup(True)
        layout.addRow("Gültig bis (optional):", self.date_gueltig_bis)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return {
            "schluessel": self.combo_schluessel.currentText(),
            "wert": self.spin_wert.value(),
            "gueltig_ab": self.date_gueltig_ab.date().toPyDate(),
            "gueltig_bis": self.date_gueltig_bis.date().toPyDate()
        }


class SystemView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        title = QLabel("System- & Tarifverwaltung (Admin-Bereich)")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2C3E50;")
        main_layout.addWidget(title)

        self.tabs = QTabWidget()
        
        # --- TAB 1: TV-L Entgelttabellen ---
        tab_tvl = QWidget()
        layout_tvl = QVBoxLayout(tab_tvl)
        
        toolbar_tvl = QHBoxLayout()
        btn_add_tarif = QPushButton("➕ Neuen Tarif hinzufügen")
        btn_add_tarif.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold;")
        btn_add_tarif.clicked.connect(self.neuen_tarif_hinzufuegen)
        
        btn_del_tarif = QPushButton("🗑️ Ausgewählten Tarif löschen")
        btn_del_tarif.setStyleSheet("background-color: #C0392B; color: white;")
        btn_del_tarif.clicked.connect(self.tarif_loeschen)
        
        btn_refresh = QPushButton("🔄 Aktualisieren")
        btn_refresh.clicked.connect(self.load_data)
        
        toolbar_tvl.addWidget(btn_add_tarif)
        toolbar_tvl.addWidget(btn_del_tarif)
        toolbar_tvl.addStretch()
        toolbar_tvl.addWidget(btn_refresh)
        layout_tvl.addLayout(toolbar_tvl)
        
        self.table_tvl = QTableWidget()
        self.spalten_tvl = ["ID", "Entgeltgruppe", "Stufe", "Monatsbrutto (€)", "JSZ-Faktor", "Gültig ab", "Gültig bis"]
        self.table_tvl.setColumnCount(len(self.spalten_tvl))
        self.table_tvl.setHorizontalHeaderLabels(self.spalten_tvl)
        self.table_tvl.setColumnHidden(0, True)
        self.table_tvl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_tvl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_tvl.setAlternatingRowColors(True)
        layout_tvl.addWidget(self.table_tvl)
        
        self.tabs.addTab(tab_tvl, "TV-L Entgelttabellen & JSZ")

        # --- TAB 2: Systemparameter & Grenzen mit vollständiger Historie ---
        tab_params = QWidget()
        layout_params = QVBoxLayout(tab_params)
        
        toolbar_params = QHBoxLayout()
        btn_add_param = QPushButton("➕ Parameter hinzufügen / anpassen")
        btn_add_param.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold;")
        btn_add_param.clicked.connect(self.neuen_parameter_hinzufuegen)
        
        btn_del_param = QPushButton("🗑️ Ausgewählten Parameter löschen")
        btn_del_param.setStyleSheet("background-color: #C0392B; color: white;")
        btn_del_param.clicked.connect(self.parameter_loeschen)
        
        toolbar_params.addWidget(btn_add_param)
        toolbar_params.addWidget(btn_del_param)
        toolbar_params.addStretch()
        layout_params.addLayout(toolbar_params)
        
        self.table_params = QTableWidget()
        self.spalten_params = ["ID", "Schlüssel", "Wert (€)", "Gültig ab", "Gültig bis"]
        self.table_params.setColumnCount(len(self.spalten_params))
        self.table_params.setHorizontalHeaderLabels(self.spalten_params)
        self.table_params.setColumnHidden(0, True)
        self.table_params.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_params.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_params.setAlternatingRowColors(True)
        layout_params.addWidget(self.table_params)
        
        self.tabs.addTab(tab_params, "Systemparameter & Grenzen (Historie)")

        main_layout.addWidget(self.tabs)

    def load_data(self):
        session = get_session()
        try:
            # 1. Tarife laden
            self.table_tvl.setRowCount(0)
            tarife = session.query(TarifTabelle).order_by(TarifTabelle.entgeltgruppe, TarifTabelle.stufe).all()
            for t in tarife:
                row = self.table_tvl.rowCount()
                self.table_tvl.insertRow(row)
                self.table_tvl.setItem(row, 0, QTableWidgetItem(str(t.id)))
                self.table_tvl.setItem(row, 1, QTableWidgetItem(str(t.entgeltgruppe)))
                self.table_tvl.setItem(row, 2, QTableWidgetItem(str(t.stufe)))
                
                betrag_str = f"{t.betrag_euro:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
                item_b = QTableWidgetItem(betrag_str)
                item_b.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_tvl.setItem(row, 3, item_b)

                item_jsz = QTableWidgetItem(f"{t.jsz_prozent:.4f}" if t.jsz_prozent else "0.5634")
                item_jsz.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_tvl.setItem(row, 4, item_jsz)
                
                gueltig_ab = t.gueltig_ab.strftime('%d.%m.%Y') if t.gueltig_ab else "-"
                gueltig_bis = t.gueltig_bis.strftime('%d.%m.%Y') if t.gueltig_bis else "unbefristet"
                self.table_tvl.setItem(row, 5, QTableWidgetItem(gueltig_ab))
                self.table_tvl.setItem(row, 6, QTableWidgetItem(gueltig_bis))

            # 2. Systemparameter laden
            self.table_params.setRowCount(0)
            params = session.query(SystemParameter).order_by(SystemParameter.schluessel, SystemParameter.gueltig_ab).all()
            for p in params:
                row = self.table_params.rowCount()
                self.table_params.insertRow(row)
                self.table_params.setItem(row, 0, QTableWidgetItem(str(p.id)))
                self.table_params.setItem(row, 1, QTableWidgetItem(str(p.schluessel)))
                
                wert_str = f"{p.wert:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
                item_w = QTableWidgetItem(wert_str)
                item_w.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_params.setItem(row, 2, item_w)

                gueltig_ab = p.gueltig_ab.strftime('%d.%m.%Y') if p.gueltig_ab else "-"
                gueltig_bis = p.gueltig_bis.strftime('%d.%m.%Y') if p.gueltig_bis else "unbefristet"
                self.table_params.setItem(row, 3, QTableWidgetItem(gueltig_ab))
                self.table_params.setItem(row, 4, QTableWidgetItem(gueltig_bis))

        finally:
            session.close()

    def neuen_tarif_hinzufuegen(self):
        dialog = TarifHinzufuegenDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            session = get_session()
            try:
                neuer_tarif = TarifTabelle(
                    entgeltgruppe=data["entgeltgruppe"],
                    stufe=data["stufe"],
                    betrag_euro=data["betrag"],
                    jsz_prozent=data["jsz"],
                    gueltig_ab=data["gueltig_ab"],
                    gueltig_bis=data["gueltig_bis"]
                )
                session.add(neuer_tarif)
                session.commit()
                self.load_data()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Fehler", f"Fehler:\n{str(e)}")
            finally:
                session.close()

    def tarif_loeschen(self):
        row = self.table_tvl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Hinweis", "Bitte Tarif auswählen.")
            return
        tarif_id = int(self.table_tvl.item(row, 0).text())
        session = get_session()
        try:
            tarif = session.query(TarifTabelle).filter_by(id=tarif_id).first()
            if tarif:
                session.delete(tarif)
                session.commit()
                self.load_data()
        finally:
            session.close()

    def neuen_parameter_hinzufuegen(self):
        dialog = ParameterHinzufuegenDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            session = get_session()
            try:
                param = SystemParameter(
                    schluessel=data["schluessel"],
                    wert=data["wert"],
                    gueltig_ab=data["gueltig_ab"],
                    gueltig_bis=data["gueltig_bis"]
                )
                session.add(param)
                session.commit()
                self.load_data()
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Fehler", f"Fehler:\n{str(e)}")
            finally:
                session.close()

    def parameter_loeschen(self):
        row = self.table_params.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Hinweis", "Bitte Parameter auswählen.")
            return
        param_id = int(self.table_params.item(row, 0).text())
        session = get_session()
        try:
            param = session.query(SystemParameter).filter_by(id=param_id).first()
            if param:
                session.delete(param)
                session.commit()
                self.load_data()
        finally:
            session.close()