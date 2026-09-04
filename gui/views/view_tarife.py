from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QDateEdit, 
                             QDoubleSpinBox, QDialogButtonBox, QApplication)
from PyQt6.QtCore import Qt, QDate

from core.database import get_session
from core.models import TarifTabelle



EG_LISTE = ["15Ü", "15", "14", "13Ü", "13", "12", "11", "10", "9b", "9a", "8", "7", "6", "5", "4", "3", "2Ü", "2", "1"]

class TarifMatrixDialog(QDialog):
    """Dialog zur Eingabe einer kompletten TV-L Tabelle als 2D-Matrix."""
    def __init__(self, ref_datum=None, parent=None, is_copy=False):
        super().__init__(parent)
        self.ref_datum = ref_datum  # Das gueltig_ab Datum, das als Schlüssel für diese Tabelle dient
        self.is_copy = is_copy
        
        titel = "TV-L Entgelttabelle bearbeiten"
        if not ref_datum: titel = "Neue TV-L Entgelttabelle anlegen"
        elif is_copy: titel = "TV-L Entgelttabelle duplizieren"
        
        self.setWindowTitle(titel)
        self.resize(1100, 750)
        
        layout = QVBoxLayout(self)
        
        # --- KOPFDATEN ---
        form_layout = QFormLayout()
        
        self.date_ab = QDateEdit()
        self.date_ab.setCalendarPopup(True)
        self.date_ab.setDate(QDate.currentDate())
        form_layout.addRow("Gültigkeit der Tabelle ab:", self.date_ab)
        
        self.date_bis = QDateEdit()
        self.date_bis.setCalendarPopup(True)
        self.date_bis.setSpecialValueText(" Unbefristet ")
        self.date_bis.setDate(QDate(2099, 12, 31))
        form_layout.addRow("Gültig bis (optional):", self.date_bis)
        
        layout.addLayout(form_layout)
        
        info = QLabel("<i>Tragen Sie die Beträge exakt so ein, wie sie in der TV-L Tabelle stehen. Felder, die in der Realität leer sind (z.B. E13Ü Stufe 1), einfach auf 0,00 € belassen.</i>")
        info.setStyleSheet("color: #7F8C8D; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # --- DIE MATRIX ---
        self.table = QTableWidget()
        self.table.setRowCount(len(EG_LISTE))
        self.spalten = ["Stufe 1", "Stufe 2", "Stufe 3", "Stufe 4", "Stufe 5", "Stufe 6", "JSZ Faktor (%)"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.setVerticalHeaderLabels([f"E {eg}" for eg in EG_LISTE])
        
        for c in range(6): self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        # Zellen mit SpinBoxen füllen
        for r, eg in enumerate(EG_LISTE):
            # Gehaltsstufen 1 bis 6
            for c in range(6):
                spin = QDoubleSpinBox()
                spin.setRange(0.0, 99999.0)
                spin.setDecimals(2)
                spin.setGroupSeparatorShown(True)
                spin.setAlignment(Qt.AlignmentFlag.AlignRight)
                
                # DARK MODE FIX: Nur Textfarbe ändern, den Hintergrund in Ruhe lassen!
                if "13" in eg: 
                    spin.setStyleSheet("color: #5DADE2; font-weight: bold;") # Kräftiges Hellblau für E13
                    
                self.table.setCellWidget(r, c, spin)
            
           # JSZ Faktor (Spalte 7)
            spin_jsz = QDoubleSpinBox()
            spin_jsz.setRange(0.0, 100.0)
            spin_jsz.setDecimals(4)  # Mind. 4 Nachkommastellen!
            spin_jsz.setSuffix(" %")
            
            # NEU: Intelligente Standardwerte nach TV-L Vorgabe!
            if eg in ["15Ü", "15", "14"]:
                default_jsz = 32.53
            elif eg in ["13Ü", "13", "12"]:
                default_jsz = 46.47
            elif eg in ["11", "10", "9b", "9a"]:
                default_jsz = 74.35
            elif eg in ["8", "7", "6", "5"]:
                default_jsz = 88.14
            else: # 4, 3, 2Ü, 2, 1
                default_jsz = 87.43
                
            spin_jsz.setValue(default_jsz) 
            spin_jsz.setAlignment(Qt.AlignmentFlag.AlignRight)
            
            # DARK MODE FIX: Goldgelbe Schrift für die JSZ
            spin_jsz.setStyleSheet("color: #F4D03F; font-weight: bold;")
            self.table.setCellWidget(r, 6, spin_jsz)
            
        layout.addWidget(self.table)
        
        # --- BUTTONS ---
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.daten_speichern)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        if self.ref_datum:
            self.lade_daten()

    def lade_daten(self):
        session = get_session()
        try:
            tarife = session.query(TarifTabelle).filter_by(gueltig_ab=self.ref_datum).all()
            if not tarife: return
            
            if not self.is_copy:
                self.date_ab.setDate(QDate(self.ref_datum.year, self.ref_datum.month, self.ref_datum.day))
                # Nimm das gueltig_bis vom ersten gefundenen Eintrag
                gb = tarife[0].gueltig_bis
                if gb: self.date_bis.setDate(QDate(gb.year, gb.month, gb.day))
                else: self.date_bis.setDate(QDate(2099, 12, 31))
            else:
                # Beim Kopieren setzen wir das Startdatum auf heute, Rest bleibt erhalten
                self.date_ab.setDate(QDate.currentDate())
                self.date_bis.setDate(QDate(2099, 12, 31))

            # Matrix befüllen
            for t in tarife:
                try:
                    r = EG_LISTE.index(t.entgeltgruppe)
                    c = t.stufe - 1 # Stufe 1 = Index 0
                    
                    spin_betrag = self.table.cellWidget(r, c)
                    if spin_betrag: spin_betrag.setValue(t.betrag_euro)
                    
                    spin_jsz = self.table.cellWidget(r, 6)
                    if spin_jsz and t.jsz_prozent is not None:
                        spin_jsz.setValue(t.jsz_prozent * 100.0)
                except ValueError:
                    pass # Entgeltgruppe aus alter DB nicht in unserer aktuellen Liste
        finally:
            session.close()

    def daten_speichern(self):
        start_date = self.date_ab.date().toPyDate()
        end_date = self.date_bis.date().toPyDate()
        if end_date.year == 2099: end_date = None
        
        if end_date and end_date < start_date:
            QMessageBox.warning(self, "Fehler", "Das Enddatum darf nicht vor dem Startdatum liegen.")
            return

        session = get_session()
        try:
            # Wenn wir bearbeiten, löschen wir die alte Tabelle dieses Datums und schreiben sie neu
            if self.ref_datum and not self.is_copy:
                session.query(TarifTabelle).filter_by(gueltig_ab=self.ref_datum).delete()
                
            # Wenn wir neu anlegen oder kopieren, prüfen wir ob das Datum schon existiert
            elif session.query(TarifTabelle).filter_by(gueltig_ab=start_date).first():
                if QMessageBox.warning(self, "Datum existiert", "Für dieses 'Gültig ab' Datum existiert bereits eine Tabelle. Möchten Sie diese überschreiben?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                    session.query(TarifTabelle).filter_by(gueltig_ab=start_date).delete()
                else:
                    return

            eintraege_gespeichert = 0
            for r, eg in enumerate(EG_LISTE):
                jsz_pct = self.table.cellWidget(r, 6).value() / 100.0
                
                for c in range(6):
                    betrag = self.table.cellWidget(r, c).value()
                    # Nur speichern, wenn ein Betrag eingetragen wurde (> 0)
                    if betrag > 0:
                        t = TarifTabelle(
                            entgeltgruppe=eg,
                            stufe=c + 1,
                            betrag_euro=betrag,
                            jsz_prozent=jsz_pct,
                            gueltig_ab=start_date,
                            gueltig_bis=end_date
                        )
                        session.add(t)
                        eintraege_gespeichert += 1
                        
            if eintraege_gespeichert == 0:
                QMessageBox.warning(self, "Leer", "Die Tabelle ist komplett leer. Bitte tragen Sie Beträge ein.")
                return
                
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", f"Konnte Tarife nicht speichern:\n{str(e)}")
        finally:
            session.close()

    def keyPressEvent(self, event):
        """Fängt Tastendrücke ab, um Strg+V (Copy-Paste) zu erkennen."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V:
            self.paste_from_clipboard()
        else:
            super().keyPressEvent(event)

    def paste_from_clipboard(self):
        """Liest Excel-Daten aus der Zwischenablage und füllt die Matrix."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text: return

        # Start-Zelle ermitteln (Dort wo der User reingeklickt hat, ansonsten oben links bei 0,0)
        start_row = self.table.currentRow() if self.table.currentRow() >= 0 else 0
        start_col = self.table.currentColumn() if self.table.currentColumn() >= 0 else 0

        # Excel trennt Zeilen mit Enter (\n) und Spalten mit Tabulator (\t)
        zeilen = text.strip('\n').split('\n')
        for r_offset, zeilen_text in enumerate(zeilen):
            spalten = zeilen_text.split('\t')
            for c_offset, zellen_text in enumerate(spalten):
                r = start_row + r_offset
                c = start_col + c_offset

                if r < self.table.rowCount() and c < self.table.columnCount():
                    widget = self.table.cellWidget(r, c)
                    if widget and isinstance(widget, QDoubleSpinBox):
                        # 1. Text bereinigen (Excel kopiert oft Leerzeichen oder €-Zeichen mit)
                        val_str = zellen_text.strip().replace('€', '').replace(' ', '')
                        if not val_str: continue

                        # 2. Deutsches Zahlenformat knacken (z.B. "4.629,74" -> "4629.74")
                        if ',' in val_str and '.' in val_str:
                            if val_str.rfind(',') > val_str.rfind('.'):
                                val_str = val_str.replace('.', '').replace(',', '.')
                            else:
                                val_str = val_str.replace(',', '')
                        elif ',' in val_str:
                            val_str = val_str.replace(',', '.')

                        # 3. Wert in die SpinBox eintragen
                        try:
                            widget.setValue(float(val_str))
                        except ValueError:
                            pass # Falls versehentlich Text (z.B. "Stufe 1") kopiert wurde, ignorieren wir es einfach


class TarifeView(QWidget):
    """Hauptansicht für die TV-L Tariftabellen."""
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_tarife()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("TV-L Entgelttabellen (Stammdaten)")
        title.setProperty("title", "true")
        layout.addWidget(title)
        
        info = QLabel("Das System greift automatisch auf die Tabelle zu, die für den jeweiligen Abrechnungsmonat gültig ist.")
        info.setStyleSheet("color: #7F8C8D; margin-bottom: 10px;")
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neue Tabelle anlegen")
        btn_add.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self.tabelle_hinzufuegen)
        
        btn_edit = QPushButton("✏️ Tabelle bearbeiten")
        btn_edit.setStyleSheet("background-color: #2980B9; color: white; padding: 6px;")
        btn_edit.clicked.connect(self.tabelle_bearbeiten)
        
        btn_copy = QPushButton("📑 Tabelle duplizieren (Neues Jahr)")
        btn_copy.setStyleSheet("background-color: #8E44AD; color: white; padding: 6px;")
        btn_copy.clicked.connect(self.tabelle_duplizieren)
        
        btn_del = QPushButton("🗑️ Tabelle löschen")
        btn_del.setStyleSheet("background-color: #C0392B; color: white; padding: 6px;")
        btn_del.clicked.connect(self.tabelle_loeschen)
        
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_copy)
        toolbar.addWidget(btn_del)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.spalten = ["Gültig ab (Referenzdatum)", "Gültig bis", "Anzahl gespeicherter EG-Stufen"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.tabelle_bearbeiten)
        
        layout.addWidget(self.table)

    def load_tarife(self):
        session = get_session()
        self.table.setRowCount(0)
        try:
            # Wir gruppieren die Tabellen nach dem Startdatum
            dates = session.query(TarifTabelle.gueltig_ab).distinct().order_by(TarifTabelle.gueltig_ab.desc()).all()
            
            for (start_date,) in dates:
                # Hole den ersten Eintrag für dieses Datum, um 'gueltig_bis' zu lesen
                first_entry = session.query(TarifTabelle).filter_by(gueltig_ab=start_date).first()
                count = session.query(TarifTabelle).filter_by(gueltig_ab=start_date).count()
                
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                self.table.setItem(row, 0, QTableWidgetItem(start_date.strftime('%Y-%m-%d')))
                
                bis_str = first_entry.gueltig_bis.strftime('%d.%m.%Y') if first_entry.gueltig_bis else "Unbefristet"
                self.table.setItem(row, 1, QTableWidgetItem(bis_str))
                
                self.table.setItem(row, 2, QTableWidgetItem(f"{count} Tarif-Zellen hinterlegt"))
        finally:
            session.close()

    def tabelle_hinzufuegen(self):
        dialog = TarifMatrixDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.load_tarife()

    def tabelle_bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        ref_datum_str = self.table.item(row, 0).text()
        ref_datum = date.fromisoformat(ref_datum_str)
        
        dialog = TarifMatrixDialog(ref_datum=ref_datum, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.load_tarife()

    def tabelle_duplizieren(self):
        row = self.table.currentRow()
        if row < 0: 
            QMessageBox.warning(self, "Achtung", "Bitte wählen Sie eine Tabelle aus, die Sie kopieren möchten.")
            return
        ref_datum_str = self.table.item(row, 0).text()
        ref_datum = date.fromisoformat(ref_datum_str)
        
        dialog = TarifMatrixDialog(ref_datum=ref_datum, parent=self, is_copy=True)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.load_tarife()

    def tabelle_loeschen(self):
        row = self.table.currentRow()
        if row < 0: return
        ref_datum_str = self.table.item(row, 0).text()
        
        if QMessageBox.question(self, "Löschen", f"Möchten Sie die gesamte TV-L Tabelle (Gültig ab {ref_datum_str}) löschen?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                ref_datum = date.fromisoformat(ref_datum_str)
                session.query(TarifTabelle).filter_by(gueltig_ab=ref_datum).delete()
                session.commit()
                self.load_tarife()
            finally:
                session.close()