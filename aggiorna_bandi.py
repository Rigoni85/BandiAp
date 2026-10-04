import json
import re
import html as html_lib
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin


# ============================================================
# BandiAP - Motore automatico aggiornamento bandi
# Versione 6
#
# Fonti:
# - Regione Marche
# - Camera di Commercio delle Marche
# - GAL Piceno
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BANDI_FILE = BASE_DIR / "bandi.json"

FONTI = [
    {
        "nome": "Regione Marche",
        "url": (
            "https://www.regione.marche.it/Entra-in-Regione/"
            "Bandi-e-opportunita/Bandi-attivi"
        ),
        "territorio": "Regione Marche",
    },
    {
        "nome": "Camera di Commercio delle Marche",
        "url": (
            "https://www.marche.camcom.it/"
            "fai-crescere-la-tua-impresa/bandi-e-contributi"
        ),
        "territorio": "Regione Marche",
    },
    {
        "nome": "GAL Piceno",
        "url": "https://galpiceno.it/bandi/",
        "territorio": "GAL Piceno",
    },
]


PAROLE_BANDO = (
    "bando",
    "avviso",
    "contribut",
    "finanzi",
    "incentiv",
    "agevol",
    "sostegno",
    "voucher",
    "fondo",
    "investiment",
    "impres",
    "intervento",
    "misura",
    "feampa",
    "srg",
    "csr",
)


ESCLUSIONI = (
    "privacy",
    "cookie",
    "facebook",
    "instagram",
    "youtube",
    "linkedin",
    "accedi",
    "login",
    "contatti",
    "newsletter",
    "amministrazione trasparente",
)


# ============================================================
# DATABASE
# ============================================================

def carica_bandi():

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

    except Exception as e:
        print(f"Errore lettura bandi.json: {e}")

    return []


def salva_bandi(bandi):

    with open(BANDI_FILE, "w", encoding="utf-8") as f:
        json.dump(
            bandi,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# DOWNLOAD
# ============================================================

def scarica_pagina(url):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; BandiAP/6.0; "
            "+https://github.com/)"
        ),
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    }

    richiesta = Request(url, headers=headers)

    with urlopen(richiesta, timeout=30) as risposta:

        return risposta.read().decode(
            "utf-8",
            errors="ignore"
        )


# ============================================================
# TESTO
# ============================================================

def pulisci_testo(testo):

    testo = re.sub(
        r"<script.*?</script>",
        " ",
        testo,
        flags=re.I | re.S
    )

    testo = re.sub(
        r"<style.*?</style>",
        " ",
        testo,
        flags=re.I | re.S
    )

    testo = re.sub(r"<[^>]+>", " ", testo)

    testo = html_lib.unescape(testo)

    testo = re.sub(r"\s+", " ", testo)

    return testo.strip()


def normalizza_testo(testo):

    testo = pulisci_testo(testo).lower()

    testo = (
        testo.replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
    )

    testo = re.sub(
        r"[^a-z0-9]+",
        " ",
        testo
    )

    return testo.strip()


# ============================================================
# DATE
# ============================================================

def converti_data(data):

    if not data:
        return ""

    data = data.strip()

    formati = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    )

    for formato in formati:

        try:

            d = datetime.strptime(
                data,
                formato
            )

            return d.strftime("%Y-%m-%d")

        except ValueError:
            pass

    return ""


def estrai_data(testo):

    patterns = [
        r"\b([0-3]?\d/[01]?\d/20\d{2})\b",
        r"\b([0-3]?\d-[01]?\d-20\d{2})\b",
        r"\b(20\d{2}-[01]\d-[0-3]\d)\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            testo
        )

        if match:
            return converti_data(
                match.group(1)
            )

    return ""


def data_testo(data):

    if not data:
        return "Verificare sulla fonte ufficiale"

    try:

        d = datetime.strptime(
            data,
            "%Y-%m-%d"
        )

        mesi = [
            "",
            "gennaio",
            "febbraio",
            "marzo",
            "aprile",
            "maggio",
            "giugno",
            "luglio",
            "agosto",
            "settembre",
            "ottobre",
            "novembre",
            "dicembre",
        ]

        return (
            f"{d.day} "
            f"{mesi[d.month]} "
            f"{d.year}"
        )

    except ValueError:

        return data


# ============================================================
# CLASSIFICAZIONE
# ============================================================

def classifica_profili(testo):

    t = normalizza_testo(testo)

    profili = []

    if any(
        x in t
        for x in (
            "nuova impresa",
            "nuove imprese",
            "creazione impresa",
            "startup",
            "start up",
        )
    ):
        profili.append("nuova")

    if any(
        x in t
        for x in (
            "microimpresa",
            "micro impresa",
            "micro imprese",
            "micro piccole",
            "m pmi",
            "mpmi",
        )
    ):
        profili.append("micro")

    if any(
        x in t
        for x in (
            "piccola impresa",
            "piccole imprese",
            "pmi",
            "mpmi",
        )
    ):
        profili.append("piccola")

    if any(
        x in t
        for x in (
            "media impresa",
            "medie imprese",
            "pmi",
            "mpmi",
        )
    ):
        profili.append("media")

    if any(
        x in t
        for x in (
            "agricol",
            "zootec",
        )
    ):
        profili.append("agricola")

    if any(
        x in t
        for x in (
            "acquacoltura",
            "feampa",
        )
    ):
        profili.append("acquacoltura")

    if not profili:
        profili = [
            "micro",
            "piccola",
            "media",
            "altro",
        ]

    return list(dict.fromkeys(profili))


def classifica_settori(testo):

    t = normalizza_testo(testo)

    settori = []

    regole = {
        "commercio": (
            "commerc",
            "retail",
        ),
        "turismo": (
            "turism",
            "ricettiv",
            "ospitalita",
        ),
        "agricoltura": (
            "agricol",
            "zootec",
            "rurale",
        ),
        "artigianato": (
            "artigian",
        ),
        "industria": (
            "industr",
            "manifattur",
        ),
        "servizi": (
            "servizi",
            "profession",
        ),
        "digitale": (
            "digital",
            "ict",
            "innovazione",
            "transizione digitale",
        ),
        "pesca": (
            "pesca",
            "acquacoltura",
            "feampa",
        ),
    }

    for settore, parole in regole.items():

        if any(
            parola in t
            for parola in parole
        ):
            settori.append(settore)

    if not settori:

        settori = [
            "commercio",
            "turismo",
            "agricoltura",
            "artigianato",
            "industria",
            "servizi",
            "digitale",
            "pesca",
            "altro",
        ]

    return settori


# ============================================================
# ID
# ============================================================

def genera_id(fonte, titolo):

    stringa = (
        fonte
       
