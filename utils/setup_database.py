import sys
import os
# Erlaubt das Importieren aus dem 'core' Ordner
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import date
from core.database import engine, get_session
from core.models import Base, SystemParameter, TarifTabelle, Projekt, ProjektStatus, Abrechnungsart, Mitarbeiter, Gehaltsverlauf, Zuweisung, ZuweisungsTyp
from core.calculations import generiere_projekt_controlling

def setup():
    # 1. Erzeugt die ifpt_controlling.db
    Base.metadata.drop_all(engine) # Löscht alte Version, falls vorhanden
    Base.metadata.create_all(engine)
    session = get_session()

    print("Tabellen erstellt. Fülle Daten ab...")

    # 2. System-Parameter eintragen (Gültig ab 01.01.2024 bis auf Weiteres)
    sys_bbg = SystemParameter(schluessel="BBG_KV", wert=5175.0, gueltig_ab=date(2024, 1, 1))
    sys_ag = SystemParameter(schluessel="AG_ANTEIL_PCT", wert=0.285, gueltig_ab=date(2024, 1, 1))
    sys_jsz = SystemParameter(schluessel="JSZ_PCT_E13", wert=0.50, gueltig_ab=date(2024, 1, 1))
    session.add_all([sys_bbg, sys_ag, sys_jsz])

    # 3. TV-L Werte eintragen (E13, Stufe 1 & 2)
    tvl_1 = TarifTabelle(entgeltgruppe="E13", stufe=1, betrag_euro=4323.38, gueltig_ab=date(2024, 1, 1))
    tvl_2 = TarifTabelle(entgeltgruppe="E13", stufe=2, betrag_euro=4668.61, gueltig_ab=date(2024, 1, 1))
    session.add_all([tvl_1, tvl_2])

    # 4. Projekt anlegen
    projekt = Projekt(
        projektname="Robo-Hub Basis",
        status=ProjektStatus.BEWILLIGT,
        abrechnungsart=Abrechnungsart.VOLLKOSTEN,
        projektbeginn=date(2026, 1, 1),
        projektende=date(2026, 12, 31),
        personalbudget_e13_e15=80000.0
    )
    session.add(projekt)

    # 5. Mitarbeiterin & Zuweisung (100% Vertrag in 2026)
    ma = Mitarbeiter(vorname="Anna", nachname="Schmidt", geburtsdatum=date(1994, 1, 1), am_ifpt_seit=date(2025, 1, 1))
    ma.gehaltsverlauf.append(Gehaltsverlauf(entgeltgruppe="E13", stufe=2, gueltig_ab=date(2026, 1, 1)))
    
    zuweisung = Zuweisung(typ=ZuweisungsTyp.VERTRAG, anteil_pct=1.0, start_datum=date(2026, 1, 1), end_datum=date(2026, 12, 31))
    zuweisung.projekt = projekt
    ma.zuweisungen.append(zuweisung)
    
    session.add(ma)
    session.commit()

    print("Testdaten erfolgreich gespeichert!")
    
    # 6. Kontroll-Rechnung durchführen (Stand heute: August 2026)
    heute = date(2026, 8, 14)
    print("\n--- TEST: BERECHNUNG LAUFEN LASSEN ---")
    ergebnis = generiere_projekt_controlling(session, projekt.id, heute)
    print(f"Projekt: {ergebnis['projekt']}")
    print(f"Budget:  {ergebnis['budget_gesamt']} €")
    print(f"IST:     {ergebnis['ist_buchungen_gesamt']} €  (Jan-Aug)")
    print(f"OBLIGO:  {ergebnis['obligo_gesamt']} €  (Sep-Dez)")
    print(f"REST:    {ergebnis['verfuegbare_mittel']} €")
    
    session.close()

if __name__ == "__main__":
    setup()