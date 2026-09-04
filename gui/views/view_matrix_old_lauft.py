import calendar
from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, 
                             QHeaderView, QLabel, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models_old import Mitarbeiter, Projekt, ProjektStatus, ZuweisungsTyp, ProjektZuweisung

class MatrixView(QWidget):
    def __init__(self):
        super().__init__()
        
        self.mitarbeiter_liste = []
        self.projekte_bewilligt = []
        self.projekte_alle = []
        
        # NEU: Variable Zeitachse
        self.start_jahr = 2026
        self.end_jahr = 2027 # Standardmäßig 2 Jahre anzeigen
        self.monate_gesamt = 0
        self.spalten_namen = []
        
        self.load_stammdaten()
        self.setup_ui()

    def load_stammdaten(self):
        session = get_session()
        try:
            self.mitarbeiter_liste = session.query(Mitarbeiter).all()
            projekte = session.query(Projekt).all()
            for p in projekte:
                self.projekte_alle.append({"id": p.id, "name": p.projektname, "status": p.status})
                if p.status in [ProjektStatus.BEWILLIGT, ProjektStatus.BEENDET]:
                    self.projekte_bewilligt.append({"id": p.id, "name": p.projektname})
        finally:
            session.close()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- TOOLBAR 1: Zeitsteuerung (Gantt-Settings) ---
        toolbar_time = QHBoxLayout()
        toolbar_time.addWidget(QLabel("<b>Planungszeitraum:</b>"))
        
        self.spin_start = QSpinBox()
        self.spin_start.setRange(2020, 2040)
        self.spin_start.setValue(self.start_jahr)
        
        self.spin_end = QSpinBox()
        self.spin_end.setRange(2020, 2040)
        self.spin_end.setValue(self.end_jahr)
        
        btn_apply_time = QPushButton("Zeitraum anwenden & Laden")
        btn_apply_time.clicked.connect(self.apply_time_range)
        
        toolbar_time.addWidget(QLabel("Von:"))
        toolbar_time.addWidget(self.spin_start)
        toolbar_time.addWidget(QLabel("Bis:"))
        toolbar_time.addWidget(self.spin_end)
        toolbar_time.addWidget(btn_apply_time)
        
        # Platzhalter für zukünftigen Zoom
        self.combo_zoom = QComboBox()
        self.combo_zoom.addItems(["Zoom: Monate", "Zoom: Quartale (In Kürze)", "Zoom: Jahre (In Kürze)"])
        toolbar_time.addWidget(self.combo_zoom)
        toolbar_time.addStretch()
        
        layout.addLayout(toolbar_time)

        # --- TOOLBAR 2: Aktionen ---
        toolbar_actions = QHBoxLayout()
        btn_add_row = QPushButton("➕ Neue Zeile")
        btn_add_row.clicked.connect(self.add_matrix_row)
        
        btn_validate = QPushButton("🔍 Matrix prüfen")
        btn_validate.clicked.connect(self.validate_matrix)
        
        btn_save = QPushButton("💾 Speichern")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_matrix)
        
        # Dein gewünschter PDF Button
        btn_export = QPushButton("📄 Stammblatt (PDF)")
        btn_export.setStyleSheet("background-color: #2980B9; color: white;")
        btn_export.clicked.connect(self.export_pdf_for_selected_row) # Später aktivieren!

        btn_export_gantt = QPushButton("📊 Matrix als Gantt (PDF)")
        btn_export_gantt.setStyleSheet("background-color: #8E44AD; color: white;")
        btn_export_gantt.clicked.connect(self.export_gantt_pdf)
        
        toolbar_actions.addWidget(btn_add_row)
        toolbar_actions.addWidget(btn_validate)
        toolbar_actions.addWidget(btn_save)
        toolbar_actions.addWidget(btn_export)
        toolbar_actions.addWidget(btn_export_gantt) # NEU hinzugefügt
        toolbar_actions.addStretch()
        layout.addLayout(toolbar_actions)

        # --- DIE TABELLE ---
        self.table = QTableWidget()
        layout.addWidget(self.table)
        
        # Initialen Header und Daten laden
        self.apply_time_range()

    def apply_time_range(self):
        """Generiert die Spalten basierend auf den gewählten Jahren neu"""
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
        
        # Fixe Breiten (Die ersten 4 Spalten passen sich an, die Monate sind kompakte Blöcke)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(4, len(self.spalten_namen)): 
            self.table.setColumnWidth(i, 90) # Schmalere Spalten für besseren Gantt-Look
            
        self.load_matrix_from_db()

    def get_date_from_col(self, col_idx):
        """Hilfsfunktion: Rechnet eine Spalte (z.B. 4) in ein echtes Datum (01/2026) um"""
        monate_seit_start = col_idx - 4
        jahr = self.start_jahr + (monate_seit_start // 12)
        monat = (monate_seit_start % 12) + 1
        return date(jahr, monat, 1)

    # --- DIE LADEN FUNKTION (Dynamisch) ---
    def load_matrix_from_db(self):
        session = get_session()
        self.table.setRowCount(0)
        
        try:
            zuweisungen = session.query(ProjektZuweisung).filter(
                ProjektZuweisung.end_datum >= date(self.start_jahr, 1, 1),
                ProjektZuweisung.start_datum <= date(self.end_jahr, 12, 31)
            ).all()
            
            if not zuweisungen:
                self.add_matrix_row()
                return
                
            zeilen_daten = {} 
            for z in zuweisungen:
                key = (z.mitarbeiter_id, z.typ, int(z.anteil_pct * 100))
                if key not in zeilen_daten:
                    zeilen_daten[key] = {col: None for col in range(4, 4 + self.monate_gesamt)}
                    
                # In welche Spalten fällt diese Zuweisung?
                for col in range(4, 4 + self.monate_gesamt):
                    col_date = self.get_date_from_col(col)
                    # Letzter Tag des Monats für End-Prüfung
                    col_end_date = date(col_date.year, col_date.month, calendar.monthrange(col_date.year, col_date.month)[1])
                    
                    if z.start_datum <= col_end_date and z.end_datum >= col_date:
                        zeilen_daten[key][col] = z.projekt_id
                        
            # Aufbauen der GUI
            for (ma_id, typ, anteil), monate in zeilen_daten.items():
                self.add_matrix_row(ma_id, typ, anteil, monate)
                
            self.validate_matrix()
            
        finally:
            session.close()

    def add_matrix_row(self, ma_id=None, typ=ZuweisungsTyp.VERTRAG, anteil=100, monate_daten=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 0. Mitarbeiter
        c_ma = QComboBox()
        c_ma.addItem("-", None)
        for ma in self.mitarbeiter_liste: c_ma.addItem(f"{ma.nachname}, {ma.vorname}", ma.id)
        if ma_id: c_ma.setCurrentIndex(c_ma.findData(ma_id))
        self.table.setCellWidget(row, 0, c_ma)
        
        # 1. Status
        c_status = QComboBox()
        c_status.addItem("Vertrag", ZuweisungsTyp.VERTRAG)
        c_status.addItem("Planung", ZuweisungsTyp.PLANUNG)
        c_status.setCurrentIndex(c_status.findData(typ))
        self.table.setCellWidget(row, 1, c_status)
        
        # 2. Anteil
        s_anteil = QSpinBox()
        s_anteil.setRange(1, 100)
        s_anteil.setValue(anteil)
        self.table.setCellWidget(row, 2, s_anteil)
        
        # 3. Fehler
        self.table.setItem(row, 3, QTableWidgetItem(""))
        
        # 4. Zeitachse (Gantt)
        monats_combos = []
        for col in range(4, 4 + self.monate_gesamt):
            c_proj = QComboBox()
            self.populate_project_combo(c_proj, typ)
            if monate_daten and monate_daten.get(col):
                c_proj.setCurrentIndex(c_proj.findData(monate_daten[col]))
            self.table.setCellWidget(row, col, c_proj)
            monats_combos.append(c_proj)
            
        c_status.currentIndexChanged.connect(lambda _, cb=c_status, m_cb=monats_combos: self.update_row_projects(cb, m_cb))

    def populate_project_combo(self, combo, status_typ):
        combo.clear()
        combo.addItem("-", None)
        liste = self.projekte_bewilligt if status_typ == ZuweisungsTyp.VERTRAG else self.projekte_alle
        for p in liste: combo.addItem(p["name"][:12]+"...", p["id"]) # Kurzer Name für kompakte Gantt-Blöcke

    def update_row_projects(self, combo_status, monats_combos):
        status_typ = combo_status.currentData()
        for combo in monats_combos:
            current_id = combo.currentData()
            self.populate_project_combo(combo, status_typ)
            idx = combo.findData(current_id)
            if idx >= 0: combo.setCurrentIndex(idx)

    # --- DIE VALIDIERUNG (Inklusive Gantt "Verschwimmen") ---
    def validate_matrix(self):
        farben = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#FFCCBC", "#E1BEE7"] 
        ma_monats_summen = {} 
        
        for row in range(self.table.rowCount()):
            ma_id = self.table.cellWidget(row, 0).currentData()
            anteil = self.table.cellWidget(row, 2).value()
            if ma_id is None: continue
            if ma_id not in ma_monats_summen: ma_monats_summen[ma_id] = {col: 0 for col in range(4, 4+self.monate_gesamt)}

            proj_farben = {}
            f_idx = 0
            
            for col in range(4, 4 + self.monate_gesamt):
                combo = self.table.cellWidget(row, col)
                pid = combo.currentData()
                
                # Der "Gantt" Effekt (Zellen verschmelzen optisch durch Border-Entfernung)
                pid_links = self.table.cellWidget(row, col-1).currentData() if col > 4 else None
                pid_rechts = self.table.cellWidget(row, col+1).currentData() if col < 3+self.monate_gesamt else None
                
                if pid:
                    ma_monats_summen[ma_id][col] += anteil
                    if pid not in proj_farben:
                        proj_farben[pid] = farben[f_idx % len(farben)]
                        f_idx += 1
                        
                    farbe = proj_farben[pid]
                    
                    # CSS Magic: Wenn links oder rechts das gleiche Projekt ist, Rand entfernen!
                    border_css = "border: 1px solid #aaa;"
                    if pid == pid_links and pid == pid_rechts:
                        border_css = "border-top: 1px solid #aaa; border-bottom: 1px solid #aaa; border-left: none; border-right: none;"
                    elif pid == pid_links:
                        border_css = "border-top: 1px solid #aaa; border-bottom: 1px solid #aaa; border-left: none; border-right: 1px solid #aaa;"
                    elif pid == pid_rechts:
                        border_css = "border-top: 1px solid #aaa; border-bottom: 1px solid #aaa; border-left: 1px solid #aaa; border-right: none;"
                        
                    combo.setStyleSheet(f"QComboBox {{ background-color: {farbe}; color: black; {border_css} margin: 0px; }}")
                else:
                    combo.setStyleSheet("")

    def save_matrix(self):
        # Stark vereinfachte Speicherlogik für dynamische Jahre
        session = get_session()
        try:
            # Löscht nur die Verträge im aktuell angezeigten Fenster (Start bis Endjahr)
            session.query(ProjektZuweisung).filter(
                ProjektZuweisung.start_datum >= date(self.start_jahr, 1, 1),
                ProjektZuweisung.end_datum <= date(self.end_jahr, 12, 31)
            ).delete()

            for row in range(self.table.rowCount()):
                ma_id = self.table.cellWidget(row, 0).currentData()
                if not ma_id: continue
                
                typ = self.table.cellWidget(row, 1).currentData()
                anteil = self.table.cellWidget(row, 2).value() / 100.0

                current_pid = None
                start_col = None

                for col in range(4, 5 + self.monate_gesamt): # +1 für den sauberen Abschluss am Ende
                    pid = self.table.cellWidget(row, col).currentData() if col < 4 + self.monate_gesamt else None
                    
                    if pid != current_pid:
                        if current_pid is not None:
                            start_date = self.get_date_from_col(start_col)
                            end_date_temp = self.get_date_from_col(col - 1)
                            end_date = date(end_date_temp.year, end_date_temp.month, calendar.monthrange(end_date_temp.year, end_date_temp.month)[1])
                            
                            session.add(ProjektZuweisung(mitarbeiter_id=ma_id, projekt_id=current_pid, typ=typ, anteil_pct=anteil, start_datum=start_date, end_datum=end_date))
                        
                        current_pid = pid
                        start_col = col

            session.commit()
            QMessageBox.information(self, "Gespeichert", "Matrix im gewählten Zeitraum erfolgreich gespeichert!")
        finally:
            session.close()


    def export_pdf_for_selected_row(self):
        """Liest die aktuell markierte Zeile aus und triggert den PDF-Export."""
        row = self.table.currentRow()
        
        if row < 0:
            QMessageBox.warning(self, "Hinweis", "Bitte klicken Sie zuerst in die Zeile des Mitarbeiters, für den Sie das PDF exportieren möchten.")
            return
            
        # Mitarbeiter-ID aus der Dropdown-Box dieser Zeile auslesen
        combo_ma = self.table.cellWidget(row, 0)
        ma_id = combo_ma.currentData()
        
        if ma_id is None:
            QMessageBox.warning(self, "Hinweis", "In dieser Zeile ist noch kein Mitarbeiter ausgewählt.")
            return
            
        # Wir nehmen das Startjahr aus dem Gantt-Chart als Referenzjahr für das PDF
        referenz_jahr = self.spin_start.value()
            
        from gui.components.pdf_exporter import export_mitarbeiter_pdf
        export_mitarbeiter_pdf(self, ma_id, referenz_jahr)       


    def export_gantt_pdf(self):
        """Triggert den PDF-Export der kompletten Matrix als Gantt-Chart."""
        from gui.components.pdf_exporter import export_matrix_gantt_pdf
        
        # Wir übergeben die Tabelle und die nötigen Parameter für den Titel & Kopfzeile
        export_matrix_gantt_pdf(
            self, 
            self.table, 
            self.start_jahr, 
            self.end_jahr, 
            self.spalten_namen
        )        