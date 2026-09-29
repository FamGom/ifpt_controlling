import calendar
from datetime import date, datetime
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtGui import QTextDocument, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtCore import QMarginsF

from core.database import get_session
from core.models import Mitarbeiter, Zuweisung, Projekt

def export_matrix_gantt_pdf(parent_widget, table, start_jahr, end_jahr, spalten_namen):
    """
    Generiert ein hochprofessionelles Gantt-Chart PDF.
    Nutzt extrem kompaktes HTML/CSS und drastisch reduzierte Seitenränder, 
    um unsaubere Zeilenumbrüche in QTextDocument zu verhindern.
    """
    farben = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#FFCCBC", "#E1BEE7"]
    projekt_farben = {}
    f_idx = 0

    alle_jahre = list(range(start_jahr, end_jahr + 1))
    jahres_bloecke = [alle_jahre[i:i + 2] for i in range(0, len(alle_jahre), 2)]

    heute_str = datetime.now().strftime('%d.%m.%Y %H:%M')

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica', 'Arial', sans-serif; color: #333; font-size: 6.5pt; }}
            h1 {{ font-size: 12pt; color: #2C3E50; border-bottom: 2px solid #2C3E50; padding-bottom: 2px; margin-bottom: 5px; }}
            h3 {{ font-size: 9pt; color: #2980B9; margin-top: 5px; margin-bottom: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
            th {{ background-color: #ECF0F1; border: 1px solid #7F8C8D; padding: 1px; font-size: 6.5pt; text-align: center; white-space: nowrap; }}
            td {{ border: 1px solid #BDC3C7; padding: 1px; font-size: 6.5pt; text-align: center; white-space: nowrap; }}
            .text-left {{ text-align: left; padding-left: 3px; font-weight: bold; }}
            .page-break {{ page-break-before: always; }}
        </style>
    </head>
    <body>
    """

    verfuegbare_spalten = {}
    for col in range(4, table.columnCount()):
        c_name = spalten_namen[col] # z.B. "01/26"
        m_teil, y_teil = c_name.split("/")
        s_jahr = 2000 + int(y_teil)
        s_monat = int(m_teil)
        verfuegbare_spalten[(s_jahr, s_monat)] = col

    for block_idx, jahre_chunk in enumerate(jahres_bloecke):
        if block_idx > 0:
            html += "<div class='page-break'></div>"
            
        html += f"<h1>Projekt- & Personalmatrix (Gantt) | Gesamt: {start_jahr} - {end_jahr}</h1>"
        html += f"<h3>Zeitraum-Ausschnitt: {jahre_chunk[0]} bis {jahre_chunk[-1]}</h3>"
        
        # Harte Spaltenbreiten: 14% + 3% + 3% = 20%. Bleiben 80% für 24 Monate = 3.33% pro Monat.
        html += "<table width='100%' cellspacing='0' cellpadding='1'><tr>"
        html += "<th width='14%' class='text-left'>Mitarbeiter</th><th width='3%'>Typ</th><th width='3%'>%</th>"
        
        block_keys = []
        for j in jahre_chunk:
            for m in range(1, 13):
                block_keys.append((j, m))
                html += f"<th width='3.33%'>{m:02d}<br>{str(j)[-2:]}</th>" 
        html += "</tr>"

        for row in range(table.rowCount()):
            ma_combo = table.cellWidget(row, 0)
            ma_name = ma_combo.currentText() if ma_combo and ma_combo.currentData() else ""
            if not ma_name or ma_name == "-": continue
            
            # Python-seitiges Clipping: Verhindert, dass ultralange Namen das PDF-Layout zerstören
            display_name = ma_name[:18] + ".." if len(ma_name) > 20 else ma_name
                
            raw_status = table.cellWidget(row, 1).currentText()
            status = "V" if raw_status == "Vertrag" else ("P" if raw_status == "Planung" else raw_status)
            anteil = table.cellWidget(row, 2).value()
            
            html += f"<tr><td class='text-left'><nobr>{display_name}</nobr></td><td>{status}</td><td>{anteil}</td>"
            
            row_items = []
            for (j, m) in block_keys:
                if (j, m) in verfuegbare_spalten:
                    col_idx = verfuegbare_spalten[(j, m)]
                    combo = table.cellWidget(row, col_idx)
                    proj = combo.currentText() if (combo and combo.currentData() is not None) else None
                else:
                    proj = None
                
                if proj and proj not in projekt_farben:
                    projekt_farben[proj] = farben[f_idx % len(farben)]
                    f_idx += 1
                row_items.append(proj)

            i = 0
            while i < len(row_items):
                p = row_items[i]
                span = 1
                if p is not None:
                    while i + span < len(row_items) and row_items[i + span] == p:
                        span += 1
                    bg_color = projekt_farben[p]
                    # Kürze auch Projektbezeichnungen stark ein, damit die Balken nicht umbrechen
                    display_p = p[:5] + ".." if span == 1 and len(p) > 5 else p
                    html += f"<td colspan='{span}' bgcolor='{bg_color}' style='font-weight: bold; border: 1px solid #34495E;'>{display_p}</td>"
                else:
                    html += "<td bgcolor='#FAFAFA'></td>"
                i += span
            html += "</tr>"

        html += "</table>"
        html += f"<div style='text-align: right; color: #7F8C8D; font-size: 6pt; margin-top: 5px;'>Erstellt am: {heute_str}</div>"

    html += "</body></html>"

    file_path, _ = QFileDialog.getSaveFileName(
        parent_widget, 
        "Gantt-Chart als PDF speichern", 
        f"Gantt_Planung_{start_jahr}_{end_jahr}.pdf", 
        "PDF-Dateien (*.pdf)"
    )

    if not file_path: return 

    document = QTextDocument()
    document.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(file_path)
    printer.setPageOrientation(QPageLayout.Orientation.Landscape)
    # Ränder von 12mm/15mm auf radikale 5mm geschrumpft für maximale Breitenausnutzung!
    printer.setPageMargins(QMarginsF(5, 5, 5, 5), QPageLayout.Unit.Millimeter)

    document.print(printer)
    QMessageBox.information(parent_widget, "Erfolg", f"Das Gantt-Chart wurde erfolgreich exportiert nach:\n{file_path}")


def export_mitarbeiter_pdf(parent_widget, ma_id, referenz_jahr):
    """
    Exportiert ein detailliertes A4-Hochformat Stammblatt für einen einzelnen Mitarbeiter.
    """
    session = get_session()
    try:
        ma = session.query(Mitarbeiter).filter_by(id=ma_id).first()
        if not ma: return

        heute_str = datetime.now().strftime('%d.%m.%Y %H:%M')
        geb = ma.geburtsdatum.strftime('%d.%m.%Y') if ma.geburtsdatum else "-"
        seit = ma.am_ifpt_seit.strftime('%d.%m.%Y') if ma.am_ifpt_seit else "-"
        abgang = ma.geplanter_abgang.strftime('%d.%m.%Y') if ma.geplanter_abgang else "Unbefristet"
        
        akt_kv = 1.7
        for kvz in ma.kv_zusatz_verlauf:
            if kvz.gueltig_ab <= date.today() and (not kvz.gueltig_bis or kvz.gueltig_bis >= date.today()):
                akt_kv = kvz.beitrag_pct
                break

        zuweisungen = session.query(Zuweisung).filter(
            Zuweisung.mitarbeiter_id == ma.id,
            Zuweisung.start_datum <= date(referenz_jahr, 12, 31),
            Zuweisung.end_datum >= date(referenz_jahr, 1, 1)
        ).all()

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Arial', sans-serif; color: #333; font-size: 10pt; }}
                h1 {{ color: #2C3E50; border-bottom: 2px solid #2980B9; padding-bottom: 5px; }}
                h2 {{ color: #2980B9; font-size: 12pt; margin-top: 20px; margin-bottom: 10px; border-bottom: 1px solid #BDC3C7; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; }}
                th {{ background-color: #ECF0F1; border: 1px solid #BDC3C7; padding: 6px; text-align: left; font-weight: bold; }}
                td {{ border: 1px solid #BDC3C7; padding: 6px; }}
                .val-right {{ text-align: right; }}
            </style>
        </head>
        <body>
            <h1>Personal-Stammblatt: {ma.vorname} {ma.nachname}</h1>
            <p><b>Auszugsjahr (Referenz):</b> {referenz_jahr}</p>

            <h2>1. Allgemeine HR-Daten</h2>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr><th width="30%">Geburtsdatum</th><td width="70%">{geb}</td></tr>
                <tr><th>Eintritt (Institut)</th><td>{seit}</td></tr>
                <tr><th>Geplanter Abgang</th><td>{abgang}</td></tr>
                <tr><th>Kinderanzahl (für PV)</th><td>{ma.kinder_anzahl or 0}</td></tr>
                <tr><th>VWL (Arbeitgeberanteil)</th><td>{ma.vl_betrag_euro or 0.0:.2f} € / Monat</td></tr>
                <tr><th>Krankenkassen-Zusatz</th><td>{akt_kv:.2f} % (Aktueller Stand)</td></tr>
            </table>

            <h2>2. TV-L Gehaltsverlauf (Historie & Planung)</h2>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="25%">Gültig ab</th>
                    <th width="25%">Gültig bis</th>
                    <th width="25%">Entgeltgruppe</th>
                    <th width="25%">Stufe</th>
                </tr>
        """
        for g in ma.gehaltsverlauf:
            g_ab = g.gueltig_ab.strftime('%d.%m.%Y')
            g_bis = g.gueltig_bis.strftime('%d.%m.%Y') if g.gueltig_bis else "Unbefristet"
            html += f"<tr><td>{g_ab}</td><td>{g_bis}</td><td>E {g.entgeltgruppe}</td><td>{g.stufe}</td></tr>"
        html += "</table>"

        html += f"""
            <h2>3. Projekt-Zuweisungen (Jahr {referenz_jahr})</h2>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="40%">Projekt</th>
                    <th width="20%">Zeitraum</th>
                    <th width="20%" class="val-right">Anteil</th>
                    <th width="20%">Status</th>
                </tr>
        """
        if zuweisungen:
            for z in zuweisungen:
                p_name = z.projekt.projektname if z.projekt else "Gelöschtes Projekt"
                z_zeit = f"{z.start_datum.strftime('%m/%Y')} - {z.end_datum.strftime('%m/%Y')}"
                html += f"""<tr>
                    <td>{p_name}</td>
                    <td>{z_zeit}</td>
                    <td class="val-right">{z.anteil_pct * 100:.1f} %</td>
                    <td>{z.typ.value}</td>
                </tr>"""
        else:
            html += "<tr><td colspan='4' align='center'><i>Keine Zuweisungen im Referenzjahr gefunden.</i></td></tr>"
        
        html += "</table>"
        
        html += f"<div style='text-align: right; color: #7F8C8D; font-size: 8pt; margin-top: 40px;'>Exportiert am: {heute_str}</div>"
        html += "</body></html>"

        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget, 
            "Stammblatt als PDF speichern", 
            f"Stammblatt_{ma.nachname}_{ma.vorname}_{referenz_jahr}.pdf", 
            "PDF-Dateien (*.pdf)"
        )

        if not file_path: return 

        document = QTextDocument()
        document.setHtml(html)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        # Hochformat hat weiterhin entspannte Ränder
        printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)

        document.print(printer)
        QMessageBox.information(parent_widget, "Erfolg", f"Das Stammblatt wurde erfolgreich exportiert nach:\n{file_path}")

    finally:
        session.close()