import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                             QMessageBox, QSpinBox, QTabWidget, QDialog, QFormLayout, 
                             QLineEdit, QDateEdit, QDoubleSpinBox, QComboBox, QDialogButtonBox)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models import Mitarbeiter, Zuweisung, ZuweisungsTyp, Projekt, ProjektStatus, Vakanz, TarifTabelle, SystemParameter
from core.journal import generiere_mitarbeiter_lohnjournal
from core.calculations import generiere_projekt_controlling

# ==========================================
# DIALOG ZUR VAKANZ-ERFASSUNG
# ==========================================
class VakanzBearbeitenDialog(QDialog):
    def __init__(self, vakanz_id=None, parent=None):
        super().__init__(parent)
        self.vakanz_id = vakanz_id
        self.setWindowTitle("Geplante Stelle (Vakanz) bearbeiten" if vakanz_id else "Neue Vakanz planen")
        self.resize(500, 400)
        self.setup_ui()
        if self.vakanz_id: self.lade_daten()

    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.txt_bez = QLineEdit()
        self.txt_bez.setPlaceholderText("z.B. Post-Doc (M/W/D) Robotik")
        layout.addRow("Bezeichnung:", self.txt_bez)
        
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate())
        layout.addRow("Geplanter Start:", self.date_start)
        
        self.spin_monate = QSpinBox()
        self.spin_monate.setRange(1, 120)
        self.spin_monate.setValue(36)
        self.spin_monate.setSuffix(" Monate")
        layout.addRow("Geplante Laufzeit:", self.spin_monate)
        
        self.spin_prob = QDoubleSpinBox()
        self.spin_prob.setRange(0.0, 100.0)
        self.spin_prob.setValue(100.0)
        self.spin_prob.setSuffix(" %")
        layout.addRow("Realisierungs-Wahrscheinlichkeit:", self.spin_prob)
        
        self.combo_tarif = QComboBox()
        self.lade_tarife()
        layout.addRow("Angenommener Tarif (Basis):", self.combo_tarif)
        
        self.spin_az = QDoubleSpinBox()
        self.spin_az.setRange(1.0, 100.0)
        self.spin_az.setValue(100.0)
        self.spin_az.setSuffix(" %")
        layout.addRow("Arbeitszeit (Vollzeit = 100%):", self.spin_az)
        
        self.combo_projekt = QComboBox()
        self.lade_projekte()
        layout.addRow("Zugedachtes Projekt (Optional):", self.combo_projekt)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.speichern)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def lade_tarife(self):
        session = get_session()
        try:
            tarife = session.query(TarifTabelle).filter_by(stufe=1).order_by(TarifTabelle.entgeltgruppe).all()
            for t in tarife:
                self.combo_tarif.addItem(f"E{t.entgeltgruppe} (Stufe 1 Referenz)", t.id)
        finally:
            session.close()
            
    def lade_projekte(self):
        session = get_session()
        try:
            self.combo_projekt.addItem("Kein spezifisches Projekt", None)
            projekte = session.query(Projekt).filter(Projekt.status.in_([ProjektStatus.BEWILLIGT, ProjektStatus.BEANTRAGT])).all()
            for p in projekte:
                self.combo_projekt.addItem(f"{p.projektname} ({p.status.value})", p.id)
        finally:
            session.close()

    def lade_daten(self):
        session = get_session()
        try:
            v = session.query(Vakanz).filter_by(id=self.vakanz_id).first()
            if v:
                self.txt_bez.setText(v.bezeichnung)
                self.date_start.setDate(QDate(v.geplanter_start.year, v.geplanter_start.month, v.geplanter_start.day))
                self.spin_monate.setValue(v.laufzeit_monate)
                self.spin_prob.setValue(v.wahrscheinlichkeit_pct)
                self.spin_az.setValue(v.arbeitszeit_pct * 100.0)
                
                idx_t = self.combo_tarif.findData(v.tarif_id)
                if idx_t >= 0: self.combo_tarif.setCurrentIndex(idx_t)
                
                idx_p = self.combo_projekt.findData(v.projekt_id)
                if idx_p >= 0: self.combo_projekt.setCurrentIndex(idx_p)
        finally:
            session.close()

    def speichern(self):
        if not self.txt_bez.text().strip():
            QMessageBox.warning(self, "Fehler", "Bitte eine Bezeichnung eingeben.")
            return
            
        session = get_session()
        try:
            v = session.query(Vakanz).filter_by(id=self.vakanz_id).first() if self.vakanz_id else Vakanz()
            if not self.vakanz_id: session.add(v)
            
            v.bezeichnung = self.txt_bez.text().strip()
            v.geplanter_start = self.date_start.date().toPyDate()
            v.laufzeit_monate = self.spin_monate.value()
            v.wahrscheinlichkeit_pct = self.spin_prob.value()
            v.tarif_id = self.combo_tarif.currentData()
            v.arbeitszeit_pct = self.spin_az.value() / 100.0
            v.projekt_id = self.combo_projekt.currentData()
            
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler", str(e))
        finally:
            session.close()


# ==========================================
# HAUPT-ANSICHT (INKL. VAKANZEN TAB)
# ==========================================
class VakanzenView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("Instituts-Steuerung: Vakanzen & 6-Jahres-Bedarfe")
        title.setProperty("title", "true")
        layout.addWidget(title)
        
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("<b>Betrachtungszeitraum:</b>"))
        self.spin_start = QSpinBox(); self.spin_start.setRange(2020, 2040); self.spin_start.setValue(date.today().year)
        self.spin_end = QSpinBox(); self.spin_end.setRange(2020, 2040); self.spin_end.setValue(date.today().year + 2)
        
        self.spin_start.valueChanged.connect(self.load_data)
        self.spin_end.valueChanged.connect(self.load_data)
        
        btn_load = QPushButton("🔄 Bedarf & Budgets berechnen")
        btn_load.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold; padding: 6px;")
        btn_load.clicked.connect(self.load_data)
        
        toolbar.addWidget(self.spin_start)
        toolbar.addWidget(QLabel("bis"))
        toolbar.addWidget(self.spin_end)
        toolbar.addWidget(btn_load)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # --- TAB 0: VAKANZEN VERWALTEN (NEU) ---
        tab_v = QWidget()
        layout_v = QVBoxLayout(tab_v)
        tool_v = QHBoxLayout()
        btn_v_add = QPushButton("➕ Neue Stelle planen")
        btn_v_add.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold;")
        btn_v_add.clicked.connect(self.vakanz_add)
        btn_v_edit = QPushButton("✏️ Bearbeiten"); btn_v_edit.clicked.connect(self.vakanz_edit)
        btn_v_del = QPushButton("🗑️ Löschen"); btn_v_del.clicked.connect(self.vakanz_del)
        tool_v.addWidget(btn_v_add); tool_v.addWidget(btn_v_edit); tool_v.addWidget(btn_v_del); tool_v.addStretch()
        layout_v.addLayout(tool_v)
        
        self.table_vakanzen = QTableWidget()
        self.table_vakanzen.setColumnCount(7)
        self.table_vakanzen.setHorizontalHeaderLabels(["ID", "Bezeichnung", "Geplanter Start", "Laufzeit", "Wahrsch.", "AZ", "Zugedachtes Projekt"])
        self.table_vakanzen.setColumnHidden(0, True)
        self.table_vakanzen.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_vakanzen.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_vakanzen.setAlternatingRowColors(True)
        self.table_vakanzen.doubleClicked.connect(self.vakanz_edit)
        layout_v.addWidget(self.table_vakanzen)
        
        self.tab1 = QTableWidget()
        self.tab2 = QTableWidget()
        self.tab3 = QTableWidget()
        
        self.tabs.addTab(tab_v, "🪑 Stellenplanung (Neue Vakanzen)")
        self.tabs.addTab(self.tab1, "📅 Tab 1: Monatliche ungedeckte Bedarfe")
        self.tabs.addTab(self.tab2, "📊 Tab 2: Jahresscheiben (Kosten & PM)")
        self.tabs.addTab(self.tab3, "⚖️ Tab 3: Deckungsabgleich")

        # Initialer Ladevorgang
        self.load_data()

    def format_euro(self, val):
        if val == 0: return "-"
        return f"{val:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    def vakanz_add(self):
        if VakanzBearbeitenDialog(parent=self).exec() == QDialog.DialogCode.Accepted: self.load_data()
    def vakanz_edit(self):
        r = self.table_vakanzen.currentRow()
        if r >= 0 and VakanzBearbeitenDialog(vakanz_id=int(self.table_vakanzen.item(r, 0).text()), parent=self).exec() == QDialog.DialogCode.Accepted: self.load_data()
    def vakanz_del(self):
        r = self.table_vakanzen.currentRow()
        if r < 0: return
        if QMessageBox.question(self, "Löschen", "Vakanz löschen?") == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                v = session.query(Vakanz).filter_by(id=int(self.table_vakanzen.item(r, 0).text())).first()
                if v: session.delete(v); session.commit(); self.load_data()
            finally: session.close()

    def get_target_capacity(self, ma, check_date):
        check_end_date = date(check_date.year, check_date.month, calendar.monthrange(check_date.year, check_date.month)[1])
        for az in ma.arbeitszeiten:
            if az.gueltig_ab <= check_end_date and (not az.gueltig_bis or az.gueltig_bis >= check_date): return az.anteil_pct
        return 1.0

    def get_ag_pauschale(self, session, ref_date):
        """Ermittelt den aktuellen pauschalen Arbeitgeberanteil für Vakanz-Kosten."""
        params = session.query(SystemParameter).filter(SystemParameter.gueltig_ab <= ref_date).all()
        if not params: return 0.28 # Fallback
        ag_sum = sum([p.wert for p in params if p.schluessel in ['ag_rv', 'ag_av', 'ag_kv_base', 'ag_pv', 'vbl_satz', 'u2_satz', 'luk_satz']])
        return ag_sum

    def load_data(self):
        start_y = self.spin_start.value()
        end_y = self.spin_end.value()
        if start_y > end_y: return
        
        heute = date.today()
        session = get_session()
        try:
            # 0. Vakanzen Tabelle befüllen
            self.table_vakanzen.setRowCount(0)
            vakanzen = session.query(Vakanz).order_by(Vakanz.geplanter_start).all()
            for v in vakanzen:
                r = self.table_vakanzen.rowCount()
                self.table_vakanzen.insertRow(r)
                self.table_vakanzen.setItem(r, 0, QTableWidgetItem(str(v.id)))
                self.table_vakanzen.setItem(r, 1, QTableWidgetItem(v.bezeichnung))
                self.table_vakanzen.setItem(r, 2, QTableWidgetItem(v.geplanter_start.strftime("%m/%Y")))
                self.table_vakanzen.setItem(r, 3, QTableWidgetItem(f"{v.laufzeit_monate} Mon."))
                self.table_vakanzen.setItem(r, 4, QTableWidgetItem(f"{v.wahrscheinlichkeit_pct} %"))
                self.table_vakanzen.setItem(r, 5, QTableWidgetItem(f"{v.arbeitszeit_pct*100:.0f} %"))
                self.table_vakanzen.setItem(r, 6, QTableWidgetItem(v.projekt.projektname if v.projekt else "-"))
            
            # --- 1. DATENBESCHAFFUNG (MITARBEITER) ---
            ma_daten = {}
            mitarbeiter_liste = session.query(Mitarbeiter).all()
            for ma in mitarbeiter_liste:
                if not ma.am_ifpt_seit: continue
                try: limit_6j = date(ma.am_ifpt_seit.year + 6, ma.am_ifpt_seit.month, ma.am_ifpt_seit.day)
                except ValueError: limit_6j = date(ma.am_ifpt_seit.year + 6, ma.am_ifpt_seit.month, 28)
                
                commitment_end = ma.geplanter_abgang if (ma.geplanter_abgang and ma.geplanter_abgang < limit_6j) else limit_6j
                try: journal = generiere_mitarbeiter_lohnjournal(session, ma.id, start_y, 1, end_y, 12)
                except ValueError: continue
                
                ma_daten[ma.id] = {
                    "name": f"{ma.nachname}, {ma.vorname}",
                    "start": ma.am_ifpt_seit,
                    "commitment_end": commitment_end,
                    "kosten": {e["monat"]: e["gesamtkosten_inkl_rueck"] for e in journal},
                    "obj": ma,
                    "bedarf_monate": {},
                    "gedeckt_fix": {},
                    "gedeckt_plan": {}
                }

            # Zuweisungen für bestehende MA abziehen
            zuweisungen = session.query(Zuweisung).filter(Zuweisung.end_datum >= date(start_y, 1, 1), Zuweisung.start_datum <= date(end_y, 12, 31)).all()
            for z in zuweisungen:
                if z.mitarbeiter_id not in ma_daten: continue
                start_m_abs = z.start_datum.year * 12 + z.start_datum.month
                end_m_abs = z.end_datum.year * 12 + z.end_datum.month
                for m_abs in range(start_m_abs, end_m_abs + 1):
                    y, m = m_abs // 12, m_abs % 12
                    if m == 0: y -= 1; m = 12
                    if y < start_y or y > end_y: continue
                    monat_str = f"{m:02d}/{y}"
                    target_dict = "gedeckt_fix" if z.typ in [ZuweisungsTyp.IST, ZuweisungsTyp.VERTRAG] else "gedeckt_plan"
                    ma_daten[z.mitarbeiter_id][target_dict][monat_str] = ma_daten[z.mitarbeiter_id][target_dict].get(monat_str, 0.0) + z.anteil_pct

            alle_monate = [f"{m:02d}/{y}" for y in range(start_y, end_y + 1) for m in range(1, 13)]
            
            summen_ungedeckt = {m: 0.0 for m in alle_monate}
            summen_gedeckt_fix = {m: 0.0 for m in alle_monate}
            summen_gedeckt_plan = {m: 0.0 for m in alle_monate}
            
            # --- 2. KOSTEN BERECHNEN (Mitarbeiter) ---
            for ma_id, d in ma_daten.items():
                for m_str in alle_monate:
                    m, y = int(m_str.split('/')[0]), int(m_str.split('/')[1])
                    col_date = date(y, m, 1)
                    
                    ist_pct = d["gedeckt_fix"].get(m_str, 0.0)
                    plan_pct = d["gedeckt_plan"].get(m_str, 0.0)
                    monats_kosten = d["kosten"].get(m_str, 0.0)
                    
                    summen_gedeckt_fix[m_str] += ist_pct * monats_kosten
                    summen_gedeckt_plan[m_str] += (ist_pct + plan_pct) * monats_kosten
                    
                    is_past_or_current = (y < heute.year) or (y == heute.year and m <= heute.month)
                    if d["start"] <= col_date < d["commitment_end"] and not is_past_or_current:
                        target_cap = self.get_target_capacity(d["obj"], col_date)
                        ungedeckt_pct = max(0.0, target_cap - (ist_pct + plan_pct))
                        if ungedeckt_pct > 0:
                            euro_bedarf = monats_kosten * ungedeckt_pct
                            d["bedarf_monate"][m_str] = {"euro": euro_bedarf, "pm": ungedeckt_pct}
                            summen_ungedeckt[m_str] += euro_bedarf

            # --- 3. KOSTEN BERECHNEN (Neue Vakanzen als Dummys) ---
            for v in vakanzen:
                dummy_id = f"VAK_{v.id}"
                v_end = v.geplanter_start + relativedelta(months=v.laufzeit_monate)
                
                # Basisgehalt aus Tarif holen
                t = session.query(TarifTabelle).filter_by(id=v.tarif_id).first()
                basis_brutto = t.betrag_euro if t else 4500.0
                ag_pauschale = self.get_ag_pauschale(session, v.geplanter_start)
                
                monats_kosten = basis_brutto * v.arbeitszeit_pct * (1.0 + ag_pauschale) * (v.wahrscheinlichkeit_pct / 100.0)
                
                ma_daten[dummy_id] = {
                    "name": f"🪑 {v.bezeichnung} ({v.wahrscheinlichkeit_pct}%)",
                    "bedarf_monate": {}
                }
                
                for m_str in alle_monate:
                    m, y = int(m_str.split('/')[0]), int(m_str.split('/')[1])
                    col_date = date(y, m, 1)
                    col_end = date(y, m, calendar.monthrange(y, m)[1])
                    
                    if v.geplanter_start <= col_end and col_date < v_end:
                        # Vakanzen fließen voll als ungedeckter Bedarf in die Pipeline
                        euro_bedarf = monats_kosten
                        pm_bedarf = v.arbeitszeit_pct * (v.wahrscheinlichkeit_pct / 100.0)
                        
                        ma_daten[dummy_id]["bedarf_monate"][m_str] = {"euro": euro_bedarf, "pm": pm_bedarf}
                        summen_ungedeckt[m_str] += euro_bedarf


            # --- RENDER TABELLE 1: MONATLICH ---
            self.tab1.clear(); self.tab1.setRowCount(0)
            self.tab1.setColumnCount(1 + len(alle_monate))
            self.tab1.setHorizontalHeaderLabels(["Mitarbeiter / Vakanz"] + alle_monate)
            self.tab1.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            
            for ma_id, d in ma_daten.items():
                if not d["bedarf_monate"]: continue
                row = self.tab1.rowCount()
                self.tab1.insertRow(row)
                self.tab1.setItem(row, 0, QTableWidgetItem(d["name"]))
                for c, m_str in enumerate(alle_monate, start=1):
                    val = d["bedarf_monate"].get(m_str, {}).get("euro", 0.0)
                    item = QTableWidgetItem(self.format_euro(val))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if val > 0: item.setForeground(QColor("#E74C3C"))
                    self.tab1.setItem(row, c, item)
            
            self.tab1.insertRow(0)
            sum_item = QTableWidgetItem("SUMMEN UNGEDECKT")
            sum_item.setBackground(QColor("#2C3E50")); sum_item.setForeground(QColor("#FFFFFF"))
            sum_item.setFont(sum_item.font()); sum_item.font().setBold(True)
            self.tab1.setItem(0, 0, sum_item)
            for c, m_str in enumerate(alle_monate, start=1):
                item = QTableWidgetItem(self.format_euro(summen_ungedeckt[m_str]))
                item.setBackground(QColor("#2C3E50")); item.setForeground(QColor("#FFFFFF"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setFont(item.font()); item.font().setBold(True)
                self.tab1.setItem(0, c, item)

            # --- RENDER TABELLE 2: JAHRESSCHEIBEN ---
            jahre = list(range(start_y, end_y + 1))
            self.tab2.clear(); self.tab2.setRowCount(0)
            spalten_t2 = ["Mitarbeiter / Vakanz"]
            for y in jahre: spalten_t2.extend([f"{y} (€)", f"{y} (PM)"])
            self.tab2.setColumnCount(len(spalten_t2))
            self.tab2.setHorizontalHeaderLabels(spalten_t2)
            self.tab2.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            
            summen_jahre = {y: {"euro": 0.0, "pm": 0.0} for y in jahre}
            for ma_id, d in ma_daten.items():
                if not d["bedarf_monate"]: continue
                row = self.tab2.rowCount()
                self.tab2.insertRow(row)
                self.tab2.setItem(row, 0, QTableWidgetItem(d["name"]))
                c = 1
                for y in jahre:
                    y_euro, y_pm = 0.0, 0.0
                    for m in range(1, 13):
                        m_str = f"{m:02d}/{y}"
                        y_euro += d["bedarf_monate"].get(m_str, {}).get("euro", 0.0)
                        y_pm += d["bedarf_monate"].get(m_str, {}).get("pm", 0.0)
                    summen_jahre[y]["euro"] += y_euro
                    summen_jahre[y]["pm"] += y_pm
                    i_euro = QTableWidgetItem(self.format_euro(y_euro))
                    i_pm = QTableWidgetItem(f"{y_pm:.1f}" if y_pm > 0 else "-")
                    i_euro.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    i_pm.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if y_euro > 0: i_euro.setForeground(QColor("#E74C3C"))
                    self.tab2.setItem(row, c, i_euro); self.tab2.setItem(row, c+1, i_pm)
                    c += 2
                    
            self.tab2.insertRow(0)
            sum_item2 = QTableWidgetItem("SUMMEN")
            sum_item2.setBackground(QColor("#2C3E50")); sum_item2.setForeground(QColor("#FFFFFF"))
            self.tab2.setItem(0, 0, sum_item2)
            c = 1
            for y in jahre:
                i_euro = QTableWidgetItem(self.format_euro(summen_jahre[y]["euro"]))
                i_pm = QTableWidgetItem(f"{summen_jahre[y]['pm']:.1f}")
                for item in [i_euro, i_pm]:
                    item.setBackground(QColor("#2C3E50")); item.setForeground(QColor("#FFFFFF"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tab2.setItem(0, c, i_euro); self.tab2.setItem(0, c+1, i_pm)
                c += 2

            # --- BERECHNUNG FREIE PROJEKTMITTEL ---
            freie_mittel_monatlich = {m: 0.0 for m in alle_monate}
            freie_mittel_inkl_beantragt = {m: 0.0 for m in alle_monate}
            projekte = session.query(Projekt).filter(Projekt.status.in_([ProjektStatus.BEWILLIGT, ProjektStatus.BEANTRAGT])).all()
            for p in projekte:
                if not p.projektbeginn or not p.projektende: continue
                try: report = generiere_projekt_controlling(session, p.id, heute)
                except ValueError: continue
                rest = report["verfuegbare_mittel"]
                if rest <= 0: continue
                prob_faktor = (p.bewilligungswahrscheinlichkeit_pct or 100.0) / 100.0
                m_heute_abs, m_start_abs, m_end_abs = heute.year * 12 + heute.month, p.projektbeginn.year * 12 + p.projektbeginn.month, p.projektende.year * 12 + p.projektende.month
                start_calc_abs = max(m_heute_abs, m_start_abs)
                rest_monate = m_end_abs - start_calc_abs + 1
                if rest_monate > 0:
                    burn_rate_prob = (rest / rest_monate) * prob_faktor
                    for m_abs in range(start_calc_abs, m_end_abs + 1):
                        y, m = m_abs // 12, m_abs % 12
                        if m == 0: y -= 1; m = 12
                        m_str = f"{m:02d}/{y}"
                        if m_str in freie_mittel_inkl_beantragt:
                            freie_mittel_inkl_beantragt[m_str] += burn_rate_prob
                            if p.status == ProjektStatus.BEWILLIGT: freie_mittel_monatlich[m_str] += (rest / rest_monate)

           # --- RENDER TABELLE 3: DECKUNGSABGLEICH ---
            self.tab3.clear(); self.tab3.setRowCount(0)
            self.tab3.setColumnCount(1 + len(alle_monate))
            self.tab3.setHorizontalHeaderLabels(["Kennzahl"] + alle_monate)
            self.tab3.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

            reihen_daten = [
                ("Ungedeckter Bedarf (WiMi Lücken + Vakanzen)", summen_ungedeckt, "#E74C3C", "Kosten für WiMis im WissZeitVG-Fenster sowie geplante neue Stellen (Vakanzen)."),
                ("Gedeckte WiMi-Ansprüche (IST + Obligo)", summen_gedeckt_fix, "#27AE60", "Kosten, die durch gültige, feste Verträge in Bewilligten Projekten gebunden sind."),
                ("Gedeckte WiMi-Ansprüche (inkl. Planung)", summen_gedeckt_plan, "#2980B9", "Kosten inklusive weicher 'Planungs'-Zuweisungen."),
                ("Summe freie Projektmittel (Nur Bewilligte)", freie_mittel_monatlich, "#F39C12", "Das unverplante Restbudget aller BEWILLIGTEN Projekte."),
                ("Summe freie Projektmittel (Inkl. Beantragte)", freie_mittel_inkl_beantragt, "#8E44AD", "Soll-Burn-Rate inkl. BEANTRAGTER Projekte, gewichtet nach Wahrscheinlichkeit.")
            ]
            
            for titel, daten_dict, color_hex, tooltip in reihen_daten:
                row = self.tab3.rowCount()
                self.tab3.insertRow(row)
                item_title = QTableWidgetItem(titel); item_title.setToolTip(tooltip)
                item_title.setBackground(QColor("#2C3E50")); item_title.setForeground(QColor("#FFFFFF"))
                item_title.setFont(item_title.font()); item_title.font().setBold(True)
                self.tab3.setItem(row, 0, item_title)
                for c, m_str in enumerate(alle_monate, start=1):
                    val = daten_dict.get(m_str, 0.0)
                    item = QTableWidgetItem(self.format_euro(val))
                    item.setBackground(QColor("#34495E")); item.setForeground(QColor("#FFFFFF"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if val > 0: item.setForeground(QColor(color_hex))
                    self.tab3.setItem(row, c, item)
        finally:
            session.close()