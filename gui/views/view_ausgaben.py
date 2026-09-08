from datetime import date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QDialog, QFormLayout, QLineEdit, 
                             QDateEdit, QDoubleSpinBox, QDialogButtonBox, QComboBox, QSplitter, QCompleter)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models import (AusgabeKopf, AusgabePosition, Kostenart, AusgabenStatus, 
                         Projekt, ProjektStatus, Mitarbeiter)

class AusgabeBearbeitenDialog(QDialog):
    def __init__(self, kopf_id=None, copy_from_plan=False, parent=None):
        super().__init__(parent)
        self.kopf_id = kopf_id
        self.copy_from_plan = copy_from_plan
        self.projekte_cache = []
        self.mitarbeiter_cache = []
        self.lieferanten_cache = []
        
        titel = "Bestellung / Rechnung bearbeiten" if kopf_id and not copy_from_plan else "Neue Ausgabe / Plan-Budget erfassen"
        self.setWindowTitle(titel)
        self.resize(1100, 700)
        
        self.lade_caches()
        self.setup_ui()
        
        if self.kopf_id:
            self.lade_daten()
        else:
            self.add_position_row()

    def lade_caches(self):
        session = get_session()
        try:
            self.projekte_cache = session.query(Projekt).order_by(Projekt.projektname).all()
            self.mitarbeiter_cache = session.query(Mitarbeiter).order_by(Mitarbeiter.nachname).all()
            lieferanten = session.query(AusgabeKopf.lieferant).distinct().all()
            self.lieferanten_cache = [l[0] for l in lieferanten if l[0]]
        finally:
            session.close()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # --- KOPFDATEN ---
        widget_kopf = QWidget()
        layout_kopf = QFormLayout(widget_kopf)
        
        self.txt_titel = QLineEdit()
        layout_kopf.addRow("Titel / Verwendungszweck:", self.txt_titel)
        
        self.combo_status = QComboBox()
        for s in AusgabenStatus:
            self.combo_status.addItem(s.value, s)
        layout_kopf.addRow("Status:", self.combo_status)
        
        self.txt_lieferant = QLineEdit()
        completer = QCompleter(self.lieferanten_cache, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.txt_lieferant.setCompleter(completer)
        layout_kopf.addRow("Lieferant / Kreditor:", self.txt_lieferant)
        
        self.txt_rechnung = QLineEdit()
        layout_kopf.addRow("Rechnungsnummer:", self.txt_rechnung)
        
        row_dates = QHBoxLayout()
        self.date_bestell = QDateEdit(); self.date_bestell.setCalendarPopup(True); self.date_bestell.setDate(QDate.currentDate())
        
        self.date_rech = QDateEdit(); self.date_rech.setCalendarPopup(True); self.date_rech.setSpecialValueText(" - ")
        self.date_rech.setDate(QDate(2099, 12, 31))
        
        btn_heute = QPushButton("📅 Heute")
        btn_heute.clicked.connect(lambda: self.date_rech.setDate(QDate.currentDate()))
        
        row_dates.addWidget(QLabel("Bestelldatum:")); row_dates.addWidget(self.date_bestell)
        row_dates.addSpacing(20)
        row_dates.addWidget(QLabel("Rechnungsdatum:")); row_dates.addWidget(self.date_rech)
        row_dates.addWidget(btn_heute)
        row_dates.addStretch()
        layout_kopf.addRow("Daten:", row_dates)
        
        self.combo_ma = QComboBox()
        self.combo_ma.addItem("Kein spezifischer Mitarbeiter (Standard)", None)
        for m in self.mitarbeiter_cache:
            self.combo_ma.addItem(f"{m.nachname}, {m.vorname}", m.id)
        layout_kopf.addRow("Reisender / Begünstigter (Optional):", self.combo_ma)
        
        splitter.addWidget(widget_kopf)
        
        # --- POSITIONEN ---
        widget_pos = QWidget()
        layout_pos = QVBoxLayout(widget_pos)
        layout_pos.addWidget(QLabel("<b>Bestell-Positionen (Splitt-Buchungen)</b>"))
        
        self.table_pos = QTableWidget()
        self.spalten = ["Projekt-Status", "Projekt", "Kostenart (Kategorie)", "Bezeichnung", "Betrag (€)", "Lfd.Nr. (Invest)"]
        self.table_pos.setColumnCount(len(self.spalten))
        self.table_pos.setHorizontalHeaderLabels(self.spalten)
        self.table_pos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_pos.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_pos.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout_pos.addWidget(self.table_pos)
        
        toolbar_pos = QHBoxLayout()
        btn_add = QPushButton("➕ Position hinzufügen")
        btn_add.clicked.connect(self.add_position_row)
        btn_del = QPushButton("🗑️ Zeile löschen")
        btn_del.clicked.connect(lambda: self.table_pos.removeRow(self.table_pos.currentRow()) if self.table_pos.currentRow() >= 0 else None)
        toolbar_pos.addWidget(btn_add); toolbar_pos.addWidget(btn_del); toolbar_pos.addStretch()
        layout_pos.addLayout(toolbar_pos)
        
        splitter.addWidget(widget_pos)
        splitter.setSizes([250, 450])
        main_layout.addWidget(splitter)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.daten_speichern)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def add_position_row(self, proj_id=None, kostenart=None, bez="", betrag=0.0, invest_nr=""):
        row = self.table_pos.rowCount()
        self.table_pos.insertRow(row)
        
        c_status = QComboBox()
        c_status.addItems(["Laufend (Bewilligt)", "Beantragt", "Abgeschlossen", "Alle"])
        
        c_proj = QComboBox()
        
        def update_projekte(stat_text):
            c_proj.blockSignals(True)
            c_proj.clear()
            for p in self.projekte_cache:
                if stat_text == "Laufend (Bewilligt)" and p.status != ProjektStatus.BEWILLIGT: continue
                if stat_text == "Beantragt" and p.status != ProjektStatus.BEANTRAGT: continue
                if stat_text == "Abgeschlossen" and p.status not in [ProjektStatus.ABGESCHLOSSEN, getattr(ProjektStatus, "BEENDET", None)]: continue
                c_proj.addItem(p.projektname, p.id)
                
            if proj_id and c_proj.findData(proj_id) >= 0:
                c_proj.setCurrentIndex(c_proj.findData(proj_id))
            c_proj.blockSignals(False)

        c_status.currentTextChanged.connect(update_projekte)
        
        # FIX: Harten Ziel-Status ermitteln und Dropdown füllen (ohne auf Signale zu warten)
        target_status = "Laufend (Bewilligt)"
        if proj_id:
            p_obj = next((p for p in self.projekte_cache if p.id == proj_id), None)
            if p_obj:
                if p_obj.status == ProjektStatus.BEWILLIGT: target_status = "Laufend (Bewilligt)"
                elif p_obj.status == ProjektStatus.BEANTRAGT: target_status = "Beantragt"
                else: target_status = "Alle"

        c_status.blockSignals(True)
        c_status.setCurrentText(target_status)
        c_status.blockSignals(False)
        
        # FIX: Das Projekt-Dropdown zwingend manuell befüllen!
        update_projekte(target_status)

        self.table_pos.setCellWidget(row, 0, c_status)
        self.table_pos.setCellWidget(row, 1, c_proj)
        
        c_art = QComboBox()
        for a in Kostenart: c_art.addItem(a.value, a)
        if kostenart: c_art.setCurrentIndex(c_art.findData(kostenart))
        self.table_pos.setCellWidget(row, 2, c_art)
        
        txt_bez = QLineEdit(bez)
        self.table_pos.setCellWidget(row, 3, txt_bez)
        
        spin_betrag = QDoubleSpinBox()
        spin_betrag.setRange(-9999999.0, 9999999.0)
        spin_betrag.setDecimals(2)
        spin_betrag.setGroupSeparatorShown(True)
        spin_betrag.setSuffix(" €")
        spin_betrag.setValue(betrag)
        self.table_pos.setCellWidget(row, 4, spin_betrag)
        
        txt_inv = QLineEdit(invest_nr if invest_nr else "")
        txt_inv.setPlaceholderText("Nur bei >800€")
        self.table_pos.setCellWidget(row, 5, txt_inv)

    def lade_daten(self):
        session = get_session()
        try:
            kopf = session.query(AusgabeKopf).filter_by(id=self.kopf_id).first()
            if not kopf: return
            
            self.txt_titel.setText(kopf.titel)
            self.txt_lieferant.setText(kopf.lieferant or "")
            self.txt_rechnung.setText(kopf.rechnungsnummer or "")
            
            if kopf.bestelldatum: self.date_bestell.setDate(QDate(kopf.bestelldatum.year, kopf.bestelldatum.month, kopf.bestelldatum.day))
            if kopf.rechnungsdatum: self.date_rech.setDate(QDate(kopf.rechnungsdatum.year, kopf.rechnungsdatum.month, kopf.rechnungsdatum.day))
            
            idx_s = self.combo_status.findData(kopf.status)
            if idx_s >= 0: self.combo_status.setCurrentIndex(idx_s)
            
            if kopf.beguenstigter_mitarbeiter_id:
                idx_m = self.combo_ma.findData(kopf.beguenstigter_mitarbeiter_id)
                if idx_m >= 0: self.combo_ma.setCurrentIndex(idx_m)
                
            if self.copy_from_plan:
                idx_b = self.combo_status.findData(AusgabenStatus.BESTELLT)
                if idx_b >= 0: self.combo_status.setCurrentIndex(idx_b)
                self.txt_titel.setText(f"{kopf.titel} (Teil-Abruf)")

            for pos in kopf.positionen:
                self.add_position_row(pos.projekt_id, pos.kostenart, pos.bezeichnung, pos.betrag_euro, pos.lfd_nr_invest)
        finally:
            session.close()

    def daten_speichern(self):
        if not self.txt_titel.text().strip():
            QMessageBox.warning(self, "Fehler", "Bitte einen Verwendungszweck eingeben.")
            return
            
        session = get_session()
        try:
            if self.kopf_id and not self.copy_from_plan:
                kopf = session.query(AusgabeKopf).filter_by(id=self.kopf_id).first()
                session.query(AusgabePosition).filter_by(kopf_id=kopf.id).delete()
            else:
                kopf = AusgabeKopf()
                session.add(kopf)
                
            kopf.titel = self.txt_titel.text().strip()
            kopf.status = self.combo_status.currentData()
            kopf.lieferant = self.txt_lieferant.text().strip()
            kopf.rechnungsnummer = self.txt_rechnung.text().strip()
            kopf.bestelldatum = self.date_bestell.date().toPyDate()
            
            r_date = self.date_rech.date().toPyDate()
            kopf.rechnungsdatum = None if r_date.year == 2099 else r_date
            kopf.beguenstigter_mitarbeiter_id = self.combo_ma.currentData()
            
            # Positionen speichern
            for r in range(self.table_pos.rowCount()):
                p_id = self.table_pos.cellWidget(r, 1).currentData()
                k_art = self.table_pos.cellWidget(r, 2).currentData()
                bez = self.table_pos.cellWidget(r, 3).text().strip()
                betrag = self.table_pos.cellWidget(r, 4).value()
                inv_nr = self.table_pos.cellWidget(r, 5).text().strip()
                
                if p_id and k_art and betrag != 0:
                    pos = AusgabePosition(
                        kopf=kopf, projekt_id=p_id, kostenart=k_art, 
                        bezeichnung=bez if bez else kopf.titel, 
                        betrag_euro=betrag, lfd_nr_invest=inv_nr
                    )
                    session.add(pos)

            # AUTOMATISCHER PLAN-ABZUG (Teilabruf)
            if self.copy_from_plan and self.kopf_id:
                orig_plan = session.query(AusgabeKopf).filter_by(id=self.kopf_id).first()
                if orig_plan:
                    for new_pos in kopf.positionen:
                        for orig_pos in orig_plan.positionen:
                            if orig_pos.projekt_id == new_pos.projekt_id and orig_pos.kostenart == new_pos.kostenart:
                                orig_pos.betrag_euro -= new_pos.betrag_euro
                                break
                    
                    # Leere Plan-Positionen (<=0) löschen
                    for p in list(orig_plan.positionen):
                        if p.betrag_euro <= 0.01:
                            session.delete(p)
                            
                    # Wenn der Plan komplett aufgebraucht ist, Kopf löschen
                    if not any(p.betrag_euro > 0.01 for p in orig_plan.positionen):
                        session.delete(orig_plan)
                        
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", str(e))
        finally:
            session.close()

class AusgabenView(QWidget):
    def __init__(self):
        super().__init__()
        self.projekte_cache = []
        self.setup_ui()
        self.load_projekte_filter()
        self.load_data()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Ausgaben-Journal (Sachmittel & Rechnungen)")
        title.setProperty("title", "true")
        layout.addWidget(title)
        
        info = QLabel("Teilabruf-Logik: Wenn Sie aus einem Plan bestellen und den Betrag anpassen, reduziert das System den Ursprungs-Plan automatisch.")
        info.setStyleSheet("color: #7F8C8D; margin-bottom: 5px;")
        layout.addWidget(info)
        
        # --- GLOBALE FILTER ---
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("<b>Filter:</b>"))
        
        self.filter_status = QComboBox()
        self.filter_status.addItems(["Alle Status", "Plan-Budget", "Bestellt (Obligo)", "Bezahlt (Ist)"])
        self.filter_status.currentIndexChanged.connect(self.load_data)
        
        self.filter_projekt = QComboBox()
        self.filter_projekt.currentIndexChanged.connect(self.load_data)
        
        filter_layout.addWidget(self.filter_status)
        filter_layout.addWidget(self.filter_projekt)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # --- SPALTEN-SUCH-FILTER ---
        search_layout = QHBoxLayout()
        self.search_titel = QLineEdit(); self.search_titel.setPlaceholderText("🔍 Titel filtern...")
        self.search_proj = QLineEdit(); self.search_proj.setPlaceholderText("🔍 Projekt filtern...")
        self.search_lief = QLineEdit(); self.search_lief.setPlaceholderText("🔍 Lieferant filtern...")
        
        self.search_titel.textChanged.connect(self.apply_text_filters)
        self.search_proj.textChanged.connect(self.apply_text_filters)
        self.search_lief.textChanged.connect(self.apply_text_filters)
        
        search_layout.addWidget(self.search_titel)
        search_layout.addWidget(self.search_proj)
        search_layout.addWidget(self.search_lief)
        layout.addLayout(search_layout)
        
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Neue freie Ausgabe")
        btn_add.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        btn_add.clicked.connect(self.neu_frei)
        
        btn_plan = QPushButton("🎯 Aus Plan-Budget bestellen")
        btn_plan.setStyleSheet("background-color: #8E44AD; color: white; font-weight: bold; padding: 6px;")
        btn_plan.clicked.connect(self.neu_aus_plan)
        
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.clicked.connect(self.bearbeiten)
        
        btn_del = QPushButton("🗑️ Löschen")
        btn_del.clicked.connect(self.loeschen)
        
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_plan); toolbar.addSpacing(20)
        toolbar.addWidget(btn_edit); toolbar.addWidget(btn_del); toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.table = QTableWidget()
        self.spalten = ["ID", "Status", "Titel / Zweck", "Projekt(e)", "Bestelldatum", "Rechnungsdatum", "Lieferant / MA", "Gesamtbetrag"]
        self.table.setColumnCount(len(self.spalten))
        self.table.setHorizontalHeaderLabels(self.spalten)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.bearbeiten)
        layout.addWidget(self.table)

    def load_projekte_filter(self):
        session = get_session()
        try:
            self.filter_projekt.blockSignals(True)
            self.filter_projekt.clear()
            self.filter_projekt.addItem("Alle Projekte", None)
            for p in session.query(Projekt).order_by(Projekt.projektname).all():
                self.filter_projekt.addItem(p.projektname, p.id)
            self.filter_projekt.blockSignals(False)
        finally:
            session.close()

    def load_data(self):
        session = get_session()
        self.table.setRowCount(0)
        try:
            query = session.query(AusgabeKopf)
            
            f_stat = self.filter_status.currentText()
            if f_stat == "Plan-Budget": query = query.filter_by(status=AusgabenStatus.PLAN)
            elif f_stat == "Bestellt (Obligo)": query = query.filter_by(status=AusgabenStatus.BESTELLT)
            elif f_stat == "Bezahlt (Ist)": query = query.filter_by(status=AusgabenStatus.BEZAHLT)
                
            f_proj = self.filter_projekt.currentData()
            if f_proj:
                query = query.join(AusgabePosition).filter(AusgabePosition.projekt_id == f_proj)
                
            koepfe = query.order_by(AusgabeKopf.bestelldatum.desc()).all()
            
            for k in koepfe:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                self.table.setItem(row, 0, QTableWidgetItem(str(k.id)))
                
                status_item = QTableWidgetItem(k.status.value)
                if k.status == AusgabenStatus.PLAN: status_item.setForeground(QColor("#8E44AD"))
                elif k.status == AusgabenStatus.BESTELLT: status_item.setForeground(QColor("#F39C12"))
                elif k.status == AusgabenStatus.BEZAHLT: status_item.setForeground(QColor("#27AE60"))
                self.table.setItem(row, 1, status_item)
                
                self.table.setItem(row, 2, QTableWidgetItem(k.titel))
                
                # Projekte aggregieren und mit Zeilenumbruch darstellen
                projekte_liste = list(set([pos.projekt.projektname for pos in k.positionen if pos.projekt]))
                self.table.setItem(row, 3, QTableWidgetItem("\n".join(projekte_liste)))
                
                b_str = k.bestelldatum.strftime('%d.%m.%Y') if k.bestelldatum else "-"
                r_str = k.rechnungsdatum.strftime('%d.%m.%Y') if k.rechnungsdatum else "-"
                self.table.setItem(row, 4, QTableWidgetItem(b_str))
                self.table.setItem(row, 5, QTableWidgetItem(r_str))
                
                partner = k.lieferant or ""
                if k.beguenstigter_mitarbeiter_id and k.mitarbeiter:
                    partner = f"MA: {k.mitarbeiter.nachname}"
                self.table.setItem(row, 6, QTableWidgetItem(partner))
                
                if f_proj:
                    summe = sum([pos.betrag_euro for pos in k.positionen if pos.projekt_id == f_proj])
                else:
                    summe = sum([pos.betrag_euro for pos in k.positionen])
                    
                sum_item = QTableWidgetItem(f"{summe:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
                sum_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 7, sum_item)
                
            self.table.resizeRowsToContents()
            self.apply_text_filters()
        finally:
            session.close()

    def apply_text_filters(self):
        """Wendet die Such-Textfelder live auf die angezeigten Zeilen an."""
        t_filter = self.search_titel.text().lower()
        p_filter = self.search_proj.text().lower()
        l_filter = self.search_lief.text().lower()
        
        for r in range(self.table.rowCount()):
            t_text = self.table.item(r, 2).text().lower() if self.table.item(r, 2) else ""
            p_text = self.table.item(r, 3).text().lower() if self.table.item(r, 3) else ""
            l_text = self.table.item(r, 6).text().lower() if self.table.item(r, 6) else ""
            
            show = True
            if t_filter and t_filter not in t_text: show = False
            if p_filter and p_filter not in p_text: show = False
            if l_filter and l_filter not in l_text: show = False
            
            self.table.setRowHidden(r, not show)

    def neu_frei(self):
        if AusgabeBearbeitenDialog(parent=self).exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def neu_aus_plan(self):
        session = get_session()
        try:
            plaene = session.query(AusgabeKopf).filter_by(status=AusgabenStatus.PLAN).all()
            if not plaene:
                QMessageBox.information(self, "Leer", "Es gibt aktuell keine offenen Plan-Budgets im System.")
                return
        finally:
            session.close()
            
        row = self.table.currentRow()
        if row >= 0 and self.table.item(row, 1).text() == AusgabenStatus.PLAN.value:
            k_id = int(self.table.item(row, 0).text())
            if AusgabeBearbeitenDialog(kopf_id=k_id, copy_from_plan=True, parent=self).exec() == QDialog.DialogCode.Accepted:
                self.load_data()
        else:
            QMessageBox.information(self, "Hinweis", "Bitte markieren Sie zuerst eine Zeile mit Status 'Plan-Budget'.")

    def bearbeiten(self):
        row = self.table.currentRow()
        if row < 0: return
        k_id = int(self.table.item(row, 0).text())
        if AusgabeBearbeitenDialog(kopf_id=k_id, parent=self).exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def loeschen(self):
        row = self.table.currentRow()
        if row < 0: return
        k_id = int(self.table.item(row, 0).text())
        titel = self.table.item(row, 2).text()
        
        if QMessageBox.question(self, "Löschen", f"Ausgabe '{titel}' samt aller Positionen unwiderruflich löschen?", 
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                kopf = session.query(AusgabeKopf).filter_by(id=k_id).first()
                if kopf: session.delete(kopf); session.commit(); self.load_data()
            finally:
                session.close()