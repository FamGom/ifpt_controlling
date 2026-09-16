from sqlalchemy import text
from core.database import engine

def patch_database():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE instituts_konto ADD COLUMN guthaben_pm FLOAT DEFAULT 0.0"))
            conn.commit()
            print("✅ Spalte 'guthaben_pm' erfolgreich zu den Konten hinzugefügt!")
        except Exception as e:
            print(f"Fehler: {e}")

if __name__ == "__main__":
    patch_database()