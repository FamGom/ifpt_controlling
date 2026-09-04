import calendar
from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, 
                             QHeaderView, QLabel, QMessageBox, QDialog, QFormLayout, 
                             QDateEdit, QDoubleSpinBox, QDialogButtonBox, QTabWidget)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models import Mitarbeiter, Projekt, ProjektStatus, Zuweisung, ZuweisungsTyp

# ==========================================
# DIALOG ZUM ANLEGEN/BEARBEITEN (Für Listenansicht)
# ==========================================
class ZuweisungDialog(QDialog):
    """Dialog zum Anlegen oder Bearbeiten einer Personal-Projekt-Zuweisung"""
    def __init__(self, zuweisung_id=None, parent=None):
        super().__init__(parent)
        self.zuweisung_id = zuweisung_id
        self.setWindowTitle("Zuweisung bearbeiten" if zuweisung_id else "Neue Zuweisung erstellen")
        self.resize(450, 350)
        
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setVerticalSpacing(12)
        
        self.combo_projekt = QComboBox()
        layout.addRow("Projekt:", self.combo_projekt)
        
        self.combo_mitarbeiter = QComboBox()
        layout.addRow("Mitarbeiter:", self.combo_mitarbeiter)
        
        self.date_start = QDateEdit()
        self.date_start.setDate(QDate.currentDate())
        self.date_start.setCalendarPopup(True)
        layout.addRow("Startdatum:", self.date_start)
        
        self.date_ende = QDateEdit()
        self.date_ende.setDate(QDate.currentDate().addYears(1))
        self.date_ende.setCalendarPopup(True)
        layout.addRow("Enddatum:", self.date_ende)
        
        self.spin_anteil = QDoubleSpinBox()
        self.spin_anteil.setRange(0.0, 100.0)
        self.spin_anteil.setSingleStep(5.0)
        self.spin_anteil.setValue(100.0)
        self.spin_anteil.setSuffix(" %")
        layout.addRow("Stellenanteil:", self.spin_anteil)
        
        self.combo_typ = QComboBox()
        for typ in ZuweisungsTyp:
            self.combo_typ.addItem(typ.value, typ)
        layout.addRow("Art der Zuweisung:", self.combo_typ)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.daten_speichern)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.lade_dropdowns()
        
        if self.zuweisung_id:
            self.lade_zuweisung_daten()

    def lade_dropdowns(self):
        session = get_session()
        try:
            for p in session.query(Projekt).order_by(Projekt.projektname).all():
                self.combo_projekt.addItem(p.projektname, p.id)
            for m in session.query(Mitarbeiter).order_by(Mitarbeiter.nachname).all():
                self.combo_mitarbeiter.addItem(f"{m.nachname}, {m.vorname}", m.id)
        finally:
            session.close()

    def lade_zuweisung_daten(self):
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
                
                idx_typ = self.combo_typ.findData(z.typ)
                if idx_typ >= 0: self.combo_typ.setCurrentIndex(idx_typ)
        finally:
            session.close()

    def daten_speichern(self):
        if self.combo_projekt.currentIndex() < 0 or self.combo_mitarbeiter.currentIndex() < 0:
            QMessageBox.warning(self, "Fehler", "Bitte Projekt und Mitarbeiter auswählen.")
            return
            
        start_date = self.date_start.date().toPyDate()
        end_date = self.date_ende.date().toPyDate()
        
        if end_date < start_date:
            QMessageBox.warning(self, "Fehler", "Das Enddatum darf nicht vor dem Startdatum liegen.")
            return

        session = get_session()
        try:
            m_id = self.combo_mitarbeiter.currentData()
            neuer_anteil = self.spin_anteil.value() / 100.0
            
            # ÜBERBUCHUNGS-SCHUTZ
            ueberschneidungen = session.query(Zuweisung).filter(
                Zuweisung.mitarbeiter_id == m_id,
                Zuweisung.start_datum <= end_date,
                Zuweisung.end_datum >= start_date
            ).all()
            aktuelle_auslastung = sum([o.anteil_pct for o in ueberschneidungen if o.id != self.zuweisung_id])
            
            if aktuelle_auslastung + neuer_anteil > 1.001:
                warn_msg = (
                    f"⚠️ WARNUNG: Überbuchung erkannt!\n\n"
                    f"Der Mitarbeiter ist in diesem Zeitraum bereits mit {aktuelle_auslastung*100:.1f} % verplant.\n"
                    f"Mit dieser Zuweisung steigt die Auslastung auf {(aktuelle_auslastung + neuer_anteil)*100:.1f} %.\n\n"
                    f"Möchten Sie trotzdem speichern?"
                )
                if QMessageBox.warning(self, "Kapazitätswarnung", warn_msg, 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                    return

            if self.zuweisung_id:
                z = session.query(Zuweisung).filter_by(id=self.zuweisung_id).first()
            else:
                z = Zuweisung()
                session.add(z)
                
            z.projekt_id = self.combo_projekt.currentData()
            z.mitarbeiter_id = m_id
            z.start_datum = start_date
            z.end_datum = end_date
            z.anteil_pct = neuer_anteil
            z.typ = self.combo_typ.currentData()
            
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", f"Fehler beim Speichern:\n{str(e)}")
        finally:
            session.close()


# ==========================================
# ANSI 1: DIE NEUE LISTEN-ANSICHT
# ==========================================
class MatrixListView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neue Zuweisung")
        btn_add.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self.zuweisung_hinzufuegen)
        
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.setStyleSheet("background-color: #2980B9; color: white; padding: 6px;")
        btn_edit.clicked.connect(self.zuweisung_bearbeiten)
        
        btn_del = QPushButton("🗑️ Löschen")
        btn_del.setStyleSheet("background-color: #C0392B; color: white; padding: 6px;")
        btn_del.clicked.connect(self.zuweisung_loeschen)
        
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_del)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.spalten = ["ID", "Projekt", "Mitarbeiter", "Zeitraum", "Anteil (%)", "Status"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.zuweisung_bearbeiten)
        layout.addWidget(self.table)

    def load_matrix(self):
        session = get_session()
        self.table.setRowCount(0)
        try:
            zuweisungen = session.query(Zuweisung).join(Projekt).join(Mitarbeiter).order_by(Projekt.projektname, Mitarbeiter.nachname).all()
            for z in zuweisungen:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(z.id)))
                self.table.setItem(row, 1, QTableWidgetItem(z.projekt.projektname if z.projekt else "Gelöscht"))
                self.table.setItem(row, 2, QTableWidgetItem(f"{z.mitarbeiter.nachname}, {z.mitarbeiter.vorname}" if z.mitarbeiter else "Gelöscht"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{z.start_datum.strftime('%m/%Y')} - {z.end_datum.strftime('%m/%Y')}"))
                
                anteil_item = QTableWidgetItem(f"{z.anteil_pct * 100:.1f} %")
                if z.anteil_pct > 1.0: anteil_item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(row, 4, anteil_item)
                self.table.setItem(row, 5, QTableWidgetItem(z.typ.value if hasattr(z.typ, 'value') else str(z.typ)))
        finally:
            session.close()

    def zuweisung_hinzufuegen(self):
        dialog = ZuweisungDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_matrix()

    def zuweisung_bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        dialog = ZuweisungDialog(zuweisung_id=int(self.table.item(row, 0).text()), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_matrix()

    def zuweisung_loeschen(self):
        row = self.table.currentRow()
        if row < 0: return
        z_id = int(self.table.item(row, 0).text())
        if QMessageBox.question(self, "Löschen bestätigen", "Zuweisung wirklich löschen?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                z = session.query(Zuweisung).filter_by(id=z_id).first()
                if z:
                    session.delete(z)
                    session.commit()
                    self.load_matrix()
            finally:
                session.close()


# ==========================================
# ANSI 2: DIE ALTE GANTT-MATRIX (Korrigiert!)
# ==========================================
class MatrixGanttView(QWidget):
    def __init__(self):
        super().__init__()
        self.mitarbeiter_liste = []
        self.projekte_alle = []
        self.start_jahr = 2026
        self.end_jahr = 2027
        self.monate_gesamt = 0
        self.spalten_namen = []
        self.setup_ui()

    def load_stammdaten(self):
        session = get_session()
        self.mitarbeiter_liste.clear()
        self.projekte_alle.clear()
        try:
            self.mitarbeiter_liste = session.query(Mitarbeiter).all()
            for p in session.query(Projekt).all():
                self.projekte_alle.append({"id": p.id, "name": p.projektname, "status": p.status})
        finally:
            session.close()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        toolbar_time = QHBoxLayout()
        toolbar_time.addWidget(QLabel("<b>Planungszeitraum:</b>"))
        self.spin_start = QSpinBox(); self.spin_start.setRange(2020, 2040); self.spin_start.setValue(self.start_jahr)
        self.spin_end = QSpinBox(); self.spin_end.setRange(2020, 2040); self.spin_end.setValue(self.end_jahr)
        btn_apply_time = QPushButton("Zeitraum anwenden & Laden")
        btn_apply_time.clicked.connect(self.apply_time_range)
        toolbar_time.addWidget(QLabel("Von:")); toolbar_time.addWidget(self.spin_start)
        toolbar_time.addWidget(QLabel("Bis:")); toolbar_time.addWidget(self.spin_end)
        toolbar_time.addWidget(btn_apply_time)
        toolbar_time.addStretch()
        layout.addLayout(toolbar_time)

        toolbar_actions = QHBoxLayout()
        btn_add_row = QPushButton("➕ Neue Zeile")
        btn_add_row.clicked.connect(self.add_matrix_row)
        btn_validate = QPushButton("🔍 Matrix prüfen")
        btn_validate.clicked.connect(self.validate_matrix)
        btn_save = QPushButton("💾 Speichern")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_matrix)
        btn_export = QPushButton("📄 Stammblatt (PDF)")
        btn_export.setStyleSheet("background-color: #2980B9; color: white;")
        btn_export.clicked.connect(self.export_pdf_for_selected_row)
        btn_export_gantt = QPushButton("📊 Matrix als Gantt (PDF)")
        btn_export_gantt.setStyleSheet("background-color: #8E44AD; color: white;")
        btn_export_gantt.clicked.connect(self.export_gantt_pdf)
        toolbar_actions.addWidget(btn_add_row); toolbar_actions.addWidget(btn_validate); toolbar_actions.addWidget(btn_save)
        toolbar_actions.addWidget(btn_export); toolbar_actions.addWidget(btn_export_gantt)
        toolbar_actions.addStretch()
        layout.addLayout(toolbar_actions)

        self.table = QTableWidget()
        layout.addWidget(self.table)
        
        # WICHTIG: Hier fehlte der Initial-Aufruf!
        self.apply_time_range() 

    def apply_time_range(self):
        self.load_stammdaten()
        self.start_jahr = self.spin_start.value()
        self.end_jahr = self.spin_end.value()
        if self.start_jahr > self.end_jahr:
            QMessageBox.warning(self, "Fehler", "Startjahr darf nicht nach Endjahr liegen.")
            return

        self.spalten_namen = ["MA-Name", "Status", "Anteil %", "Fehler"]
        for jahr in range(self.start_jahr, self.end_jahr + 1):
            for monat in range(1, 13):
                self.spalten_namen.append(f"{monat:02d}/{str(jahr)[-2:]}")
                
        self.monate_gesamt = len(self.spalten_namen) - 4
        self.table.clear()
        self.table.setColumnCount(len(self.spalten_namen))
        self.table.setHorizontalHeaderLabels(self.spalten_namen)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(4, len(self.spalten_namen)): 
            self.table.setColumnWidth(i, 90)
            
        self.load_matrix_from_db()

    def get_date_from_col(self, col_idx):
        monate_seit_start = col_idx - 4
        jahr = self.start_jahr + (monate_seit_start // 12)
        monat = (monate_seit_start % 12) + 1
        return date(jahr, monat, 1)

    def load_matrix_from_db(self):
        session = get_session()
        self.table.setRowCount(0)
        try:
            zuweisungen = session.query(Zuweisung).filter(
                Zuweisung.end_datum >= date(self.start_jahr, 1, 1),
                Zuweisung.start_datum <= date(self.end_jahr, 12, 31)
            ).all()
            
            if not zuweisungen:
                self.add_matrix_row()
                return
                
            zeilen_daten = {} 
            for z in zuweisungen:
                key = (z.mitarbeiter_id, z.typ, int(z.anteil_pct * 100))
                if key not in zeilen_daten:
                    zeilen_daten[key] = {col: None for col in range(4, 4 + self.monate_gesamt)}
                    
                for col in range(4, 4 + self.monate_gesamt):
                    col_date = self.get_date_from_col(col)
                    col_end_date = date(col_date.year, col_date.month, calendar.monthrange(col_date.year, col_date.month)[1])
                    if z.start_datum <= col_end_date and z.end_datum >= col_date:
                        zeilen_daten[key][col] = z.projekt_id
                        
            for (ma_id, typ, anteil), monate in zeilen_daten.items():
                self.add_matrix_row(ma_id, typ, anteil, monate)
            self.validate_matrix()
        finally:
            session.close()

    def add_matrix_row(self, ma_id=None, typ=ZuweisungsTyp.PLANUNG, anteil=100, monate_daten=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        c_ma = QComboBox(); c_ma.addItem("-", None)
        for ma in self.mitarbeiter_liste: c_ma.addItem(f"{ma.nachname}, {ma.vorname}", ma.id)
        if ma_id: c_ma.setCurrentIndex(c_ma.findData(ma_id))
        self.table.setCellWidget(row, 0, c_ma)
        
        # Dynamisch die Enums aus der Datenbank nutzen
        c_status = QComboBox()
        for t in ZuweisungsTyp:
            c_status.addItem(t.value, t)
        idx_typ = c_status.findData(typ)
        if idx_typ >= 0: c_status.setCurrentIndex(idx_typ)
        self.table.setCellWidget(row, 1, c_status)
        
        s_anteil = QSpinBox(); s_anteil.setRange(1, 100); s_anteil.setValue(anteil)
        self.table.setCellWidget(row, 2, s_anteil)
        
        self.table.setItem(row, 3, QTableWidgetItem(""))
        
        monats_combos = []
        for col in range(4, 4 + self.monate_gesamt):
            c_proj = QComboBox()
            self.populate_project_combo(c_proj)
            if monate_daten and monate_daten.get(col):
                c_proj.setCurrentIndex(c_proj.findData(monate_daten[col]))
            self.table.setCellWidget(row, col, c_proj)
            monats_combos.append(c_proj)
            
        c_status.currentIndexChanged.connect(lambda _, m_cb=monats_combos: self.update_row_projects(m_cb))

    def populate_project_combo(self, combo):
        combo.clear(); combo.addItem("-", None)
        # HIER WAR DER FEHLER: Es werden jetzt IMMER alle Projekte angezeigt.
        for p in self.projekte_alle: 
            combo.addItem(p["name"][:12]+"...", p["id"])

    def update_row_projects(self, monats_combos):
        for combo in monats_combos:
            current_id = combo.currentData()
            self.populate_project_combo(combo)
            idx = combo.findData(current_id)
            if idx >= 0: combo.setCurrentIndex(idx)

    def validate_matrix(self):
        # High-Contrast Gantt Farben für den Dark Mode (kräftigere Farben, schwarzer Text)
        farben = ["#5DADE2", "#58D68D", "#F4D03F", "#EB984E", "#AF7AC5"] 
        ma_monats_summen = {} 
        for row in range(self.table.rowCount()):
            ma_id = self.table.cellWidget(row, 0).currentData()
            anteil = self.table.cellWidget(row, 2).value()
            if ma_id is None: continue
            if ma_id not in ma_monats_summen: ma_monats_summen[ma_id] = {col: 0 for col in range(4, 4+self.monate_gesamt)}
            proj_farben = {}; f_idx = 0
            for col in range(4, 4 + self.monate_gesamt):
                combo = self.table.cellWidget(row, col)
                pid = combo.currentData()
                pid_links = self.table.cellWidget(row, col-1).currentData() if col > 4 else None
                pid_rechts = self.table.cellWidget(row, col+1).currentData() if col < 3+self.monate_gesamt else None
                
                if pid:
                    ma_monats_summen[ma_id][col] += anteil
                    if pid not in proj_farben:
                        proj_farben[pid] = farben[f_idx % len(farben)]
                        f_idx += 1
                    farbe = proj_farben[pid]
                    
                    border_css = "border: 1px solid #777;"
                    if pid == pid_links and pid == pid_rechts: border_css = "border-top: 1px solid #777; border-bottom: 1px solid #777; border-left: none; border-right: none;"
                    elif pid == pid_links: border_css = "border-top: 1px solid #777; border-bottom: 1px solid #777; border-left: none; border-right: 1px solid #777;"
                    elif pid == pid_rechts: border_css = "border-top: 1px solid #777; border-bottom: 1px solid #777; border-left: 1px solid #777; border-right: none;"
                        
                    combo.setStyleSheet(f"QComboBox {{ background-color: {farbe}; color: #000000; {border_css} margin: 0px; font-weight: bold; }}")
                else:
                    combo.setStyleSheet("")

    def save_matrix(self):
        session = get_session()
        try:
            session.query(Zuweisung).filter(
                Zuweisung.start_datum >= date(self.start_jahr, 1, 1),
                Zuweisung.end_datum <= date(self.end_jahr, 12, 31)
            ).delete()

            for row in range(self.table.rowCount()):
                ma_id = self.table.cellWidget(row, 0).currentData()
                if not ma_id: continue
                typ = self.table.cellWidget(row, 1).currentData()
                anteil = self.table.cellWidget(row, 2).value() / 100.0

                current_pid = None; start_col = None

                for col in range(4, 5 + self.monate_gesamt):
                    pid = self.table.cellWidget(row, col).currentData() if col < 4 + self.monate_gesamt else None
                    if pid != current_pid:
                        if current_pid is not None:
                            start_date = self.get_date_from_col(start_col)
                            end_date_temp = self.get_date_from_col(col - 1)
                            end_date = date(end_date_temp.year, end_date_temp.month, calendar.monthrange(end_date_temp.year, end_date_temp.month)[1])
                            session.add(Zuweisung(mitarbeiter_id=ma_id, projekt_id=current_pid, typ=typ, anteil_pct=anteil, start_datum=start_date, end_datum=end_date))
                        current_pid = pid; start_col = col

            session.commit()
            QMessageBox.information(self, "Gespeichert", "Matrix im gewählten Zeitraum erfolgreich gespeichert!")
        finally:
            session.close()

    def export_pdf_for_selected_row(self):
        try:
            from gui.components.pdf_exporter import export_mitarbeiter_pdf
            row = self.table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Hinweis", "Bitte klicken Sie zuerst in eine Zeile.")
                return
            ma_id = self.table.cellWidget(row, 0).currentData()
            if ma_id is None:
                QMessageBox.warning(self, "Hinweis", "In dieser Zeile ist kein Mitarbeiter ausgewählt.")
                return
            export_mitarbeiter_pdf(self, ma_id, self.spin_start.value())
        except ImportError:
            QMessageBox.warning(self, "Hinweis", "Das PDF-Export Modul ist nicht verfügbar.")

    def export_gantt_pdf(self):
        try:
            from gui.components.pdf_exporter import export_matrix_gantt_pdf
            export_matrix_gantt_pdf(self, self.table, self.start_jahr, self.end_jahr, self.spalten_namen)
        except ImportError:
            QMessageBox.warning(self, "Hinweis", "Das PDF-Export Modul ist nicht verfügbar.")


# ==========================================
# HAUPT-WIDGET: HÄLT BEIDE TABS ZUSAMMEN
# ==========================================
class MatrixMainView(QWidget):
    """Container, der sowohl die Gantt-Matrix als auch die Listenansicht als Tabs beinhaltet."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Instanziere beide Ansichten
        self.gantt_view = MatrixGanttView()
        self.list_view = MatrixListView()
        
        self.tabs.addTab(self.gantt_view, "📊 Gantt-Matrix (Master)")
        self.tabs.addTab(self.list_view, "📋 Listen-Ansicht (Details)")
        
        # Signal für Tab-Wechsel
        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        """Aktualisiert die jeweils sichtbare Ansicht mit den neuesten Datenbankwerten."""
        if index == 0:
            self.gantt_view.apply_time_range() 
        else:
            self.list_view.load_matrix()