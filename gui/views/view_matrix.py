import calendar
from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, 
                             QHeaderView, QLabel, QMessageBox, QDialog, QFormLayout, 
                             QDateEdit, QDoubleSpinBox, QDialogButtonBox, QTabWidget,
                             QMenu)
from PyQt6.QtCore import Qt, QDate

from core.database import get_session
from core.models import Mitarbeiter, Projekt, ProjektStatus, Zuweisung, ZuweisungsTyp, Arbeitszeitverlauf

# ==========================================
# DIALOG ZUM ANLEGEN/BEARBEITEN 
# ==========================================
class ZuweisungDialog(QDialog):
    def __init__(self, zuweisung_id=None, parent=None):
        super().__init__(parent)
        self.zuweisung_id = zuweisung_id
        self.setWindowTitle("Zuweisung bearbeiten" if zuweisung_id else "Neue Zuweisung erstellen")
        self.resize(450, 350)
        
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
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
        self.combo_typ.addItem("Vertrag", ZuweisungsTyp.VERTRAG)
        self.combo_typ.addItem("Planung", ZuweisungsTyp.PLANUNG)
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
        start_date = self.date_start.date().toPyDate()
        end_date = self.date_ende.date().toPyDate()
        p_id = self.combo_projekt.currentData()
        m_id = self.combo_mitarbeiter.currentData()
        gewaehlter_typ = self.combo_typ.currentData()
        neuer_anteil = self.spin_anteil.value() / 100.0
        
        if end_date < start_date:
            QMessageBox.warning(self, "Fehler", "Enddatum darf nicht vor Startdatum liegen.")
            return

        session = get_session()
        try:
            projekt = session.query(Projekt).filter_by(id=p_id).first()
            if not projekt: return

            if start_date < projekt.projektbeginn or end_date > projekt.projektende:
                QMessageBox.critical(self, "Laufzeitfehler", "Die Zuweisung liegt außerhalb der Projektlaufzeit!")
                return
                
            if self.zuweisung_id:
                z = session.query(Zuweisung).filter_by(id=self.zuweisung_id).first()
            else:
                z = Zuweisung()
                session.add(z)
                
            z.projekt_id = p_id
            z.mitarbeiter_id = m_id
            z.start_datum = start_date
            z.end_datum = end_date
            z.anteil_pct = neuer_anteil
            z.typ = gewaehlter_typ
            
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", f"Fehler:\n{str(e)}")
        finally:
            session.close()

# ==========================================
# ANSI 1: LISTEN-ANSICHT
# ==========================================
class MatrixListView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neue Plan-Zuweisung")
        btn_add.clicked.connect(self.zuweisung_hinzufuegen)
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.clicked.connect(self.zuweisung_bearbeiten)
        btn_del = QPushButton("🗑️ Löschen")
        btn_del.clicked.connect(self.zuweisung_loeschen)
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_edit); toolbar.addWidget(btn_del); toolbar.addStretch()
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
            zuweisungen = session.query(Zuweisung).join(Projekt).join(Mitarbeiter).filter(
                Zuweisung.typ.in_([ZuweisungsTyp.VERTRAG, ZuweisungsTyp.PLANUNG])
            ).order_by(Projekt.projektname, Mitarbeiter.nachname).all()
            for z in zuweisungen:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(z.id)))
                self.table.setItem(row, 1, QTableWidgetItem(z.projekt.projektname if z.projekt else "Gelöscht"))
                self.table.setItem(row, 2, QTableWidgetItem(f"{z.mitarbeiter.nachname}, {z.mitarbeiter.vorname}" if z.mitarbeiter else "Gelöscht"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{z.start_datum.strftime('%m/%Y')} - {z.end_datum.strftime('%m/%Y')}"))
                self.table.setItem(row, 4, QTableWidgetItem(f"{z.anteil_pct * 100:.1f} %"))
                self.table.setItem(row, 5, QTableWidgetItem("Vertrag" if z.typ == ZuweisungsTyp.VERTRAG else "Planung"))
        finally:
            session.close()

    def zuweisung_hinzufuegen(self):
        dialog = ZuweisungDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.load_matrix()

    def zuweisung_bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        dialog = ZuweisungDialog(zuweisung_id=int(self.table.item(row, 0).text()), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.load_matrix()

    def zuweisung_loeschen(self):
        row = self.table.currentRow()
        if row < 0: return
        if QMessageBox.question(self, "Löschen", "Zuweisung löschen?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                z = session.query(Zuweisung).filter_by(id=int(self.table.item(row, 0).text())).first()
                if z: session.delete(z); session.commit(); self.load_matrix()
            finally:
                session.close()

# ==========================================
# ANSI 2: GANTT-MATRIX (MIT INTELLIGENTER SUMMIERUNG)
# ==========================================
class MatrixGanttView(QWidget):
    def __init__(self):
        super().__init__()
        self.mitarbeiter_liste = []
        self.mitarbeiter_daten = {} 
        self.projekte_alle = []
        self.start_jahr = 2026
        self.end_jahr = 2027
        self.monate_gesamt = 0
        self.spalten_namen = []
        self.setup_ui()

    def load_stammdaten(self):
        session = get_session()
        self.mitarbeiter_liste.clear()
        self.mitarbeiter_daten.clear()
        self.projekte_alle.clear()
        try:
            for m in session.query(Mitarbeiter).all():
                self.mitarbeiter_liste.append(m)
                
                # Wir laden alle Teilzeit-Modelle dieses Mitarbeiters
                az_verlaeufe = session.query(Arbeitszeitverlauf).filter_by(mitarbeiter_id=m.id).all()
                
                self.mitarbeiter_daten[m.id] = {
                    "start": m.am_ifpt_seit,
                    "end": m.geplanter_abgang,
                    "name": f"{m.nachname}, {m.vorname}",
                    "arbeitszeiten": az_verlaeufe
                }
            for p in session.query(Projekt).all():
                self.projekte_alle.append({
                    "id": p.id, "name": p.projektname, "status": p.status,
                    "start": p.projektbeginn, "end": p.projektende
                })
        finally:
            session.close()

    def get_target_capacity(self, ma_id, check_date):
        """Ermittelt die individuelle Ziel-Auslastung (z.B. 50% bei Teilzeit) für einen bestimmten Monat."""
        if not ma_id or ma_id not in self.mitarbeiter_daten: return 100.0
        az_verlaeufe = self.mitarbeiter_daten[ma_id]["arbeitszeiten"]
        
        # Den letzten Tag des Monats für die Prüfung verwenden
        check_end_date = date(check_date.year, check_date.month, calendar.monthrange(check_date.year, check_date.month)[1])
        
        for az in az_verlaeufe:
            if az.gueltig_ab <= check_end_date:
                if not az.gueltig_bis or az.gueltig_bis >= check_date:
                    return az.anteil_pct * 100.0
        
        # Standard: 100%
        return 100.0

    def setup_ui(self):
        layout = QVBoxLayout(self)
        toolbar_time = QHBoxLayout()
        self.spin_start = QSpinBox(); self.spin_start.setRange(2020, 2040); self.spin_start.setValue(self.start_jahr)
        self.spin_end = QSpinBox(); self.spin_end.setRange(2020, 2040); self.spin_end.setValue(self.end_jahr)
        btn_apply = QPushButton("Zeitraum anwenden & Laden")
        btn_apply.clicked.connect(self.apply_time_range)
        toolbar_time.addWidget(QLabel("Von:")); toolbar_time.addWidget(self.spin_start)
        toolbar_time.addWidget(QLabel("Bis:")); toolbar_time.addWidget(self.spin_end)
        toolbar_time.addWidget(btn_apply); toolbar_time.addStretch()
        layout.addLayout(toolbar_time)

        toolbar_actions = QHBoxLayout()
        btn_add = QPushButton("➕ Neue Zeile"); btn_add.clicked.connect(self.add_matrix_row)
        btn_val = QPushButton("🔍 Matrix auswerten (Fehler & Lücken)")
        btn_val.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold;")
        btn_val.clicked.connect(self.validate_and_report)
        btn_save = QPushButton("💾 Speichern")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_matrix)
        toolbar_actions.addWidget(btn_add); toolbar_actions.addWidget(btn_val); toolbar_actions.addWidget(btn_save)
        toolbar_actions.addStretch()
        layout.addLayout(toolbar_actions)

        self.table = QTableWidget()
        layout.addWidget(self.table)
        self.apply_time_range()

    def apply_time_range(self):
        self.load_stammdaten()
        self.start_jahr = self.spin_start.value()
        self.end_jahr = self.spin_end.value()
        if self.start_jahr > self.end_jahr: return
        self.spalten_namen = ["MA-Name", "Status", "Anteil %", "Zell-Info"]
        for jahr in range(self.start_jahr, self.end_jahr + 1):
            for monat in range(1, 13):
                self.spalten_namen.append(f"{monat:02d}/{str(jahr)[-2:]}")
        self.monate_gesamt = len(self.spalten_namen) - 4
        self.table.clear()
        self.table.setColumnCount(len(self.spalten_namen))
        self.table.setHorizontalHeaderLabels(self.spalten_namen)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(4, len(self.spalten_namen)): self.table.setColumnWidth(i, 90)
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
                Zuweisung.start_datum <= date(self.end_jahr, 12, 31),
                Zuweisung.typ.in_([ZuweisungsTyp.VERTRAG, ZuweisungsTyp.PLANUNG])
            ).all()
            if not zuweisungen:
                self.add_matrix_row()
                return
            zeilen_daten = {} 
            for z in zuweisungen:
                key = (z.mitarbeiter_id, z.typ, int(z.anteil_pct * 100))
                if key not in zeilen_daten: zeilen_daten[key] = {col: None for col in range(4, 4 + self.monate_gesamt)}
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

    def get_cell_pos(self, widget):
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                if self.table.cellWidget(r, c) == widget: return r, c
        return -1, -1

    def add_matrix_row(self, ma_id=None, typ=ZuweisungsTyp.PLANUNG, anteil=100, monate_daten=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        c_ma = QComboBox(); c_ma.addItem("-", None)
        for ma in self.mitarbeiter_liste: c_ma.addItem(f"{ma.nachname}, {ma.vorname}", ma.id)
        if ma_id: c_ma.setCurrentIndex(c_ma.findData(ma_id))
        self.table.setCellWidget(row, 0, c_ma)
        
        c_status = QComboBox()
        c_status.addItem("Vertrag", ZuweisungsTyp.VERTRAG)
        c_status.addItem("Planung", ZuweisungsTyp.PLANUNG)
        idx_typ = c_status.findData(typ)
        if idx_typ >= 0: c_status.setCurrentIndex(idx_typ)
        self.table.setCellWidget(row, 1, c_status)
        
        s_anteil = QSpinBox(); s_anteil.setRange(1, 100); s_anteil.setValue(anteil)
        s_anteil.valueChanged.connect(self.validate_matrix)
        self.table.setCellWidget(row, 2, s_anteil)
        
        self.table.setItem(row, 3, QTableWidgetItem(""))
        
        monats_combos = []
        for col in range(4, 4 + self.monate_gesamt):
            c_proj = QComboBox()
            col_date = self.get_date_from_col(col)
            self.populate_project_combo(c_proj, col_date, typ, ma_id)
            if monate_daten and monate_daten.get(col):
                c_proj.setCurrentIndex(c_proj.findData(monate_daten[col]))
            c_proj.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            c_proj.customContextMenuRequested.connect(lambda pos, cb=c_proj: self.show_context_menu_combo(pos, cb))
            self.table.setCellWidget(row, col, c_proj)
            monats_combos.append(c_proj)
            
        c_status.currentIndexChanged.connect(lambda _, m_cb=monats_combos, c_s=c_status, c_m=c_ma: self.update_row_projects(m_cb, c_s, c_m))
        c_ma.currentIndexChanged.connect(lambda _, m_cb=monats_combos, c_s=c_status, c_m=c_ma: self.update_row_projects(m_cb, c_s, c_m))

    def populate_project_combo(self, combo, col_date, row_typ, ma_id):
        combo.clear()
        combo.addItem("-", None)
        col_end_date = date(col_date.year, col_date.month, calendar.monthrange(col_date.year, col_date.month)[1])
        if ma_id and ma_id in self.mitarbeiter_daten:
            m_start = self.mitarbeiter_daten[ma_id]["start"]
            m_end = self.mitarbeiter_daten[ma_id]["end"]
            if m_start and col_end_date < m_start:
                combo.setToolTip("Gesperrt: Noch nicht am Institut.")
                return 
            if m_end and col_date > m_end:
                combo.setToolTip("Gesperrt: Hat Institut verlassen.")
                return 

        for p in self.projekte_alle:
            if p["start"] > col_end_date or p["end"] < col_date: continue
            if row_typ == ZuweisungsTyp.VERTRAG and p["status"] != ProjektStatus.BEWILLIGT: continue
            combo.addItem(p["name"][:12]+"...", p["id"])

    def update_row_projects(self, monats_combos, c_status, c_ma):
        row_typ = c_status.currentData()
        ma_id = c_ma.currentData()
        for i, combo in enumerate(monats_combos):
            current_id = combo.currentData()
            col_date = self.get_date_from_col(i + 4)
            self.populate_project_combo(combo, col_date, row_typ, ma_id)
            idx = combo.findData(current_id)
            if idx >= 0: combo.setCurrentIndex(idx)
            else: combo.setCurrentIndex(0) 
        self.validate_matrix()

    def show_context_menu_combo(self, pos, combo):
        row, col = self.get_cell_pos(combo)
        if row >= 0 and col >= 4:
            menu = QMenu(self)
            fill_right_action = menu.addAction("➡️ Projekt nach rechts bis Jahresende ziehen")
            fill_gap_action = menu.addAction("↔️ Lücken zwischen gleichen Projekten füllen")
            action = menu.exec(combo.mapToGlobal(pos))
            if action == fill_right_action: self.fill_right(row, col)
            elif action == fill_gap_action: self.fill_gap(row)

    def fill_right(self, row, start_col):
        combo_start = self.table.cellWidget(row, start_col)
        if not combo_start: return
        pid = combo_start.currentData()
        if not pid: return
        target_year = self.get_date_from_col(start_col).year
        for col in range(start_col + 1, 4 + self.monate_gesamt):
            if self.get_date_from_col(col).year > target_year: break 
            combo = self.table.cellWidget(row, col)
            idx = combo.findData(pid)
            if idx >= 0: combo.setCurrentIndex(idx)
        self.validate_matrix()

    def fill_gap(self, row):
        proj_ids = [self.table.cellWidget(row, c).currentData() for c in range(4, 4+self.monate_gesamt)]
        last_pid = None
        last_idx = -1
        for i, pid in enumerate(proj_ids):
            if pid is not None:
                if pid == last_pid and (i - last_idx) > 1:
                    for j in range(last_idx + 1, i):
                        combo = self.table.cellWidget(row, j + 4)
                        if combo.currentData() is None: 
                            idx = combo.findData(pid)
                            if idx >= 0: combo.setCurrentIndex(idx)
                last_pid = pid
                last_idx = i
        self.validate_matrix()

    # --- DIE MAGIE: Summierung, 100%-Prüfung & Saubere Lücken ---
    def validate_matrix(self):
        farben = ["#5DADE2", "#58D68D", "#F4D03F", "#EB984E", "#AF7AC5"] 
        
        # 1. Wir aggregieren alle Zeilen (Prozente) für jeden MA und Monat
        ma_monthly_sums = {}
        for row in range(self.table.rowCount()):
            ma_id = self.table.cellWidget(row, 0).currentData()
            anteil = self.table.cellWidget(row, 2).value()
            if not ma_id: continue
            if ma_id not in ma_monthly_sums: ma_monthly_sums[ma_id] = {c: 0 for c in range(4, 4+self.monate_gesamt)}
            
            for col in range(4, 4 + self.monate_gesamt):
                if self.table.cellWidget(row, col).currentData() is not None:
                    ma_monthly_sums[ma_id][col] += anteil

        # 2. Visuelles Update der Blöcke
        for row in range(self.table.rowCount()):
            ma_id = self.table.cellWidget(row, 0).currentData()
            
            m_start, limit_6j = None, None
            if ma_id and ma_id in self.mitarbeiter_daten:
                m_start = self.mitarbeiter_daten[ma_id]["start"]
                if m_start:
                    try: limit_6j = date(m_start.year + 6, m_start.month, m_start.day)
                    except ValueError: limit_6j = date(m_start.year + 6, m_start.month, 28)

            proj_farben = {}; f_idx = 0
            for col in range(4, 4 + self.monate_gesamt):
                combo = self.table.cellWidget(row, col)
                pid = combo.currentData()
                pid_links = self.table.cellWidget(row, col-1).currentData() if col > 4 else None
                pid_rechts = self.table.cellWidget(row, col+1).currentData() if col < 3+self.monate_gesamt else None
                
                col_date = self.get_date_from_col(col)
                is_over_6j = limit_6j and col_date >= limit_6j
                
                # Ziel-Auslastung (Standard 100%, kann durch Teilzeit 50% sein)
                target_pct = self.get_target_capacity(ma_id, col_date)
                actual_sum = ma_monthly_sums.get(ma_id, {}).get(col, 0)

                if pid:
                    if pid not in proj_farben:
                        proj_farben[pid] = farben[f_idx % len(farben)]
                        f_idx += 1
                    farbe = proj_farben[pid]
                    border_css = "border: 1px solid #777;"
                    
                    if pid == pid_links and pid == pid_rechts: border_css = "border-top: 1px solid #777; border-bottom: 1px solid #777; border-left: none; border-right: none;"
                    elif pid == pid_links: border_css = "border-top: 1px solid #777; border-bottom: 1px solid #777; border-left: none; border-right: 1px solid #777;"
                    elif pid == pid_rechts: border_css = "border-top: 1px solid #777; border-bottom: 1px solid #777; border-left: 1px solid #777; border-right: none;"
                    
                    tooltip = ""
                    
                    # ÜBERBUCHUNG / UNTERDECKUNG VISUALISIEREN
                    if actual_sum > target_pct + 0.1:
                        border_css = "border: 2px solid #E74C3C;" # Rot für überbucht
                        tooltip = f"⚠️ ÜBERBUCHT! Summe: {actual_sum} % (Ziel: {target_pct} %)\n"
                    elif actual_sum < target_pct - 0.1:
                        border_css = "border: 2px solid #F1C40F;" # Gelb für teil-gebucht
                        tooltip = f"⚠️ UNTERDECKUNG! Summe: {actual_sum} % (Ziel: {target_pct} %)\n"
                    
                    if is_over_6j:
                        border_css += " border-style: dashed;" # Gestrichelt = Weiches 6-Jahre-Fenster
                        tooltip += "Info: Befindet sich außerhalb des 6-Jahre-Fensters (WissZeitVG)."
                        
                    combo.setStyleSheet(f"QComboBox {{ background-color: {farbe}; color: #000000; {border_css} margin: 0px; font-weight: bold; }}")
                    combo.setToolTip(tooltip.strip())
                else:
                    combo.setStyleSheet("")
                    combo.setToolTip("")
                    
        return ma_monthly_sums

    def validate_and_report(self):
        """Erzeugt einen detaillierten Report über echte Lücken, Überbuchungen und auslaufende Verträge."""
        ma_monthly_sums = self.validate_matrix()
        
        heute = date.today()
        m_limit = heute.month + 6
        y_limit = heute.year
        if m_limit > 12: m_limit -= 12; y_limit += 1
        limit_6_monate = date(y_limit, m_limit, calendar.monthrange(y_limit, m_limit)[1])

        report_luecken = []     # Echte Lücken (zwischen Projekten)
        report_urgent_end = []  # Läuft in den nächsten 6 Monaten aus
        report_info_end = []    # Läuft irgendwann später aus
        report_kapazitaet = []  # Überbucht oder unterdeckt (aber > 0)
        
        untersuchte_mas = set([self.table.cellWidget(r, 0).currentData() for r in range(self.table.rowCount()) if self.table.cellWidget(r, 0).currentData()])
            
        for ma_id in untersuchte_mas:
            if ma_id not in self.mitarbeiter_daten: continue
            m_name = self.mitarbeiter_daten[ma_id]["name"]
            
            # Alle Spalten sammeln, in denen der MA > 0% gebucht ist
            active_cols = [c for c, summe in ma_monthly_sums.get(ma_id, {}).items() if summe > 0]
            if not active_cols: continue
            
            first_col = min(active_cols)
            last_col = max(active_cols)
            
            gaps = []
            
            for col in range(first_col, last_col): # Prüft NUR dazwischen!
                if col not in active_cols:
                    gaps.append(self.spalten_namen[col])
                    
            if gaps:
                report_luecken.append((m_name, gaps))
                
            # Prüfen auf Über/Unterbuchung
            kap_fehler = []
            for col in active_cols:
                actual = ma_monthly_sums[ma_id][col]
                col_date = self.get_date_from_col(col)
                target = self.get_target_capacity(ma_id, col_date)
                
                if actual > target + 0.1:
                    kap_fehler.append(f"{self.spalten_namen[col]}: Überbucht ({actual}% statt {target}%)")
                elif actual < target - 0.1:
                    kap_fehler.append(f"{self.spalten_namen[col]}: Unterdeckt ({actual}% statt {target}%)")
            
            if kap_fehler:
                report_kapazitaet.append((m_name, kap_fehler))

            # Vertragsende prüfen (Der Monat NACH der letzten Buchung)
            if last_col < (4 + self.monate_gesamt - 1):
                auslauf_col = last_col + 1
                col_date = self.get_date_from_col(auslauf_col)
                col_end_date = date(col_date.year, col_date.month, calendar.monthrange(col_date.year, col_date.month)[1])
                
                # Ist der Mitarbeiter da überhaupt noch angestellt?
                m_end = self.mitarbeiter_daten[ma_id]["end"]
                if not m_end or col_date <= m_end:
                    if col_end_date <= limit_6_monate:
                        report_urgent_end.append((m_name, self.spalten_namen[auslauf_col]))
                    else:
                        report_info_end.append((m_name, self.spalten_namen[auslauf_col]))
                
        # --- BERICHT AUSGEBEN ---
        if not report_luecken and not report_urgent_end and not report_kapazitaet and not report_info_end:
            QMessageBox.information(self, "Alles OK!", "✅ Perfekt! Keine Lücken, keine Überbuchungen.")
            return
            
        msg = ""
        if report_luecken:
            msg += "🚨 ECHTE LÜCKEN (Monate ohne Vertrag zwischen zwei Projekten):\n"
            for m, gaps in report_luecken: msg += f"👤 {m}: Fehlt in {', '.join(gaps)}\n"
            msg += "\n"
            
        if report_urgent_end:
            msg += "⚠️ DRINGEND: Auslaufende Finanzierung (In den nächsten 6 Monaten):\n"
            for m, month in report_urgent_end: msg += f"👤 {m}: Kein Vertrag mehr ab {month}\n"
            msg += "\n"
            
        if report_kapazitaet:
            msg += "⚖️ KAPAZITÄTSFEHLER (Überbuchung oder Unterdeckung):\n"
            for m, errors in report_kapazitaet: 
                msg += f"👤 {m}:\n"
                for e in errors: msg += f"   - {e}\n"
            msg += "\n"
            
        if report_info_end:
            msg += "ℹ️ INFO: Auslaufende Verträge (Zukunft, kein direkter Handlungsbedarf):\n"
            for m, month in report_info_end: msg += f"👤 {m}: Endet planmäßig in {month}\n"
            
        QMessageBox.warning(self, "Controlling Report", msg)

    def save_matrix(self):
        session = get_session()
        try:
            session.query(Zuweisung).filter(
                Zuweisung.start_datum >= date(self.start_jahr, 1, 1),
                Zuweisung.end_datum <= date(self.end_jahr, 12, 31),
                Zuweisung.typ.in_([ZuweisungsTyp.VERTRAG, ZuweisungsTyp.PLANUNG])
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
            QMessageBox.information(self, "Gespeichert", "Planungs-Matrix gespeichert!")
            self.apply_time_range() 
        finally:
            session.close()

class MatrixMainView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.gantt_view = MatrixGanttView()
        self.list_view = MatrixListView()
        self.tabs.addTab(self.gantt_view, "📊 Gantt-Matrix (Planung)")
        self.tabs.addTab(self.list_view, "📋 Listen-Ansicht (Details)")
        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        if index == 0: self.gantt_view.apply_time_range() 
        else: self.list_view.load_matrix()