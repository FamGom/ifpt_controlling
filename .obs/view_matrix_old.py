import calendar
from datetime import date

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QHeaderView, QLabel, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models_old import Mitarbeiter, Projekt, ProjektStatus, ZuweisungsTyp

class MatrixView(QWidget):
    def __init__(self):
        super().__init__()
        
        # Wir laden die Stammdaten einmalig für die Dropdowns
        self.mitarbeiter_liste = []
        self.projekte_bewilligt = []
        self.projekte_alle = []
        self.load_stammdaten()

        self.setup_ui()

    def load_stammdaten(self):
        """Holt das Personal und die Projekte aus der Datenbank"""
        session = get_session()
        try:
            self.mitarbeiter_liste = session.query(Mitarbeiter).all()
            
            projekte = session.query(Projekt).all()
            for p in projekte:
                # Format für Dropdown: "Name (PSP/FKZ)"
                anzeige_name = f"{p.projektname}"
                self.projekte_alle.append({"id": p.id, "name": anzeige_name, "status": p.status})
                if p.status == ProjektStatus.BEWILLIGT or p.status == ProjektStatus.BEENDET:
                    self.projekte_bewilligt.append({"id": p.id, "name": anzeige_name})
        finally:
            session.close()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- TOOLBAR ---
        toolbar = QHBoxLayout()
        title = QLabel("Personal-Projekt-Matrix (Jahr: 2026)")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        btn_add_row = QPushButton("➕ Neue Zeile hinzufügen")
        btn_add_row.clicked.connect(self.add_matrix_row)
        
        btn_validate = QPushButton("🔍 Matrix prüfen (Zebra-Look & Fehler)")
        btn_validate.clicked.connect(self.validate_matrix)
        
        btn_save = QPushButton("💾 Speichern")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_matrix) # <- Diese Zeile neu hinzufügen!

        # NEU: Der PDF-Export Button
        btn_export = QPushButton("📄 Stammblatt (PDF) der gewählten Zeile")
        btn_export.setStyleSheet("background-color: #2980B9; color: white;")
        btn_export.clicked.connect(self.export_pdf_for_selected_row)
        
        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(btn_add_row)
        toolbar.addWidget(btn_validate)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_export) # NEU
        
        layout.addLayout(toolbar)

        # --- DIE TABELLE ---
        self.table = QTableWidget()
        
        # 4 Basis-Spalten + 12 Monate
        self.spalten_namen = ["MA-Name", "Status", "Anteil %", "Fehler"] + [f"{m:02d}/26" for m in range(1, 13)]
        self.table.setColumnCount(len(self.spalten_namen))
        self.table.setHorizontalHeaderLabels(self.spalten_namen)
        
        # Breiten-Einstellungen
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for i in range(4, 16): # Monatsspalten
            self.table.setColumnWidth(i, 120)
            
        layout.addWidget(self.table)
        
        # Daten aus der Datenbank laden
        self.load_matrix_from_db()
        

    def add_matrix_row(self):
        """Fügt eine neue, interaktive Zeile in die Tabelle ein"""
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)

        # 1. Mitarbeiter Dropdown (Spalte 0)
        combo_ma = QComboBox()
        combo_ma.addItem("--- Auswählen ---", None)
        for ma in self.mitarbeiter_liste:
            combo_ma.addItem(f"{ma.nachname}, {ma.vorname}", ma.id)
        self.table.setCellWidget(row_idx, 0, combo_ma)

        # 2. Status Dropdown (Spalte 1)
        combo_status = QComboBox()
        combo_status.addItem("Vertrag", ZuweisungsTyp.VERTRAG)
        combo_status.addItem("Planung", ZuweisungsTyp.PLANUNG)
        self.table.setCellWidget(row_idx, 1, combo_status)

        # 3. Anteil SpinBox (Spalte 2)
        spin_anteil = QSpinBox()
        spin_anteil.setRange(1, 100)
        spin_anteil.setValue(100)
        spin_anteil.setSuffix(" %")
        self.table.setCellWidget(row_idx, 2, spin_anteil)

        # 4. Fehlerfeld (Spalte 3 - Read Only)
        item_fehler = QTableWidgetItem("")
        item_fehler.setForeground(Qt.GlobalColor.red)
        item_fehler.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled) # Nicht bearbeitbar
        self.table.setItem(row_idx, 3, item_fehler)

        # 5. Monats-Dropdowns (Spalten 4 bis 15)
        # Wir speichern die Dropdowns in einer Liste, um sie bei Status-Wechsel zu aktualisieren
        monats_combos = []
        for col in range(4, 16):
            combo_projekt = QComboBox()
            self.populate_project_combo(combo_projekt, ZuweisungsTyp.VERTRAG) # Standard: Nur bewilligte
            self.table.setCellWidget(row_idx, col, combo_projekt)
            monats_combos.append(combo_projekt)
            
        # 6. SIGNALS (Die Dynamik!): Wenn sich der Status ändert, aktualisiere die Projekt-Dropdowns in dieser Zeile
        combo_status.currentIndexChanged.connect(
            lambda index, cb=combo_status, m_cb=monats_combos: self.update_row_projects(cb, m_cb)
        )

    def load_matrix_from_db(self):
        """Lädt gespeicherte Zuweisungen aus der DB und übersetzt sie in die GUI-Tabelle."""
        session = get_session()
        try:
            from core.models_old import ProjektZuweisung
            
            # Alle Zuweisungen für das Betrachtungsjahr (hier fest 2026) laden
            zuweisungen = session.query(ProjektZuweisung).filter(
                ProjektZuweisung.start_datum >= date(2026, 1, 1),
                ProjektZuweisung.end_datum <= date(2026, 12, 31)
            ).all()
            
            # Falls die Datenbank leer ist, einfach eine leere Start-Zeile anzeigen
            if not zuweisungen:
                self.add_matrix_row()
                return
                
            # 1. Daten aus der DB in Zeilen-Strukturen gruppieren
            # Eine GUI-Zeile wird definiert durch die Kombi aus: Mitarbeiter, Status, Anteil
            zeilen_daten = {} 
            
            for z in zuweisungen:
                key = (z.mitarbeiter_id, z.typ, int(z.anteil_pct * 100))
                if key not in zeilen_daten:
                    # Leeres Dictionary für 12 Monate anlegen
                    zeilen_daten[key] = {m: None for m in range(1, 13)}
                    
                # Die Monate dieses Blocks ausfüllen
                start_m = z.start_datum.month
                end_m = z.end_datum.month
                for m in range(start_m, end_m + 1):
                    zeilen_daten[key][m] = z.projekt_id
                    
            # 2. GUI Tabelle leeren
            self.table.setRowCount(0)
            
            # 3. Für jede gefundene Gruppierung eine Zeile in der GUI aufbauen
            for (ma_id, typ, anteil), monate in zeilen_daten.items():
                row_idx = self.table.rowCount()
                self.table.insertRow(row_idx)
                
                # --- Spalte 0: Mitarbeiter ---
                combo_ma = QComboBox()
                combo_ma.addItem("--- Auswählen ---", None)
                for ma in self.mitarbeiter_liste:
                    combo_ma.addItem(f"{ma.nachname}, {ma.vorname}", ma.id)
                idx_ma = combo_ma.findData(ma_id)
                if idx_ma >= 0: combo_ma.setCurrentIndex(idx_ma)
                self.table.setCellWidget(row_idx, 0, combo_ma)
                
                # --- Spalte 1: Status ---
                combo_status = QComboBox()
                combo_status.addItem("Vertrag", ZuweisungsTyp.VERTRAG)
                combo_status.addItem("Planung", ZuweisungsTyp.PLANUNG)
                idx_status = combo_status.findData(typ)
                if idx_status >= 0: combo_status.setCurrentIndex(idx_status)
                self.table.setCellWidget(row_idx, 1, combo_status)
                
                # --- Spalte 2: Anteil ---
                spin_anteil = QSpinBox()
                spin_anteil.setRange(1, 100)
                spin_anteil.setValue(anteil)
                spin_anteil.setSuffix(" %")
                self.table.setCellWidget(row_idx, 2, spin_anteil)
                
                # --- Spalte 3: Fehler ---
                item_fehler = QTableWidgetItem("")
                item_fehler.setForeground(Qt.GlobalColor.red)
                item_fehler.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row_idx, 3, item_fehler)
                
                # --- Spalten 4 bis 15: Monate ---
                monats_combos = []
                for col in range(4, 16):
                    monat = col - 3
                    combo_projekt = QComboBox()
                    self.populate_project_combo(combo_projekt, typ)
                    
                    # Wenn wir für diesen Monat ein Projekt in der DB haben, wähle es aus
                    projekt_id = monate[monat]
                    if projekt_id is not None:
                        idx_proj = combo_projekt.findData(projekt_id)
                        if idx_proj >= 0:
                            combo_projekt.setCurrentIndex(idx_proj)
                            
                    self.table.setCellWidget(row_idx, col, combo_projekt)
                    monats_combos.append(combo_projekt)
                    
                # Signal für Dynamik verknüpfen
                combo_status.currentIndexChanged.connect(
                    lambda index, cb=combo_status, m_cb=monats_combos: self.update_row_projects(cb, m_cb)
                )
                
            # Ganz am Ende: Validierung aufrufen, damit der Zebra-Look und Fehlermeldungen direkt da sind!
            self.validate_matrix()
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Laden", f"Die Matrix konnte nicht geladen werden:\n{str(e)}")
        finally:
            session.close()

    def populate_project_combo(self, combo, status_typ):
        """Füllt ein Dropdown mit den korrekten Projekten basierend auf dem Status"""
        combo.clear()
        combo.addItem("-", None) # Leere Auswahl
        
        # Filtern der Projekte
        if status_typ == ZuweisungsTyp.VERTRAG:
            liste = self.projekte_bewilligt
        else: # PLANUNG (zeigt auch beantragte)
            liste = self.projekte_alle
            
        for p in liste:
            combo.addItem(p["name"], p["id"])

    def update_row_projects(self, combo_status, monats_combos):
        """Wird aufgerufen, wenn der Nutzer zwischen 'Vertrag' und 'Planung' wechselt"""
        status_typ = combo_status.currentData()
        
        for combo in monats_combos:
            # Aktuell ausgewähltes Projekt merken (damit es beim Update nicht verschwindet)
            current_id = combo.currentData()
            self.populate_project_combo(combo, status_typ)
            
            # Versuch, das vorherige Projekt wieder auszuwählen
            idx = combo.findData(current_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def validate_matrix(self):
        """Prüft auf Lücken, Unterauslastung, >100% und setzt Projekt-basierte Farben."""
        
        # Deutlichere Farben für den Zebra-Look mit erzwungener SCHWARZER Schrift für max. Kontrast
        farben = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#FFCCBC", "#E1BEE7"] # Blau, Grün, Gelb, Orange, Lila
        
        ma_monats_summen = {} 
        zeilen_fehler = {row: [] for row in range(self.table.rowCount())}
        zeilen_hinweise = {row: [] for row in range(self.table.rowCount())} # Neu für Warnungen!

        # --- TEIL 1: Horizontale Prüfung (Projekt-Zebra) & Summenbildung ---
        for row in range(self.table.rowCount()):
            combo_ma = self.table.cellWidget(row, 0)
            ma_id = combo_ma.currentData()
            
            spin_anteil = self.table.cellWidget(row, 2)
            anteil_pct = spin_anteil.value()
            
            if ma_id is None:
                continue
                
            if ma_id not in ma_monats_summen:
                ma_monats_summen[ma_id] = {col: 0 for col in range(4, 16)}

            # NEU: Jedes Projekt behält seine Farbe in dieser Zeile
            projekt_farben_mapping = {}
            farb_counter = 0
            
            for col in range(4, 16):
                combo_projekt = self.table.cellWidget(row, col)
                projekt_id = combo_projekt.currentData()
                
                if projekt_id is not None:
                    ma_monats_summen[ma_id][col] += anteil_pct
                    
                    # Wenn wir das Projekt in dieser Zeile noch nicht hatten, bekommt es die nächste Farbe
                    if projekt_id not in projekt_farben_mapping:
                        projekt_farben_mapping[projekt_id] = farben[farb_counter % len(farben)]
                        farb_counter += 1
                        
                    farbe = projekt_farben_mapping[projekt_id]
                    # Das QComboBox-Styling erzwingt schwarze Schrift und ignoriert Windows-Standard-Themes
                    combo_projekt.setStyleSheet(f"QComboBox {{ background-color: {farbe}; color: black; }}")
                else:
                    combo_projekt.setStyleSheet("") 

        # --- TEIL 2: Vertikale Prüfung (>100%, Lücken, Unterauslastung) ---
        for row in range(self.table.rowCount()):
            combo_ma = self.table.cellWidget(row, 0)
            ma_id = combo_ma.currentData()
            
            if ma_id is None:
                continue
                
            # 1. >100% Check (Kritischer Fehler)
            ueber_100_monate = []
            for col in range(4, 16):
                if ma_monats_summen[ma_id][col] > 100:
                    ueber_100_monate.append(self.spalten_namen[col])
                    self.table.cellWidget(row, col).setStyleSheet("QComboBox { background-color: #ff9999; color: black; border: 2px solid red; }")
            
            if ueber_100_monate:
                if len(ueber_100_monate) > 2:
                    zeilen_fehler[row].append(f">100% in {len(ueber_100_monate)} Mon.")
                else:
                    zeilen_fehler[row].append(f">100%: {', '.join(ueber_100_monate)}")

            # 2. Echte Lücken Check (Kritischer Fehler)
            hatte_vertrag = False
            hatte_pause = False
            hat_luecke = False
            aktive_monate = [] # Sammeln wir direkt für Punkt 3
            
            for col in range(4, 16):
                summe = ma_monats_summen[ma_id][col]
                if summe > 0:
                    aktive_monate.append(summe)
                    if hatte_pause: 
                        hat_luecke = True
                    hatte_vertrag = True
                else:
                    if hatte_vertrag: 
                        hatte_pause = True
                        
            if hat_luecke:
                zeilen_fehler[row].append("Vertragslücke!")

            # 3. Unterauslastung / Drop (Warnhinweis)
            if aktive_monate:
                max_auslastung = max(aktive_monate) # z.B. 100
                unterauslastung_monate = []
                for col in range(4, 16):
                    summe = ma_monats_summen[ma_id][col]
                    # Wenn er in dem Monat arbeitet, aber weniger als sein Maximum
                    if 0 < summe < max_auslastung:
                        unterauslastung_monate.append(f"{self.spalten_namen[col]} ({summe}%)")
                
                if unterauslastung_monate:
                    # Kurze Anzeige, damit die Spalte nicht explodiert
                    anzeige = ", ".join(unterauslastung_monate[:2])
                    if len(unterauslastung_monate) > 2:
                        anzeige += " ..."
                    zeilen_hinweise[row].append(f"Drop in {anzeige}")

        # --- TEIL 3: Fehler und Hinweise in der GUI darstellen ---
        for row in range(self.table.rowCount()):
            item_fehler = self.table.item(row, 3)
            fehler_liste = zeilen_fehler[row]
            hinweis_liste = zeilen_hinweise[row]
            
            if fehler_liste:
                # KRITISCHE FEHLER (Rot)
                item_fehler.setText(" | ".join(fehler_liste))
                item_fehler.setForeground(Qt.GlobalColor.red)
                self.table.cellWidget(row, 0).setStyleSheet("QComboBox { background-color: #ffcccc; color: black; }")
            elif hinweis_liste:
                # NUR HINWEISE (Orange)
                item_fehler.setText(" | ".join(hinweis_liste))
                item_fehler.setForeground(QColor(200, 100, 0)) # Dunkelorange Text
                self.table.cellWidget(row, 0).setStyleSheet("QComboBox { background-color: #ffe0b2; color: black; }") # Helles Orange im Namen
            else:
                # ALLES OK
                item_fehler.setText("")
                if self.table.cellWidget(row, 0):
                    self.table.cellWidget(row, 0).setStyleSheet("")

    
    def save_matrix(self):
        """Liest die Tabelle aus, fasst Monate zusammen und speichert in die DB."""
        
        # 1. Wir zwingen die App, erst zu prüfen!
        self.validate_matrix()
        
        # Prüfen, ob noch Fehler (rote Felder) vorhanden sind
        hat_fehler = False
        for row in range(self.table.rowCount()):
            if self.table.item(row, 3).text() != "":
                hat_fehler = True
                break
                
        if hat_fehler:
            # Zeigt einen Ja/Nein-Dialog an, statt knallhart zu blockieren
            antwort = QMessageBox.question(
                self, 
                "Matrix enthält Fehler", 
                "In der Matrix gibt es noch ungelöste Fehler (z. B. Lücken oder über 100 % Verplanung).\n\nMöchten Sie den aktuellen Stand trotzdem speichern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No # Standardmäßig auf "Nein" als Schutz
            )
            
            if antwort == QMessageBox.StandardButton.No:
                return # Der Nutzer hat abgebrochen, wir speichern nicht.

        session = get_session()
        try:
            from core.models_old import ProjektZuweisung
            
            # 2. Bereinigen der Alt-Daten
            # Für dieses Tutorial-Jahr 2026 löschen wir vorher alle alten Einträge aus 2026,
            # damit wir nicht unendlich viele Duplikate erzeugen, wenn wir mehrfach "Speichern" klicken.
            session.query(ProjektZuweisung).filter(
                ProjektZuweisung.start_datum >= date(2026, 1, 1),
                ProjektZuweisung.end_datum <= date(2026, 12, 31)
            ).delete()

            # 3. Tabelle auslesen und in Blöcke (Start- bis Enddatum) zusammenfassen
            for row in range(self.table.rowCount()):
                ma_id = self.table.cellWidget(row, 0).currentData()
                if ma_id is None:
                    continue

                status_typ = self.table.cellWidget(row, 1).currentData()
                anteil_pct = self.table.cellWidget(row, 2).value() / 100.0 # Aus 50% wird 0.5

                # Variablen für die Block-Erkennung
                current_projekt_id = None
                block_start_monat = None

                for col in range(4, 16):
                    monat = col - 3 # Spalte 4 = Monat 1 (Januar)
                    projekt_id = self.table.cellWidget(row, col).currentData()

                    # Hat sich das Projekt im Vergleich zum Vormonat geändert?
                    if projekt_id != current_projekt_id:
                        
                        # Wenn wir vorher in einem Block waren, diesen jetzt abschließen und speichern!
                        if current_projekt_id is not None:
                            # Wir ermitteln den letzten Tag des End-Monats (z.B. 28., 30. oder 31.)
                            letzter_tag = calendar.monthrange(2026, monat - 1)[1]
                            
                            neue_zuweisung = ProjektZuweisung(
                                mitarbeiter_id=ma_id,
                                projekt_id=current_projekt_id,
                                typ=status_typ,
                                anteil_pct=anteil_pct,
                                start_datum=date(2026, block_start_monat, 1),
                                end_datum=date(2026, monat - 1, letzter_tag)
                            )
                            session.add(neue_zuweisung)

                        # Neuen Block starten
                        current_projekt_id = projekt_id
                        block_start_monat = monat

                # Schleife zu Ende (Dezember erreicht). Ist noch ein Block offen?
                if current_projekt_id is not None:
                    letzter_tag = calendar.monthrange(2026, 12)[1]
                    neue_zuweisung = ProjektZuweisung(
                        mitarbeiter_id=ma_id,
                        projekt_id=current_projekt_id,
                        typ=status_typ,
                        anteil_pct=anteil_pct,
                        start_datum=date(2026, block_start_monat, 1),
                        end_datum=date(2026, 12, letzter_tag)
                    )
                    session.add(neue_zuweisung)

            # Alles sicher in die Datenbank schreiben
            session.commit()
            QMessageBox.information(self, "Erfolg", "Alle Zuweisungen wurden erfolgreich in der Datenbank gespeichert!")
            
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Datenbank-Fehler", f"Fehler beim Speichern:\n{str(e)}")
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
            
        # Den PDF-Exporter aufrufen
        from gui.components.pdf_exporter import export_mitarbeiter_pdf
        export_mitarbeiter_pdf(self, ma_id, 2026)            