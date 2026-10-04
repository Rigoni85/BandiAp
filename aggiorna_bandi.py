import json
from datetime import date, datetime
from pathlib import Path


# ============================================================
# BandiAP - Aggiornamento automatico database
# Versione 4
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BANDI_FILE = BASE_DIR / "bandi.json"


def carica_bandi():
    """Carica il database bandi.json."""

    if not BANDI_FILE.exists():
        print("ERRORE: bandi.json non trovato.")
        return []

    try:
        with BANDI_FILE.open("r", encoding="utf-8") as file:
            dati = json.load(file)

        if not isinstance(dati, list):
            print("ERRORE: bandi.json deve contenere una lista.")
            return []

        return dati

    except json.JSONDecodeError as errore:
        print(f"ERRORE JSON: {errore}")
        return []


def salva_bandi(bandi):
    """Salva il database mantenendo il JSON leggibile."""

    with BANDI_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            bandi,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("bandi.json salvato correttamente.")


def converti_data(scadenza):
    """Converte una data YYYY-MM-DD in oggetto date."""

    if not scadenza:
        return None

    try:
        return datetime.strptime(
            scadenza,
            "%Y-%m-%d"
        ).date()

    except (ValueError, TypeError):
        return None


def aggiorna_stato(bando):
    """
    Imposta automaticamente:
    APERTO  -> scadenza futura o odierna
    SCADUTO -> scadenza precedente a oggi
    """

    scadenza = converti_data(bando.get("scadenza"))

    if scadenza is None:
        return False

    oggi = date.today()

    nuovo_stato = (
        "SCADUTO"
        if scadenza < oggi
        else "APERTO"
    )

    vecchio_stato = bando.get("stato")

    if vecchio_stato != nuovo_stato:
        bando["stato"] = nuovo_stato
        return True

    return False


def controlla_duplicati(bandi):
    """Segnala eventuali ID duplicati."""

    ids = set()
    duplicati = []

    for bando in bandi:
        bando_id = bando.get("id")

        if not bando_id:
            continue

        if bando_id in ids:
            duplicati.append(bando_id)
        else:
            ids.add(bando_id)

    return duplicati


def main():

    print("=" * 50)
    print("BandiAP - Aggiornamento database V4")
    print("=" * 50)

    bandi = carica_bandi()

    if not bandi:
        print("Nessun bando presente.")
        return

    print(f"Bandi caricati: {len(bandi)}")

    modifiche = 0

    for bando in bandi:

        if aggiorna_stato(bando):
            modifiche += 1

            print(
                f"Aggiornato: "
                f"{bando.get('nome', 'Bando senza nome')} "
                f"-> {bando.get('stato')}"
            )

    duplicati = controlla_duplicati(bandi)

    if duplicati:
        print(
            "ATTENZIONE - ID duplicati:",
            ", ".join(map(str, duplicati))
        )

    if modifiche > 0:
        salva_bandi(bandi)
        print(f"Modifiche effettuate: {modifiche}")
    else:
        print("Nessuna modifica necessaria.")

    print("Aggiornamento completato.")


if __name__ == "__main__":
    main()
