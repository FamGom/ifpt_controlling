from sqlalchemy import text
# Wir importieren die bestehende Engine, die deine App auch nutzt!
from core.database import engine
from core.models import Base  # Korrigierter Import

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



    with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE projekt ADD COLUMN bewilligungswahrscheinlichkeit_pct FLOAT DEFAULT 100.0"))
                conn.commit()
                print("✅ Spalte erfolgreich hinzugefügt.")
            except Exception as e:
                print(f"Fehler: {e}")



def patch_database2():
    # 1. Neue Tabellen anlegen (InstitutsKonto & OverheadRegel)
    Base.metadata.create_all(engine)
    
    # 2. Bestehende Projekt-Tabelle um die neuen Spalten erweitern
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE projekt ADD COLUMN overhead_regel_id INTEGER REFERENCES overhead_regel(id)"))
            conn.execute(text("ALTER TABLE projekt ADD COLUMN ziel_konto_id INTEGER REFERENCES instituts_konto(id)"))
            conn.execute(text("ALTER TABLE projekt ADD COLUMN restmittel_institut_pct FLOAT DEFAULT 0.0"))
            conn.commit()
            print("✅ Datenbank erfolgreich gepatcht! Spalten wurden hinzugefügt.")
        except Exception as e:
            print("Hinweis: Spalten existieren vermutlich bereits oder es gab einen Fehler:")
            print(e)

def patch_buchungen():
    Base.metadata.create_all(engine)
    print("✅ Tabelle 'konto_buchung' erfolgreich erstellt!")

def patch_guthaben():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE instituts_konto ADD COLUMN guthaben FLOAT DEFAULT 0.0"))
            conn.commit()
            print("✅ Erfolgreich: Spalte 'guthaben' wurde zum Institutskonto hinzugefügt!")
        except Exception as e:
            print("Fehler oder Spalte existiert bereits:")
            print(e)

def patch_database_guthabensplit():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE instituts_konto ADD COLUMN guthaben_personal FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE instituts_konto ADD COLUMN guthaben_sachmittel FLOAT DEFAULT 0.0"))
            # Übertrage altes Guthaben in Sachmittel (Sicherheit), danach alte Spalte ignorieren
            conn.execute(text("UPDATE instituts_konto SET guthaben_sachmittel = guthaben"))
            conn.commit()
            print("✅ Konten erfolgreich in Personal- und Sachmittel gesplittet!")
        except Exception as e:
            print("Fehler (oder bereits ausgeführt):", e)            

if __name__ == "__main__":
    #patch_database()
    #patch_database2()
    #patch_guthaben()
    patch_database_guthabensplit()
    