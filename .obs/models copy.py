import enum
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Enum, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class ProjektStatus(enum.Enum):
    BEANTRAGT = "Beantragt"
    BEWILLIGT = "Bewilligt"
    ABGELEHNT = "Abgelehnt"
    BEENDET = "Beendet"

class Abrechnungsart(enum.Enum):
    VOLLKOSTEN = "Vollkosten"
    PAUSCHALIERT = "Pauschaliert"
    NORMAL = "Normal"

class ZuweisungsTyp(enum.Enum):
    VERTRAG = "Vertrag"
    PLANUNG = "Planung"
    IST = "Ist"

# --- SYSTEM & TARIFE ---
class TarifTabelle(Base):
    __tablename__ = 'tarif_tabelle'
    id = Column(Integer, primary_key=True)
    entgeltgruppe = Column(String)
    stufe = Column(Integer)
    betrag_euro = Column(Float)
    jsz_prozent = Column(Float, default=0.4647)
    gueltig_ab = Column(Date)
    gueltig_bis = Column(Date, nullable=True)

class SystemParameter(Base):
    __tablename__ = 'system_parameter'
    id = Column(Integer, primary_key=True)
    schluessel = Column(String) 
    wert = Column(Float)            
    gueltig_ab = Column(Date)
    gueltig_bis = Column(Date, nullable=True)

# --- MITARBEITER ---
class Mitarbeiter(Base):
    __tablename__ = 'mitarbeiter'
    id = Column(Integer, primary_key=True)
    vorname = Column(String)
    nachname = Column(String)
    geburtsdatum = Column(Date)
    am_ifpt_seit = Column(Date)
    geplanter_abgang = Column(Date, nullable=True) 

    # --- INDIVIDUELLE FAKTOREN ---
    kinder_anzahl = Column(Integer, default=0)              
    kv_zusatzbeitrag_pct = Column(Float, default=1.7)       
    vl_betrag_euro = Column(Float, default=0.0)             
    
    gehaltsverlauf = relationship("Gehaltsverlauf", back_populates="mitarbeiter", cascade="all, delete-orphan")
    sonderzahlungen = relationship("Sonderzahlung", back_populates="mitarbeiter", cascade="all, delete-orphan")
    zuweisungen = relationship("Zuweisung", back_populates="mitarbeiter", cascade="all, delete-orphan")

class Gehaltsverlauf(Base):
    __tablename__ = 'gehaltsverlauf'
    id = Column(Integer, primary_key=True)
    mitarbeiter_id = Column(Integer, ForeignKey('mitarbeiter.id'))
    entgeltgruppe = Column(String)
    stufe = Column(Integer)
    gueltig_ab = Column(Date)
    gueltig_bis = Column(Date, nullable=True)
    mitarbeiter = relationship("Mitarbeiter", back_populates="gehaltsverlauf")

class Sonderzahlung(Base):
    __tablename__ = 'sonderzahlung'
    id = Column(Integer, primary_key=True)
    mitarbeiter_id = Column(Integer, ForeignKey('mitarbeiter.id'))
    bezeichnung = Column(String)
    betrag_euro = Column(Float)
    gueltig_ab = Column(Date)
    gueltig_bis = Column(Date, nullable=True) 
    mitarbeiter = relationship("Mitarbeiter", back_populates="sonderzahlungen")

# --- PROJEKTE ---
class Projekt(Base):
    __tablename__ = 'projekt'
    id = Column(Integer, primary_key=True)
    projektname = Column(String)
    status = Column(Enum(ProjektStatus), default=ProjektStatus.BEANTRAGT)
    abrechnungsart = Column(Enum(Abrechnungsart), default=Abrechnungsart.VOLLKOSTEN)
    overhead_pct = Column(Float, default=0.0)
    projektbeginn = Column(Date)
    projektende = Column(Date)
    
    personalbudget_e1_e12 = Column(Float, default=0.0)
    personalbudget_e13_e15 = Column(Float, default=0.0)
    personalbudget_besch_entgelt = Column(Float, default=0.0)
    sachmittelbudget = Column(Float, default=0.0)
    
    zuweisungen = relationship("Zuweisung", back_populates="projekt", cascade="all, delete-orphan")

class Zuweisung(Base):
    __tablename__ = 'projekt_zuweisung'
    id = Column(Integer, primary_key=True)
    mitarbeiter_id = Column(Integer, ForeignKey('mitarbeiter.id'))
    projekt_id = Column(Integer, ForeignKey('projekt.id'))
    typ = Column(Enum(ZuweisungsTyp), default=ZuweisungsTyp.PLANUNG) 
    anteil_pct = Column(Float, default=1.0)        
    start_datum = Column(Date)
    end_datum = Column(Date)
    
    mitarbeiter = relationship("Mitarbeiter", back_populates="zuweisungen")
    projekt = relationship("Projekt", back_populates="zuweisungen")

class GehaltsTabelle(Base):
    __tablename__ = 'gehaltstabelle'
    id = Column(Integer, primary_key=True)
    entgeltgruppe = Column(String(50))  
    stufe = Column(String(10))          
    gehalt_brutto = Column(Float)       
    gueltig_ab = Column(Date)