from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFormLayout, QColorDialog, 
                             QComboBox, QSpinBox, QMessageBox, QGroupBox, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from utils.theme import load_theme, save_theme, apply_app_theme
import sys

class ColorPickerButton(QPushButton):
    def __init__(self, color_hex):
        super().__init__()
        self.color_hex = color_hex
        self.update_style()
        self.clicked.connect(self.pick_color)

    def update_style(self):
        self.setStyleSheet(f"background-color: {self.color_hex}; border: 1px solid #333; min-width: 80px; min-height: 25px;")

    def pick_color(self):
        color = QColorDialog.getColor(
            QColor(self.color_hex), 
            self, 
            "Farbe wählen",
            options=QColorDialog.ColorDialogOption.DontUseNativeDialog
        )
        if color.isValid():
            self.color_hex = color.name()
            self.update_style()

class SettingsView(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("main_view") # Für CSS Targeting
        self.theme_data = load_theme()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        title = QLabel("Grafische Anpassungen & Design")
        title.setProperty("title", "true") # Wird vom neuen QSS erkannt
        main_layout.addWidget(title)
        
        row_layout = QHBoxLayout()

        # ==========================================
        # GRUPPE 1: APP GUI DESIGN (Die Software selbst)
        # ==========================================
        group_app = QGroupBox("Benutzeroberfläche der App (Live)")
        layout_app = QFormLayout(group_app)
        
        self.combo_app_font = QComboBox()
        self.combo_app_font.addItems(["Segoe UI", "Arial", "Verdana", "Tahoma"])
        self.combo_app_font.setCurrentText(self.theme_data.get("app_font_family", "Segoe UI"))
        layout_app.addRow("Schriftart App:", self.combo_app_font)

        self.spin_app_size = QSpinBox()
        self.spin_app_size.setRange(8, 20)
        self.spin_app_size.setSuffix(" pt")
        curr_app_size = int(self.theme_data.get("app_font_size", "10pt").replace("pt", ""))
        self.spin_app_size.setValue(curr_app_size)
        layout_app.addRow("Schriftgröße App:", self.spin_app_size)

        self.btn_app_text = ColorPickerButton(self.theme_data.get("app_text_color", "#2C3E50"))
        layout_app.addRow("Standard Textfarbe:", self.btn_app_text)
        
        self.btn_app_bg = ColorPickerButton(self.theme_data.get("app_bg_color", "#F4F6F7"))
        layout_app.addRow("Hintergrundfarbe (App):", self.btn_app_bg)
        
        self.btn_app_table_bg = ColorPickerButton(self.theme_data.get("app_table_bg", "#FFFFFF"))
        layout_app.addRow("Hintergrund (Tabellen):", self.btn_app_table_bg)
        
        self.btn_app_table_alt = ColorPickerButton(self.theme_data.get("app_table_alt_bg", "#EAECEE"))
        layout_app.addRow("Tabellen-Zebrastreifen:", self.btn_app_table_alt)
        
        self.btn_app_primary = ColorPickerButton(self.theme_data.get("app_primary_color", "#2980B9"))
        layout_app.addRow("Tabellenköpfe & Akzente:", self.btn_app_primary)
        
        row_layout.addWidget(group_app)

        # ==========================================
        # GRUPPE 2: PDF EXPORT DESIGN
        # ==========================================
        group_pdf = QGroupBox("PDF Export (Lohnjournale)")
        layout_pdf = QFormLayout(group_pdf)

        self.combo_pdf_font = QComboBox()
        self.combo_pdf_font.addItems(["Arial", "Segoe UI", "Times New Roman"])
        self.combo_pdf_font.setCurrentText(self.theme_data.get("pdf_font_family", "Arial"))
        layout_pdf.addRow("Schriftart:", self.combo_pdf_font)

        self.spin_pdf_size = QSpinBox()
        self.spin_pdf_size.setRange(5, 20)
        self.spin_pdf_size.setSuffix(" pt")
        curr_pdf_size = int(self.theme_data.get("pdf_font_size", "9pt").replace("pt", ""))
        self.spin_pdf_size.setValue(curr_pdf_size)
        layout_pdf.addRow("Schriftgröße:", self.spin_pdf_size)

        self.btn_pdf_text = ColorPickerButton(self.theme_data.get("pdf_text_color", "#000000"))
        layout_pdf.addRow("Schriftfarbe:", self.btn_pdf_text)

        self.btn_pdf_head_bg = ColorPickerButton(self.theme_data.get("pdf_header_bg", "#D9D9D9"))
        layout_pdf.addRow("Kopfzeilen Hintergrund:", self.btn_pdf_head_bg)

        self.btn_pdf_row_even = ColorPickerButton(self.theme_data.get("pdf_row_even_bg", "#F2F2F2"))
        layout_pdf.addRow("Zebra-Zeilen:", self.btn_pdf_row_even)

        self.btn_pdf_border = ColorPickerButton(self.theme_data.get("pdf_border_color", "#000000"))
        layout_pdf.addRow("Rahmenfarbe:", self.btn_pdf_border)
        
        self.combo_border_style = QComboBox()
        self.combo_border_style.addItems(["solid", "dashed", "dotted"])
        self.combo_border_style.setCurrentText(self.theme_data.get("pdf_border_style", "solid"))
        layout_pdf.addRow("Rahmenart:", self.combo_border_style)
        
        row_layout.addWidget(group_pdf)
        main_layout.addLayout(row_layout)

        # Speichern Button
        btn_save = QPushButton("💾 Design speichern & live anwenden")
        btn_save.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; font-size: 11pt; padding: 12px; margin-top: 10px;")
        btn_save.clicked.connect(self.save_settings)
        main_layout.addWidget(btn_save)
        
        main_layout.addStretch()

    def save_settings(self):
        # GUI Daten aktualisieren
        self.theme_data["app_font_family"] = self.combo_app_font.currentText()
        self.theme_data["app_font_size"] = f"{self.spin_app_size.value()}pt"
        self.theme_data["app_text_color"] = self.btn_app_text.color_hex
        self.theme_data["app_bg_color"] = self.btn_app_bg.color_hex
        self.theme_data["app_table_bg"] = self.btn_app_table_bg.color_hex
        self.theme_data["app_table_alt_bg"] = self.btn_app_table_alt.color_hex
        self.theme_data["app_primary_color"] = self.btn_app_primary.color_hex

        # PDF Daten aktualisieren
        self.theme_data["pdf_font_family"] = self.combo_pdf_font.currentText()
        self.theme_data["pdf_font_size"] = f"{self.spin_pdf_size.value()}pt"
        self.theme_data["pdf_text_color"] = self.btn_pdf_text.color_hex
        self.theme_data["pdf_header_bg"] = self.btn_pdf_head_bg.color_hex
        self.theme_data["pdf_row_even_bg"] = self.btn_pdf_row_even.color_hex
        self.theme_data["pdf_border_color"] = self.btn_pdf_border.color_hex
        self.theme_data["pdf_border_style"] = self.combo_border_style.currentText()

        save_theme(self.theme_data)
        
        # Das neue Theme SOFORT auf die laufende Anwendung anwenden!
        app = QApplication.instance()
        if app:
            apply_app_theme(app)
            
        QMessageBox.information(self, "Erfolg", "Design wurde erfolgreich gespeichert und angewendet!")