import calendar
from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, 
                             QHeaderView, QLabel, QMessageBox, QDialog, QFormLayout, 
                             QDateEdit, QDoubleSpinBox, QDialogButtonBox, QTabWidget,
                             QMenu, QTextEdit, QCheckBox)
from PyQt6.QtGui import QColor
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
# ANSI 2: GANTT-MATRIX (MIT LIVE-REPORTING)
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

    def compress_months(self, month_list):
        if not month_list: return []
        def parse_m(s):
            m, y = s.split('/')
            return int(y) * 12 + int(m)
        sorted_m = sorted(month_list, key=parse_m)
        ranges, start, last = [], sorted_m[0], sorted_m[0]
        
        for current in sorted_m[1:]:
            if parse_m(current) == parse_m(last) + 1:
                last = current
            else:
                ranges.append((start, last))
                start, last = current, current
        ranges.append((start, last))
        return [f"{s} - {e}" if s != e else s for s, e in ranges]

    def get_actual_hr_capacity(self, ma_id, check_date):
        if not ma_id or ma_id not in self.mitarbeiter_daten: return 100.0
        az_verlaeufe = self.mitarbeiter_daten[ma_id]["arbeitszeiten"]
        check_end_date = date(check_date.year, check_date.month, calendar.monthrange(check_date.year, check_date.month)[1])
        for az in az_verlaeufe:
            if az.gueltig_ab <= check_end_date:
                if not az.gueltig_bis or az.gueltig_bis >= check_date:
                    return az.anteil_pct * 100.0 
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
        btn_save = QPushButton("💾 Speichern")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_matrix)
        
        self.check_live = QCheckBox("Live-Prüfung & Reporting (Auto-Berechnung)")
        self.check_live.setChecked(True)
        self.check_live.toggled.connect(self.validate_and_report)
        
        toolbar_actions.addWidget(btn_add)
        toolbar_actions.addWidget(self.check_live)
        toolbar_actions.addWidget(btn_save)
        toolbar_actions.addStretch()
        layout.addLayout(toolbar_actions)
        
        self.table = QTableWidget()
        layout.addWidget(self.table)
        
        self.report_box = QTextEdit()
        self.report_box.setReadOnly(True)
        self.report_box.setMaximumHeight(150)
        self.report_box.setStyleSheet("background-color: #F8F9F9; border: 1px solid #BDC3C7;")
        layout.addWidget(self.report_box)
        
        self.apply_time_range()

    def apply_time_range(self):
        self.load_stammdaten()
        self.start_jahr = self.spin_start.value()
        self.end_jahr = self.spin_end.value()
        if self.start_jahr > self.end_jahr: return
        self.spalten_namen = ["MA-Name", "Status", "Plan-Anteil %", "Zell-Info"]
        for jahr in range(self.start_jahr, self.end_jahr + 1):
            for monat in range(1, 13):
                self.spalten_namen.append(f"{monat:02d}/{str(jahr)[-2:]}")
        self.monate_gesamt = len(self.spalten_namen) - 4
        self.table.clear()
        self.table.setColumnCount(len(self.spalten_namen))
        self.table.setHorizontalHeaderLabels(self.spalten_namen)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
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
                key = (z.mitarbeiter_id, z.typ, round(z.anteil_pct * 100, 2))
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

    def add_matrix_row(self, ma_id=None, typ=ZuweisungsTyp.PLANUNG, anteil=100.0, monate_daten=None):
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
        
        s_anteil = QDoubleSpinBox()
        s_anteil.setRange(0.0, 100.0)
        s_anteil.setDecimals(2)
        s_anteil.setValue(anteil)
        s_anteil.setSuffix(" %")
        s_anteil.valueChanged.connect(self.validate_matrix)
        self.table.setCellWidget(row, 2, s_anteil)
        
        item_info = QTableWidgetItem("")
        item_info.setForeground(Qt.GlobalColor.gray)
        self.table.setItem(row, 3, item_info)
        
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

    def validate_matrix(self):
        farben = ["#5DADE2", "#58D68D", "#F4D03F", "#EB984E", "#AF7AC5"]          
        
        ma_monthly_sums = {}
        for row in range(self.table.rowCount()):
            ma_id = self.table.cellWidget(row, 0).currentData()
            anteil = self.table.cellWidget(row, 2).value()
            if not ma_id: continue
            if ma_id not in ma_monthly_sums: ma_monthly_sums[ma_id] = {c: 0 for c in range(4, 4+self.monate_gesamt)}
            
            for col in range(4, 4 + self.monate_gesamt):
                if self.table.cellWidget(row, col).currentData() is not None:
                    ma_monthly_sums[ma_id][col] += anteil

        for row in range(self.table.rowCount()):
            ma_id = self.table.cellWidget(row, 0).currentData()
            
            m_start, commitment_end = None, None
            if ma_id and ma_id in self.mitarbeiter_daten:
                m_start = self.mitarbeiter_daten[ma_id]["start"]
                m_abgang = self.mitarbeiter_daten[ma_id]["end"]
                if m_start:
                    try: limit_6j = date(m_start.year + 6, m_start.month, m_start.day)
                    except ValueError: limit_6j = date(m_start.year + 6, m_start.month, 28)
                    commitment_end = m_abgang if m_abgang and m_abgang < limit_6j else limit_6j

                # --- ZELL-INFO FÜLLEN (Nur noch als Basis-Info, Fehler kommen per Ticker) ---
                hr_capacity = self.get_actual_hr_capacity(ma_id, date.today())
                info_text = f"Vertrag: {hr_capacity:.1f}%"
                if commitment_end:
                    info_text += f" | Zusage bis: {commitment_end.strftime('%m/%Y')}"
                self.table.item(row, 3).setText(info_text)
            else:
                self.table.item(row, 3).setText("")

            proj_farben = {}; f_idx = 0
            for col in range(4, 4 + self.monate_gesamt):
                combo = self.table.cellWidget(row, col)
                pid = combo.currentData()
                pid_links = self.table.cellWidget(row, col-1).currentData() if col > 4 else None
                pid_rechts = self.table.cellWidget(row, col+1).currentData() if col < 3+self.monate_gesamt else None
                
                col_date = self.get_date_from_col(col)
                is_in_commitment = m_start and commitment_end and (m_start <= col_date < commitment_end)
                
                # ZIEL IST IMMER 100% (Verteilung der VERFÜGBAREN Zeit)
                target_pct = 100.0 
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
                    if actual_sum > target_pct + 0.1:
                        border_css = "border: 2px solid #E74C3C;"
                        tooltip = f"⚠️ ÜBERBUCHT! Summe: {actual_sum} % (Ziel: {target_pct} %)\n"
                    elif actual_sum < target_pct - 0.1:
                        border_css = "border: 2px solid #F1C40F;"
                        tooltip = f"⚠️ UNTERDECKUNG! Summe: {actual_sum} % (Ziel: {target_pct} %)\n"
                        
                    combo.setStyleSheet(f"QComboBox {{ background-color: {farbe}; color: #000000; {border_css} margin: 0px; font-weight: bold; }}")
                    combo.setToolTip(tooltip.strip())
                else:
                    if is_in_commitment and actual_sum == 0:
                        combo.setStyleSheet("QComboBox { background-color: #FDEDEC; border: 1px dashed #E74C3C; margin: 1px; }")
                        combo.setToolTip("⚠️ Ungedeckter Bedarf (Finanzierungs-Zusage)")
                    else:
                        combo.setStyleSheet("")
                        combo.setToolTip("")
                    
        if hasattr(self, 'check_live') and self.check_live.isChecked():
            self.validate_and_report(ma_monthly_sums=ma_monthly_sums)
            
        return ma_monthly_sums

    def validate_and_report(self, checked=True, ma_monthly_sums=None):
        if not hasattr(self, 'report_box'): return
        
        show_live = self.check_live.isChecked()
        self.report_box.setVisible(show_live)
        
        if ma_monthly_sums is None:
            ma_monthly_sums = self.validate_matrix()
            return 
        
        heute = date.today()
        m_limit = heute.month + 6
        y_limit = heute.year
        if m_limit > 12: m_limit -= 12; y_limit += 1
        limit_6_monate = date(y_limit, m_limit, calendar.monthrange(y_limit, m_limit)[1])

        report_luecken = []     
        report_urgent_end = []  
        report_kapazitaet = []  
        report_urgent_ungedeckt = [] 
        report_info_ungedeckt = []   
        report_info_end = [] 
        
        untersuchte_mas = set([self.table.cellWidget(r, 0).currentData() for r in range(self.table.rowCount()) if self.table.cellWidget(r, 0).currentData()])
            
        for ma_id in untersuchte_mas:
            if ma_id not in self.mitarbeiter_daten: continue
            m_name = self.mitarbeiter_daten[ma_id]["name"]
            
            m_start = self.mitarbeiter_daten[ma_id]["start"]
            m_abgang = self.mitarbeiter_daten[ma_id]["end"]
            commitment_end = None
            if m_start:
                try: limit_6j = date(m_start.year + 6, m_start.month, m_start.day)
                except ValueError: limit_6j = date(m_start.year + 6, m_start.month, 28)
                commitment_end = m_abgang if m_abgang and m_abgang < limit_6j else limit_6j
            
            active_cols = [c for c, summe in ma_monthly_sums.get(ma_id, {}).items() if summe > 0]
            
            urg_ungedeckt_cols = []
            info_ungedeckt_cols = []
            
            for col in range(4, 4 + self.monate_gesamt):
                col_date = self.get_date_from_col(col)
                # Ungedeckt Check innerhalb der Bringschuld
                if m_start and commitment_end and (m_start <= col_date < commitment_end):
                    if ma_monthly_sums.get(ma_id, {}).get(col, 0) == 0:
                        if col_date <= limit_6_monate: urg_ungedeckt_cols.append(self.spalten_namen[col])
                        else: info_ungedeckt_cols.append(self.spalten_namen[col])
            
            if urg_ungedeckt_cols: report_urgent_ungedeckt.append((m_name, self.compress_months(urg_ungedeckt_cols)))
            if info_ungedeckt_cols: report_info_ungedeckt.append((m_name, self.compress_months(info_ungedeckt_cols)))

            gaps = []
            kap_fehler = []
            is_urgent_end = False
            is_info_end = False
            
            if active_cols:
                first_col = min(active_cols)
                last_col = max(active_cols)
                
                for col in range(first_col, last_col):
                    if col not in active_cols: gaps.append(self.spalten_namen[col])
                if gaps: report_luecken.append((m_name, self.compress_months(gaps)))
                    
                for col in active_cols:
                    actual = ma_monthly_sums[ma_id][col]
                    target = 100.0
                    if actual > target + 0.1: kap_fehler.append(f"{self.spalten_namen[col]}: {actual}%")
                    elif actual < target - 0.1: kap_fehler.append(f"{self.spalten_namen[col]}: {actual}%")
                if kap_fehler: report_kapazitaet.append((m_name, kap_fehler))

                if last_col < (4 + self.monate_gesamt - 1):
                    auslauf_col = last_col + 1
                    col_date = self.get_date_from_col(auslauf_col)
                    col_end_date = date(col_date.year, col_date.month, calendar.monthrange(col_date.year, col_date.month)[1])
                    if not m_abgang or col_date <= m_abgang:
                        if col_end_date <= limit_6_monate: 
                            report_urgent_end.append((m_name, self.spalten_namen[auslauf_col]))
                            is_urgent_end = True
                        else: 
                            report_info_end.append((m_name, self.spalten_namen[auslauf_col]))
                            is_info_end = True

            # --- ZELL-INFO LOGIK (Der persönliche Ticker) ---
            short_error = "✅ OK"
            error_color = "#27AE60"
            
            if urg_ungedeckt_cols:
                short_error = "⚠️ Ungedeckt (<6M)"
                error_color = "#E74C3C"
            elif gaps:
                short_error = "⚠️ Plan-Lücke"
                error_color = "#E67E22"
            elif is_urgent_end:
                short_error = "⚠️ Endet <6M"
                error_color = "#E67E22"
            elif kap_fehler:
                short_error = "⚠️ Anteil != 100%"
                error_color = "#C0392B"
            elif info_ungedeckt_cols:
                short_error = "ℹ️ Ungedeckt (>6M)"
                error_color = "#F39C12"
            elif is_info_end:
                short_error = "ℹ️ Endet regulär"
                error_color = "#7F8C8D"
                
            # Die primäre Stammdaten-Info wieder dazuschreiben
            hr_capacity = self.get_actual_hr_capacity(ma_id, date.today())
            base_info = f"Az: {hr_capacity:.0f}%"
            
            for r in range(self.table.rowCount()):
                if self.table.cellWidget(r, 0).currentData() == ma_id:
                    info_item = self.table.item(r, 3)
                    if info_item:
                        info_item.setText(f"{base_info} | {short_error}")
                        info_item.setForeground(QColor(error_color))

        if not show_live: return

        if not any([report_luecken, report_urgent_end, report_kapazitaet, report_urgent_ungedeckt, report_info_ungedeckt]):
            self.report_box.setStyleSheet("background-color: #E8F8F5; color: #1E8449; border: 1px solid #27AE60; padding: 5px;")
            self.report_box.setText("✅ Alles OK! Die sichtbare Planungsmatrix deckt alle Zusagen, enthält keine Lücken und keine Überbuchungen.")
            return
            
        msg = ""
        # KRITISCH: Oben
        if report_urgent_ungedeckt:
            msg += "⚠️ AKUTER UNGEDECKTER BEDARF (Zusage-Lücke in den nächsten 6 Monaten):\n"
            for m, errs in report_urgent_ungedeckt: msg += f"👤 {m}: Finanzierung fehlt für {', '.join(errs)}\n"
            msg += "\n"
        if report_luecken:
            msg += "⚠️ ECHTE LÜCKEN (Planungslücke zwischen zwei Projekten):\n"
            for m, gaps in report_luecken: msg += f"👤 {m}: Fehlt in {', '.join(gaps)}\n"
            msg += "\n"
        if report_urgent_end:
            msg += "⚠️ DRINGEND: Auslaufende Projektfinanzierung (< 6 Monate):\n"
            for m, month in report_urgent_end: msg += f"👤 {m}: Endet planmäßig ab {month}\n"
            msg += "\n"
        if report_kapazitaet:
            msg += "⚠️ KAPAZITÄTSFEHLER (Matrix-Planung != 100%):\n"
            for m, errors in report_kapazitaet: msg += f"👤 {m}: " + " | ".join(errors) + "\n"
            msg += "\n"
            
        # INFO: Unten
        if report_info_ungedeckt:
            msg += "ℹ️ INFO: Zukünftiger ungedeckter Bedarf (> 6 Monate):\n"
            for m, errs in report_info_ungedeckt: msg += f"👤 {m}: Finanzierung fehlt für {', '.join(errs)}\n"
            msg += "\n"
        if report_info_end:
            msg += "ℹ️ INFO: Auslaufende Verträge in ferner Zukunft (> 6 Monate):\n"
            for m, month in report_info_end: msg += f"👤 {m}: Endet planmäßig ab {month}\n"
            
        self.report_box.setStyleSheet("background-color: #FDEDEC; color: #C0392B; border: 1px solid #E74C3C; padding: 5px;")
        self.report_box.setText(msg.strip())

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