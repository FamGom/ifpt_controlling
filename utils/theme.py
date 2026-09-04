import json
import os

THEME_FILE = "theme_config.json"

# Ein hochkontrastreiches "Modern Dark Mode"-Design als Standard
DEFAULT_THEME = {
    # --- PDF EXPORT DESIGN (Bleibt Schwarz/Weiß für Drucker) ---
    "pdf_font_family": "Arial",
    "pdf_font_size": "9pt",
    "pdf_text_color": "#000000",          
    "pdf_header_bg": "#D9D9D9",           
    "pdf_header_text": "#000000",
    "pdf_row_even_bg": "#F2F2F2",         
    "pdf_sum_bg": "#E6E6E6",              
    "pdf_sum_text": "#000000",            
    "pdf_total_bg": "#CCCCCC",            
    "pdf_total_text": "#000000",          
    "pdf_border_color": "#000000",        
    "pdf_border_style": "solid",          
    "pdf_border_width": 1,                

    # --- APP GUI DESIGN (Hochkontrast Dark Mode) ---
    "app_font_family": "Segoe UI",
    "app_font_size": "10pt",
    "app_text_color": "#E0E0E0",          # Hellgrau/Weiß für extrem gute Lesbarkeit
    "app_bg_color": "#1E1E1E",            # Dunkles Grau (Hintergrund)
    "app_table_bg": "#252526",            # Etwas helleres Dunkelgrau für Tabellen
    "app_table_alt_bg": "#2D2D30",        # Tabellen-Zebrastreifen
    "app_primary_color": "#007ACC"        # Strahlendes Blau für Tabs, Header und Akzente
}

def load_theme():
    if os.path.exists(THEME_FILE):
        try:
            with open(THEME_FILE, "r") as f:
                data = json.load(f)
                theme = DEFAULT_THEME.copy()
                theme.update(data)
                return theme
        except Exception:
            pass
    return DEFAULT_THEME.copy()

def save_theme(theme_dict):
    with open(THEME_FILE, "w") as f:
        json.dump(theme_dict, f, indent=4)

def get_pdf_css():
    t = load_theme()
    return f"""
    <style>
        body {{ font-family: '{t['pdf_font_family']}', sans-serif; font-size: {t['pdf_font_size']}; color: {t['pdf_text_color']}; }}
        h1, h2 {{ color: {t['pdf_text_color']}; border-bottom: 1px solid {t['pdf_border_color']}; }}
        .info-box {{ border: 1px {t['pdf_border_style']} {t['pdf_border_color']}; padding: 8px; margin-bottom: 15px; background-color: #FAFAFA; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; }}
        th {{ background-color: {t['pdf_header_bg']}; color: {t['pdf_header_text']}; font-weight: bold; padding: 5px; border: {t['pdf_border_width']}px {t['pdf_border_style']} {t['pdf_border_color']}; text-align: center; }}
        td {{ padding: 4px; border: {t['pdf_border_width']}px {t['pdf_border_style']} {t['pdf_border_color']}; text-align: right; white-space: nowrap; }}
        td.left {{ text-align: left; }}
        tr:nth-child(even) td {{ background-color: {t['pdf_row_even_bg']}; }}
        tr.sum-row td {{ background-color: {t['pdf_sum_bg']}; color: {t['pdf_sum_text']}; font-weight: bold; }}
        tr.total-row td {{ background-color: {t['pdf_total_bg']}; color: {t['pdf_total_text']}; font-weight: bold; border-top: 2px solid {t['pdf_border_color']}; }}
        .page-break {{ page-break-after: always; }}
    </style>
    """

def apply_app_theme(app):
    """Wendet die globalen App-Styles auf die PyQt-Instanz an."""
    t = load_theme()
    qss = f"""
        /* 1. Globaler Hintergrund und Schrift */
        QWidget {{
            font-family: '{t['app_font_family']}';
            font-size: {t['app_font_size']};
            background-color: {t['app_bg_color']};
            color: {t['app_text_color']};
        }}

        /* 2. REITER / TABS (Behebt das Problem auf deinem Bild) */
        QTabWidget::pane {{
            border: 1px solid {t['app_primary_color']};
            background-color: {t['app_bg_color']};
        }}
        QTabBar::tab {{
            background-color: #333333;     /* Dunkles Grau für inaktive Tabs */
            color: #AAAAAA;                /* Hellgraue Schrift für inaktive Tabs */
            padding: 8px 16px;
            border: 1px solid #222222;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {t['app_primary_color']}; /* Die Primärfarbe für den aktiven Tab */
            color: #FFFFFF;                             /* Harter Weiß-Kontrast */
            font-weight: bold;
        }}
        QTabBar::tab:hover:!selected {{
            background-color: #444444;
            color: #FFFFFF;
        }}

        /* 3. TABELLEN (Klare Grenzen, abgesetzter Header) */
        QTableWidget {{
            background-color: {t['app_table_bg']};
            alternate-background-color: {t['app_table_alt_bg']};
            color: {t['app_text_color']};
            gridline-color: #444444;
            selection-background-color: {t['app_primary_color']};
            selection-color: #FFFFFF;
            border: 1px solid #444444;
        }}
        QHeaderView::section {{
            background-color: {t['app_primary_color']};
            color: #FFFFFF;
            font-weight: bold;
            padding: 6px;
            border: 1px solid #1A1A1A;
        }}
        QTableCornerButton::section {{
            background-color: {t['app_primary_color']};
            border: 1px solid #1A1A1A;
        }}

        /* 4. EINGABEFELDER & DROPDOWNS (Dunkel mit hellem Text) */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
            background-color: #2D2D30;
            color: #FFFFFF;
            border: 1px solid #555555;
            padding: 5px;
            border-radius: 3px;
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
            border: 1px solid {t['app_primary_color']};
        }}
        QComboBox QAbstractItemView {{
            background-color: #2D2D30;
            color: #FFFFFF;
            selection-background-color: {t['app_primary_color']};
        }}

        /* 5. ÜBERSCHRIFTEN UND LABELS */
        QLabel {{
            background-color: transparent;
        }}
        QLabel[title="true"] {{
            color: {t['app_primary_color']};
            font-size: 14pt;
            font-weight: bold;
        }}
        
        /* 6. SYSTEM-MENÜS UND LISTEN */
        QMenu, QMenuBar {{
            background-color: {t['app_bg_color']};
            color: {t['app_text_color']};
            border: 1px solid #444444;
        }}
        QMenu::item:selected {{
            background-color: {t['app_primary_color']};
            color: #FFFFFF;
        }}
        QAbstractItemView {{
            background-color: {t['app_bg_color']};
            color: {t['app_text_color']};
            selection-background-color: {t['app_primary_color']};
            selection-color: #FFFFFF;
        }}

    """
    app.setStyleSheet(qss)