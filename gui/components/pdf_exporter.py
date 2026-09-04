from datetime import date
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtGui import QTextDocument, QPageLayout
from PyQt6.QtPrintSupport import QPrinter


''' Braucht definitiv noch Arbeit - die Spalten sind nicht gleich breit. Die Jahre passen sich nicht an; die Monate sind nicht gleichmäßig verteilt. '''

def export_matrix_gantt_pdf(parent_widget, table, start_jahr, end_jahr, spalten_namen):
    """Generiert ein sauberes Gantt-Chart PDF mit festen Spaltenbreiten, 
    gestapelten Monatsköpfen gegen unsaubere Umbrüche und Seitenumbrüchen alle 2 Jahre."""
    
    farben = ["#BBDEFB", "#C8E6C9", "#FFF9C4", "#FFCCBC", "#E1BEE7"]
    projekt_farben = {}
    f_idx = 0

    alle_jahre = list(range(start_jahr, end_jahr + 1))
    jahres_bloecke = [alle_jahre[i:i + 2] for i in range(0, len(alle_jahre), 2)]

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica', 'Arial', sans-serif; color: #333; font-size: 9pt; }}
            h1 {{ font-size: 14pt; color: #2C3E50; border-bottom: 2px solid #2C3E50; padding-bottom: 5px; margin-bottom: 15px; }}
            h3 {{ font-size: 11pt; color: #2980B9; margin-top: 10px; margin-bottom: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; table-layout: fixed; }}
            th {{ background-color: #ECF0F1; border: 1px solid #BDC3C7; padding: 3px 1px; font-size: 7.5pt; text-align: center; white-space: nowrap; line-height: 1.1; }}
            td {{ border: 1px solid #BDC3C7; padding: 2px; font-size: 8pt; text-align: center; height: 24px; overflow: hidden; }}
            
            /* Feste Prozentbreiten für ein starres, gleichmäßiges Raster (24 Monate pro Block) */
            .col-name {{ width: 20%; text-align: left; padding-left: 5px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
            .col-status {{ width: 6%; font-size: 7pt; }}
            .col-anteil {{ width: 5%; font-size: 7pt; }}
            .col-monat {{ width: 2.875%; }} 
            
            .gantt-block {{ 
                border-radius: 3px; 
                font-weight: bold; 
                color: #000; 
                padding: 3px; 
                font-size: 8pt;
                overflow: hidden; 
                white-space: nowrap; 
                text-overflow: ellipsis;
                border: 1px solid #7f8c8d;
            }}
            .empty-cell {{ background-color: #FAFAFA; }}
            .page-break {{ page-break-after: always; }}
        </style>
    </head>
    <body>
        <h1>Projekt- & Personalplanung (Gesamtzeitraum: {start_jahr} - {end_jahr})</h1>
    """

    verfügbare_spalten = {}
    for col in range(4, table.columnCount()):
        c_name = spalten_namen[col] # z.B. "01/26"
        m_teil, y_teil = c_name.split("/")
        s_jahr = 2000 + int(y_teil)
        s_monat = int(m_teil)
        verfügbare_spalten[(s_jahr, s_monat)] = col

    for block_idx, jahre_chunk in enumerate(jahres_bloecke):
        chunk_titel = f"Zeitraum: {jahre_chunk[0]} bis {jahre_chunk[-1]}"
        html += f"<h3>{chunk_titel}</h3>"
        html += "<table><tr>"
        
        html += "<th class='col-name'>Mitarbeiter</th><th class='col-status'>Typ</th><th class='col-anteil'>%</th>"
        
        block_spalten_schlüssel = []
        for j in jahre_chunk:
            for m in range(1, 13):
                block_spalten_schlüssel.append((j, m))
                m_str = f"{m:02d}"
                y_str = str(j)[-2:]
                # Monat und Jahr sauber übereinander gestapelt, um unsaubere Zeilenumbrüche zu verhindern
                html += f"<th class='col-monat'>{m_str}<br>{y_str}</th>"
        
        html += "</tr>"

        for row in range(table.rowCount()):
            ma_combo = table.cellWidget(row, 0)
            ma_name = ma_combo.currentText() if ma_combo and ma_combo.currentData() else ""
            if not ma_name or ma_name == "-":
                continue
                
            raw_status = table.cellWidget(row, 1).currentText()
            status = "V" if raw_status == "Vertrag" else ("P" if raw_status == "Planung" else raw_status)
            anteil = table.cellWidget(row, 2).value()
            
            html += f"<tr><td class='col-name'>{ma_name}</td><td class='col-status'>{status}</td><td class='col-anteil'>{anteil}</td>"
            
            row_items = []
            for (j, m) in block_spalten_schlüssel:
                if (j, m) in verfügbare_spalten:
                    col_idx = verfügbare_spalten[(j, m)]
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
                    html += f"<td colspan='{span}'><div class='gantt-block' style='background-color: {bg_color};'>{p}</div></td>"
                else:
                    html += "<td class='col-monat empty-cell'>&nbsp;</td>"
                    span = 1
                    
                i += span
                
            html += "</tr>"

        html += "</table>"
        
        if block_idx < len(jahres_bloecke) - 1:
            html += "<div class='page-break'></div>"

    html += """
        <br>
        <p style='font-size: 7pt; color: #7F8C8D;'>Generiert aus dem IFPT Controlling-System.</p>
    </body>
    </html>
    """

    file_path, _ = QFileDialog.getSaveFileName(
        parent_widget, 
        "Gantt-Chart als PDF speichern", 
        f"Gantt_Planung_{start_jahr}_{end_jahr}.pdf", 
        "PDF-Dateien (*.pdf)"
    )

    if not file_path:
        return 

    document = QTextDocument()
    document.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(file_path)
    printer.setPageOrientation(QPageLayout.Orientation.Landscape)

    document.print(printer)
    QMessageBox.information(parent_widget, "Erfolg", f"Das Gantt-Chart wurde erfolgreich exportiert nach:\n{file_path}")