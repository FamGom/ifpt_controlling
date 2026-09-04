from PyQt6.QtWidgets import QMainWindow, QTabWidget
from PyQt6.QtGui import QAction

# Importieren unserer sauberen Ansichten
from gui.views.view_controlling import ControllingView
from gui.views.view_ist_abweichungen import IstAbweichungenView
from gui.views.view_matrix import MatrixMainView
from gui.views.view_projekte import ProjekteView
from gui.views.view_mitarbeiter import MitarbeiterView
from gui.views.view_system import SystemAdminMainView
from gui.views.view_settings import SettingsView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Fenstereinstellungen
        self.setWindowTitle("IFPT Budget & Projekt-Controlling")
        self.resize(1200, 800) # Schöne große Standardgröße für Tabellen

        # Zentrales Widget als Tab-Widget anlegen
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Die Haupt-Ansichten initialisieren
        self.tab_controlling = ControllingView()
        self.tab_matrix = MatrixMainView()
        self.tab_ist_abweichungen = IstAbweichungenView()
        self.tab_projekte = ProjekteView()
        self.tab_mitarbeiter = MitarbeiterView()
        self.tab_admin = SystemAdminMainView()
        self.tab_settings = SettingsView()

        # Tabs dem Fenster in logischer Prozess-Reihenfolge hinzufügen
        self.tabs.addTab(self.tab_controlling, "📊 Controlling & Dashboards")
        self.tabs.addTab(self.tab_matrix, "📅 Personal-Projekt-Matrix")
        self.tabs.addTab(self.tab_ist_abweichungen, "⏱️ Ist-Abweichungen erfassen")
        self.tabs.addTab(self.tab_projekte, "📂 Projekt-Verwaltung")
        self.tabs.addTab(self.tab_mitarbeiter, "👥 Mitarbeiter-Stammdaten")
        self.tabs.addTab(self.tab_admin, "⚙️ System & Administration")
        self.tabs.addTab(self.tab_settings, "🎨 Design & Einstellungen")

        # Menüleiste aufbauen
        self._create_menu()

    def _create_menu(self):
        menubar = self.menuBar()
        
        # Datei-Menü
        file_menu = menubar.addMenu("Datei")
        
        exit_action = QAction("Beenden", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        
        file_menu.addAction(exit_action)