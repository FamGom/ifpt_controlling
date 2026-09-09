from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QLineEdit, 
                             QDoubleSpinBox, QDialogButtonBox, QGroupBox, QSplitter, QComboBox)
from PyQt6.QtCore import Qt
from sqlalchemy.exc import IntegrityError

from datetime import date

from core.database import get_session
from core.models import InstitutsKonto, OverheadRegel, KontoBuchung

class KontoBearbeitenDialog(QDialog):
    def __init__(self, konto_id=None, parent=None):
        super().__init__(parent)
        self.konto_id = konto_id
        self.setWindowTitle("Instituts-Konto bearbeiten" if konto_id else "Neues Konto anlegen")
        self.resize(450, 250)
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
        
        # NEU: Start-Guthaben / Manueller Kontostand
        self.spin_guthaben = QDoubleSpinBox()
        self.spin_guthaben.setRange(-99999999.0, 99999999.0)
        self.spin_guthaben.setDecimals(2)
        self.spin_guthaben.setGroupSeparatorShown(True)
        self.spin_guthaben.setSuffix(" €")
        form.addRow("Aktueller Kontostand:", self.spin_guthaben)
        
        layout.addLayout(form)
        
        info = QLabel("<i>Hinweis: Abgeschlossene Projekte buchen ihren Overhead automatisch auf diesen Kontostand.</i>")
        info.setStyleSheet("color: gray; font-size: 8pt;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
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
                self.spin_guthaben.setValue(k.guthaben or 0.0)
        finally:
            session.close()

    def speichern(self):
        if not self.txt_name.text().strip(): return
        session = get_session()
        try:
            k = session.query(InstitutsKonto).filter_by(id=self.konto_id).first() if self.konto_id else InstitutsKonto()
            if not self.konto_id: session.add(k)
                
            k.name = self.txt_name.text().strip()
            k.kontonummer = self.txt_nummer.text().strip()
            
            # NEU: Differenz berechnen und als Buchung ablegen
            alter_stand = k.guthaben or 0.0
            neuer_stand = self.spin_guthaben.value()
            differenz = neuer_stand - alter_stand
            
            if differenz != 0:
                buchung = KontoBuchung(
                    konto=k,
                    datum=date.today(),
                    beschreibung="Manuelle Anpassung / Startsaldo",
                    betrag=differenz
                )
                session.add(buchung)
                k.guthaben = neuer_stand
            
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
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
        btn_k_hist = QPushButton("📜 Historie / Kontoauszug"); btn_k_hist.clicked.connect(self.show_historie) # NEU
        btn_k_umbuchung = QPushButton("🔄 Umbuchung"); btn_k_umbuchung.clicked.connect(self.umbuchen)
        
        tool_k.addWidget(btn_k_neu); tool_k.addWidget(btn_k_edit); tool_k.addWidget(btn_k_del)
        tool_k.addWidget(btn_k_hist); tool_k.addWidget(btn_k_umbuchung); tool_k.addStretch()
        lay_konten.addLayout(tool_k)
        
        self.tab_konten = QTableWidget()
        # NEU: Spalte für den Kontostand eingefügt
        self.tab_konten.setColumnCount(4)
        self.tab_konten.setHorizontalHeaderLabels(["ID", "Kontoname / Topf", "Kontonummer", "Aktueller Kontostand"])
        self.tab_konten.setColumnHidden(0, True)
        self.tab_konten.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tab_konten.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
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
                
                # NEU: Kontostand formatiert einfügen
                guthaben = k.guthaben or 0.0
                g_str = f"{guthaben:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
                item_g = QTableWidgetItem(g_str)
                item_g.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tab_konten.setItem(r, 3, item_g)
                
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

    def show_historie(self):
        row = self.tab_konten.currentRow()
        if row >= 0:
            k_id = int(self.tab_konten.item(row, 0).text())
            k_name = self.tab_konten.item(row, 1).text()
            KontoHistorieDialog(k_id, k_name, self).exec()    
        
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

    def umbuchen(self):
        if KontoUmbuchungDialog(parent=self).exec() == QDialog.DialogCode.Accepted:
            self.load_data()

class ValueItem(QTableWidgetItem):
    """Hilfsklasse für korrektes Sortieren von Zahlen- und Datumswerten im QTableWidget"""
    def __init__(self, display_str, sort_value):
        super().__init__(display_str)
        self.setData(Qt.ItemDataRole.UserRole, sort_value)
        
    def __lt__(self, other):
        # Sortiert nach dem hinterlegten unsichtbaren Roh-Wert (z.B. Float oder Date-Ordinal)
        return self.data(Qt.ItemDataRole.UserRole) < other.data(Qt.ItemDataRole.UserRole)

class KontoHistorieDialog(QDialog):
    def __init__(self, konto_id, konto_name, parent=None):
        super().__init__(parent)
        self.konto_id = konto_id
        self.setWindowTitle(f"Kontoauszug: {konto_name}")
        self.resize(850, 450)
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Live-Filter ---
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("🔍 Filter:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Überall suchen...")
        self.search_box.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_box)
        layout.addLayout(filter_layout)
        
        # --- Tabelle ---
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Datum", "Vorgang", "Gegenkonto / Projekt", "Verwendungszweck", "Betrag (€)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        self.table.setSortingEnabled(True) 
        layout.addWidget(self.table)

    def load_data(self):
        session = get_session()
        try:
            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)
            
            buchungen = session.query(KontoBuchung).filter_by(konto_id=self.konto_id).order_by(KontoBuchung.datum.desc(), KontoBuchung.id.desc()).all()
            
            for b in buchungen:
                r = self.table.rowCount()
                self.table.insertRow(r)
                
                # 1. Datum
                item_date = ValueItem(b.datum.strftime('%d.%m.%Y'), b.datum.toordinal())
                self.table.setItem(r, 0, item_date)
                
                # 2. Smart-Parsing: Vorgang, Gegenkonto und Zweck trennen
                vorgang = "Systembuchung"
                gegenkonto = "-"
                zweck = b.beschreibung
                
                if b.beschreibung.startswith("Umbuchung von '"):
                    vorgang = "Eingang (Umbuchung)"
                    parts = b.beschreibung.split("': ", 1)
                    gegenkonto = parts[0].replace("Umbuchung von '", "")
                    zweck = parts[1] if len(parts) > 1 else "Manuelle Umbuchung"
                elif b.beschreibung.startswith("Umbuchung an '"):
                    vorgang = "Ausgang (Umbuchung)"
                    parts = b.beschreibung.split("': ", 1)
                    gegenkonto = parts[0].replace("Umbuchung an '", "")
                    zweck = parts[1] if len(parts) > 1 else "Manuelle Umbuchung"
                elif b.beschreibung.startswith("Projektabschluss:"):
                    vorgang = "Projektabschluss"
                    parts = b.beschreibung.split(" (", 1)
                    gegenkonto = parts[0].replace("Projektabschluss: ", "").strip()
                    zweck = "Abschluss (" + parts[1] if len(parts) > 1 else "Overhead & Restmittel"
                elif b.beschreibung.startswith("Manuelle Anpassung"):
                    vorgang = "Manuelle Korrektur"
                    gegenkonto = "-"
                    zweck = b.beschreibung
                
                self.table.setItem(r, 1, QTableWidgetItem(vorgang))
                self.table.setItem(r, 2, QTableWidgetItem(gegenkonto))
                self.table.setItem(r, 3, QTableWidgetItem(zweck))
                
                # 3. Betrag
                b_str = f"{b.betrag:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
                item_b = ValueItem(b_str, b.betrag)
                item_b.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                if b.betrag > 0: item_b.setForeground(Qt.GlobalColor.green)
                elif b.betrag < 0: item_b.setForeground(Qt.GlobalColor.red)
                self.table.setItem(r, 4, item_b)
                
            self.table.setSortingEnabled(True)
            self.table.sortItems(0, Qt.SortOrder.DescendingOrder)
            
        finally:
            session.close()

    def apply_filter(self):
        text = self.search_box.text().lower()
        for r in range(self.table.rowCount()):
            show = False
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item and text in item.text().lower():
                    show = True
                    break
            self.table.setRowHidden(r, not show)

class KontoUmbuchungDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Umbuchung zwischen Instituts-Konten")
        self.resize(450, 250)
        self.konten_cache = []
        self.setup_ui()
        self.load_konten()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.combo_quelle = QComboBox()
        form.addRow("Von Konto (Quelle):", self.combo_quelle)
        
        self.combo_ziel = QComboBox()
        form.addRow("Nach Konto (Ziel):", self.combo_ziel)
        
        self.spin_betrag = QDoubleSpinBox()
        self.spin_betrag.setRange(0.01, 99999999.0)
        self.spin_betrag.setDecimals(2)
        self.spin_betrag.setGroupSeparatorShown(True)
        self.spin_betrag.setSuffix(" €")
        form.addRow("Betrag:", self.spin_betrag)
        
        self.txt_zweck = QLineEdit()
        self.txt_zweck.setPlaceholderText("z.B. Ausgleich für Hardware-Kauf")
        form.addRow("Verwendungszweck:", self.txt_zweck)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.speichern)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_konten(self):
        session = get_session()
        try:
            self.konten_cache = session.query(InstitutsKonto).order_by(InstitutsKonto.name).all()
            for k in self.konten_cache:
                text = f"{k.name} ({k.guthaben or 0.0:,.2f} €)".replace(",", "X").replace(".", ",").replace("X", ".")
                self.combo_quelle.addItem(text, k.id)
                self.combo_ziel.addItem(text, k.id)
        finally:
            session.close()

    def speichern(self):
        q_id = self.combo_quelle.currentData()
        z_id = self.combo_ziel.currentData()
        betrag = self.spin_betrag.value()
        zweck = self.txt_zweck.text().strip()
        
        if q_id == z_id:
            QMessageBox.warning(self, "Fehler", "Quell- und Zielkonto dürfen nicht identisch sein.")
            return
            
        if not zweck:
            QMessageBox.warning(self, "Fehler", "Bitte einen Verwendungszweck eingeben.")
            return
            
        session = get_session()
        try:
            konto_q = session.query(InstitutsKonto).filter_by(id=q_id).first()
            konto_z = session.query(InstitutsKonto).filter_by(id=z_id).first()
            
            # Abbuchung (Quelle)
            konto_q.guthaben = (konto_q.guthaben or 0.0) - betrag
            buchung_q = KontoBuchung(
                konto=konto_q,
                datum=date.today(),
                beschreibung=f"Umbuchung an '{konto_z.name}': {zweck}",
                betrag=-betrag
            )
            session.add(buchung_q)
            
            # Zubuchung (Ziel)
            konto_z.guthaben = (konto_z.guthaben or 0.0) + betrag
            buchung_z = KontoBuchung(
                konto=konto_z,
                datum=date.today(),
                beschreibung=f"Umbuchung von '{konto_q.name}': {zweck}",
                betrag=betrag
            )
            session.add(buchung_z)
            
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", str(e))
        finally:
            session.close()            