from sqlalchemy import text
# Wir importieren die bestehende Engine, die deine App auch nutzt!
from core.database import engine 

def patch_database():
    # Wir probieren beide Tabellennamen (projekt und projekte), 
    # da dein Traceback "projekt" sagt, SQLAlchemy aber oft Plural nutzt.
    tabellen_namen = ["projekt", "projekte"]
    
    with engine.connect() as conn:
        for tabellen_name in tabellen_namen:
            try:
                # 1. Spalte hinzufügen
                conn.execute(text(f"ALTER TABLE {tabellen_name} ADD COLUMN tatsaechliche_rueckzahlung FLOAT DEFAULT 0.0"))
                # 2. Spalte hinzufügen
                conn.execute(text(f"ALTER TABLE {tabellen_name} ADD COLUMN restmittel_verbleib_typ VARCHAR DEFAULT 'Rückzahlung an Zuwendungsgeber'"))
                
                conn.commit()
                print(f"✅ Tabelle '{tabellen_name}' erfolgreich gepatcht! Du kannst die App jetzt starten.")
                return # Wenn erfolgreich, abbrechen
                
            except Exception as e:
                # Wenn die Tabelle nicht existiert oder die Spalte schon da ist, ignorieren wir den Fehler
                if "no such table" in str(e).lower():
                    continue
                elif "duplicate column" in str(e).lower():
                    print(f"✅ Die Tabelle '{tabellen_name}' hat die Spalten bereits.")
                    return
                else:
                    print(f"Fehler bei {tabellen_name}: {e}")
                    
        print("❌ Keine passende Tabelle gefunden. Bist du sicher, dass die Datenbank existiert?")

if __name__ == "__main__":
    patch_database()