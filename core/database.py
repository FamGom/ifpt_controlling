from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Wir nutzen vorerst eine lokale SQLite-Datei im Hauptordner
DATABASE_URL = 'sqlite:///ifpt_controlling.db'

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    return SessionLocal()