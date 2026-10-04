import json
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin


# ============================================================
# BandiAP - Aggiornamento automatico database
# Versione 5
# Fonte iniziale: Regione Marche
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BANDI_FILE = BASE_DIR / "bandi.json"

REGIONE_MARCHE_URL = (
    "https://www.regione.marche.it/Entra-in-Regione/"
    "Bandi-e-opportunita/Bandi-attivi"
)


def carica_bandi():
    """Carica il database bandi.json."""

    if not BANDI_FILE.exists():
        return []

    try:
        with open(BANDI_FILE, "r", encoding="utf-8") as f:
            dati = json.load(f)

        if isinstance(dati, list):
            return dati

        if isinstance(dati, dict):
            if isinstance(dati.get("bandi"), list):
                return dati["bandi"]

        return []

    except Exception as e:
        print(f"Errore lettura bandi.json: {e}")
        return []


def scarica_pagina(url):
    """Scarica una pagina web."""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; BandiAP/5.0; "
            "+https://github.com/)"
        )
    }

    richiesta = Request(url, headers=headers)

    with urlopen(richiesta, timeout=30) as risposta:
        return risposta.read().decode("utf-8", errors="ignore")


def pulisci_testo(testo):
    """Rimuove tag HTML e spazi superflui."""

    testo = re.sub(r"<[^>]+>", " ", testo)
    testo = testo.replace("&nbsp;", " ")
    testo = testo.replace("&amp;", "&")
    testo = testo.replace("&quot;", '"')
    testo = testo.replace("&#39;", "'")
    testo = re.sub(r"\s+", " ", testo)

    return testo.strip()


def estrai_data(testo):
    """Cerca una data nel formato gg/mm/aaaa."""

    match = re.search(
        r"\b([0-3]?\d/[01]?\d/20\d{2})\b",
        testo
    )

    if match:
        return match.group(1)

    return ""


def genera_id(titolo):
    """Genera un identificativo semplice dal titolo."""

    testo = titolo.lower()
    testo = re.sub(r"[^a-z0-9àèéìòù]+", "-", testo)
    testo = testo.strip("-")

    return testo[:100]


def estrai_bandi_regione_marche(html):
    """
    Individua possibili bandi nella pagina Regione Marche.
    """

    risultati = []

    link_pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)</a>',
        re.IGNORECASE | re.DOTALL
    )

    parole_utili = (
        "bando",
        "avviso",
        "contribut",
        "finanzi",
        "sostegno",
        "fondo",
        "incentiv",
        "agevol"
    )

    esclusioni = (
        "accedi",
        "login",
        "privacy",
        "cookie",
        "contatti",
        "facebook",
        "twitter",
        "instagram",
        "youtube"
    )

    visti = set()

    for href, contenuto in link_pattern.findall(html):

        titolo = pulisci_testo(contenuto)

        if len(titolo) < 15:
            continue

        titolo_lower = titolo.lower()

        if any(x in titolo_lower for x in esclusioni):
            continue

        if not any(x in titolo_lower for x in parole_utili):
            continue

        url = urljoin(REGIONE_MARCHE_URL, href)

        chiave = titolo_lower.strip()

        if chiave in visti:
            continue

        visti.add(chiave)

        risultati.append(
            {
                "id": genera_id(titolo),
                "titolo": titolo,
                "ente": "Regione Marche",
                "categoria": "Bandi e agevolazioni",
                "scadenza": estrai_data(titolo),
                "link": url,
                "fonte": "Regione Marche",
                "data_aggiornamento": datetime.now().strftime(
                    "%Y-%m-%d"
                )
            }
        )

    return risultati


def chiave_bando(bando):
    """Crea una chiave per evitare duplicati."""

    link = str(bando.get("link", "")).strip().lower()

    if link:
        return link

    titolo = str(bando.get("titolo", "")).strip().lower()

    return titolo


def unisci_bandi(esistenti, nuovi):
    """Aggiunge soltanto i bandi non presenti."""

    chiavi_esistenti = {
        chiave_bando(b)
        for b in esistenti
        if isinstance(b, dict)
    }

    aggiunti = []

    for bando in nuovi:

        chiave = chiave_bando(bando)

        if not chiave:
            continue

        if chiave not in chiavi_esistenti:
            esistenti.append(bando)
            chiavi_esistenti.add(chiave)
            aggiunti.append(bando)

    return esistenti, aggiunti


def salva_bandi(bandi):
    """Salva bandi.json."""

    with open(BANDI_FILE, "w", encoding="utf-8") as f:
        json.dump(
            bandi,
            f,
            ensure_ascii=False,
            indent=2
        )


def main():

    print("=" * 55)
    print("BandiAP - Aggiornamento database V5")
    print("=" * 55)

    bandi_esistenti = carica_bandi()

    print(f"Bandi già presenti: {len(bandi_esistenti)}")
    print()
    print("Controllo Regione Marche...")

    try:

        html = scarica_pagina(REGIONE_MARCHE_URL)

        bandi_trovati = estrai_bandi_regione_marche(html)

        print(
            f"Possibili bandi trovati: "
            f"{len(bandi_trovati)}"
        )

    except Exception as e:

        print(
            "Errore durante il controllo "
            f"Regione Marche: {e}"
        )

        bandi_trovati = []

    bandi_finali, aggiunti = unisci_bandi(
        bandi_esistenti,
        bandi_trovati
    )

    print()

    if aggiunti:

        salva_bandi(bandi_finali)

        print(
            f"Nuovi bandi aggiunti: {len(aggiunti)}"
        )

        for bando in aggiunti:
            print(
                f"+ {bando.get('titolo', '')}"
            )

    else:

        print("Nessun nuovo bando da aggiungere.")

    print()
    print(
        f"Totale bandi nel database: "
        f"{len(bandi_finali)}"
    )

    print("Aggiornamento completato.")


if __name__ == "__main__":
    main()
