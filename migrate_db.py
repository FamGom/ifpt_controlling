from sqlalchemy import text
from datetime import date
from core.database import get_session, engine
from core.models import Base, Mitarbeiter, KVZusatzVerlauf

def migrate():
    print("1. Lege neue Tabellen an (falls fehlend)...")
    Base.metadata.create_all(engine)
    
    session = get_session()
    try:
        mitarbeiter_liste = session.query(Mitarbeiter).all()
        print(f"2. Prüfe {len(mitarbeiter_liste)} Mitarbeiter...")
        
        for m in mitarbeiter_liste:
            # Prüfen, ob schon ein Verlauf existiert (verhindert doppelte Einträge, falls du das Skript 2x startest)
            if not m.kv_zusatz_verlauf:
                # Wir holen den alten Wert über rohes SQL, da unser neues Python-Modell die Spalte nicht mehr kennt!
                sql = text(f"SELECT kv_zusatzbeitrag_pct FROM mitarbeiter WHERE id = {m.id}")
                result = session.execute(sql).fetchone()
                
                # Falls ein alter Wert gefunden wurde, nehmen wir den, sonst 1.7
                alter_wert = result[0] if result and result[0] is not None else 1.7
                
                # Wir legen den alten Wert als historischen Startwert an (z.B. gültig ab 01.01.2000)
                neuer_eintrag = KVZusatzVerlauf(
                    mitarbeiter_id=m.id,
                    beitrag_pct=alter_wert,
                    gueltig_ab=date(2000, 1, 1)
                )
                session.add(neuer_eintrag)
                print(f"   -> KV-Zusatz für {m.vorname} {m.nachname} ({alter_wert} %) in neue Historie gerettet.")
                
        session.commit()
        print("3. Migration erfolgreich abgeschlossen! Du kannst das Programm jetzt normal starten.")
    except Exception as e:
        session.rollback()
        print(f"Fehler bei der Migration: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate()