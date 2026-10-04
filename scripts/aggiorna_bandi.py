import json
from datetime import datetime
from pathlib import Path

# Percorso del database
BASE_DIR = Path(__file__).resolve().parent.parent
FILE_BANDI = BASE_DIR / "bandi.json"


def carica_bandi():
    """Carica il database dei bandi."""
    if not FILE_BANDI.exists():
        raise FileNotFoundError(
            f"File non trovato: {FILE_BANDI}"
        )

    with open(FILE_BANDI, "r", encoding="utf-8") as file:
        return json.load(file)


def salva_bandi(bandi):
    """Salva il database aggiornato."""
    with open(FILE_BANDI, "w", encoding="utf-8") as file:
        json.dump(
            bandi,
            file,
            ensure_ascii=False,
            indent=2
        )


def aggiorna_scadenze(bandi):
    """
    Controlla automaticamente le scadenze
    e imposta SCADUTO quando necessario.
    """

    oggi = datetime.now().date()
    modifiche = 0

    for bando in bandi:

        data_scadenza = bando.get("scadenza")

        if not data_scadenza:
            continue

        try:
            scadenza = datetime.strptime(
                data_scadenza,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            print(
                f"Data non valida per: "
                f"{bando.get('nome', 'Bando senza nome')}"
            )
            continue

        nuovo_stato = (
            "SCADUTO"
            if scadenza < oggi
            else "APERTO"
        )

        if bando.get("stato") != nuovo_stato:

            print(
                f"{bando.get('nome')} -> "
                f"{nuovo_stato}"
            )

            bando["stato"] = nuovo_stato
            modifiche += 1

    return modifiche


def main():

    print("=== BandiAP - Aggiornamento database ===")

    bandi = carica_bandi()

    print(
        f"Bandi presenti nel database: {len(bandi)}"
    )

    modifiche = aggiorna_scadenze(bandi)

    if modifiche > 0:

        salva_bandi(bandi)

        print(
            f"Database aggiornato: "
            f"{modifiche} modifiche."
        )

    else:

        print(
            "Nessuna modifica necessaria."
        )

    print("=== Fine aggiornamento ===")


if __name__ == "__main__":
    main()
