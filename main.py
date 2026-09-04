import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from utils.theme import apply_app_theme  # <--- NEU

def main():
    app = QApplication(sys.argv)
    
    # Das "Fusion" Style-Theme sieht auf Windows, Mac und Linux gleichermaßen professionell aus
    #app.setStyle("Fusion") 
    app.setStyle("PyQtDarkTheme")
    #apply_app_theme(app)                 # <--- NEU
    
    # Fenster initialisieren und anzeigen
    window = MainWindow()
    window.show()
    
    # Anwendungsschleife starten (hält das Fenster offen)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()