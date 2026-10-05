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


# ============================================================
# CONFIGURAZIONE
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

        print(
            f"Database non trovato: {BANDI_FILE}"
        )

        return []

    try:

        with open(
            BANDI_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            dati = json.load(f)

        if isinstance(dati, list):

            return dati

        if isinstance(dati, dict):

            if isinstance(
                dati.get("bandi"),
                list
            ):

                return dati["bandi"]

    except Exception as e:

        print(
            f"Errore lettura bandi.json: {e}"
        )

    return []


def salva_bandi(bandi):

    with open(
        BANDI_FILE,
        "w",
        encoding="utf-8"
    ) as f:

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
        "Accept-Language": (
            "it-IT,it;q=0.9,en;q=0.8"
        ),
    }

    richiesta = Request(
        url,
        headers=headers
    )

    with urlopen(
        richiesta,
        timeout=30
    ) as risposta:

        return risposta.read().decode(
            "utf-8",
            errors="ignore"
        )


# ============================================================
# TESTO
# ============================================================

def pulisci_testo(testo):

    if not testo:

        return ""

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

    testo = re.sub(
        r"<[^>]+>",
        " ",
        testo
    )

    testo = html_lib.unescape(
        testo
    )

    testo = re.sub(
        r"\s+",
        " ",
        testo
    )

    return testo.strip()


def normalizza_testo(testo):

    testo = pulisci_testo(
        testo
    ).lower()

    testo = (
        testo
        .replace("à", "a")
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

            return d.strftime(
                "%Y-%m-%d"
            )

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

        return (
            "Verificare sulla fonte ufficiale"
        )

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
# CLASSIFICAZIONE PROFILI
# ============================================================

def classifica_profili(testo):

    t = normalizza_testo(
        testo
    )

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

        profili.append(
            "nuova"
        )

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

        profili.append(
            "micro"
        )

    if any(
        x in t
        for x in (
            "piccola impresa",
            "piccole imprese",
            "pmi",
            "mpmi",
        )
    ):

        profili.append(
            "piccola"
        )

    if any(
        x in t
        for x in (
            "media impresa",
            "medie imprese",
            "pmi",
            "mpmi",
        )
    ):

        profili.append(
            "media"
        )

    if any(
        x in t
        for x in (
            "agricol",
            "zootec",
        )
    ):

        profili.append(
            "agricola"
        )

    if any(
        x in t
        for x in (
            "acquacoltura",
            "feampa",
        )
    ):

        profili.append(
            "acquacoltura"
        )

    if not profili:

        profili = [
            "micro",
            "piccola",
            "media",
            "altro",
        ]

    return list(
        dict.fromkeys(
            profili
        )
    )


# ============================================================
# CLASSIFICAZIONE SETTORI
# ============================================================

def classifica_settori(testo):

    t = normalizza_testo(
        testo
    )

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

            settori.append(
                settore
            )

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
# ID UNIVOCO
# ============================================================

def genera_id(
    fonte,
    titolo
):

    stringa = (
        fonte.strip().lower()
        + "|"
        + normalizza_testo(
            titolo
        )
    )

    return hashlib.sha256(
        stringa.encode(
            "utf-8"
        )
    ).hexdigest()[:16]


# ============================================================
# ESTRAZIONE LINK
# ============================================================

def estrai_link(
    html,
    base_url
):

    risultati = []

    visti = set()

    pattern = re.compile(
        (
            r'<a[^>]+'
            r'href=["\']([^"\']+)["\']'
            r'[^>]*>(.*?)</a>'
        ),
        re.I | re.S
    )

    for href, contenuto in pattern.findall(
        html
    ):

        titolo = pulisci_testo(
            contenuto
        )

        if not titolo:

            continue

        if len(titolo) < 8:

            continue

        url = urljoin(
            base_url,
            html_lib.unescape(
                href
            )
        )

        if not url.startswith(
            (
                "http://",
                "https://",
            )
        ):

            continue

        testo_normale = (
            normalizza_testo(
                titolo
                + " "
                + url
            )
        )

        if any(
            esclusione in testo_normale
            for esclusione in ESCLUSIONI
        ):

            continue

        if not any(
            parola in testo_normale
            for parola in PAROLE_BANDO
        ):

            continue

        chiave = (
            normalizza_testo(
                titolo
            ),
            url,
        )

        if chiave in visti:

            continue

        visti.add(
            chiave
        )

        risultati.append(
            {
                "titolo": titolo,
                "url": url,
            }
        )

    return risultati


# ============================================================
# ANALISI DETTAGLIO BANDO
# ============================================================

def analizza_bando(
    link,
    fonte
):

    titolo = link[
        "titolo"
    ]

    url = link[
        "url"
    ]

    print(
        f"Analizzo: {titolo}"
    )

    try:

        pagina = scarica_pagina(
            url
        )

        testo = pulisci_testo(
            pagina
        )

    except Exception as e:

        print(
            "  Impossibile leggere "
            f"il dettaglio: {e}"
        )

        testo = titolo

    testo_completo = (
        titolo
        + " "
        + testo[:15000]
    )

    scadenza = estrai_data(
        testo_completo
    )

    return {

        "id": genera_id(
            fonte["nome"],
            titolo
        ),

        "nome": titolo,

        "ente": fonte[
            "nome"
        ],

        "stato": "APERTO",

        "scadenza": scadenza,

        "scadenzaTesto": (
            data_testo(
                scadenza
            )
        ),

        "profili": (
            classifica_profili(
                testo_completo
            )
        ),

        "settori": (
            classifica_settori(
                testo_completo
            )
        ),

        "descrizione": (
            "Opportunità individuata "
            "automaticamente da BandiAP. "
            "Verificare i dettagli sulla "
            "fonte ufficiale."
        ),

        "requisiti": (
            "Verificare beneficiari, "
            "requisiti e condizioni "
            "sulla fonte ufficiale."
        ),

        "dotazione": (
            "Verificare sulla fonte "
            "ufficiale"
        ),

        "territorio": fonte[
            "territorio"
        ],

        "url": url,

        "fonteAutomatica": True,

        "ultimoControllo": (
            datetime.now().strftime(
                "%Y-%m-%d"
            )
        ),
    }


# ============================================================
# AGGIORNAMENTO SCADENZE
# ============================================================

def aggiorna_scadenze(
    bandi
):

    oggi = datetime.now().date()

    modifiche = 0

    for bando in bandi:

        scadenza = bando.get(
            "scadenza",
            ""
        )

        if not scadenza:

            continue

        try:

            data = datetime.strptime(
                scadenza,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            print(
                "Data non valida: "
                f"{scadenza} - "
                f"{bando.get('nome', '')}"
            )

            continue

        nuovo_stato = (
            "SCADUTO"
            if data < oggi
            else "APERTO"
        )

        if (
            bando.get("stato")
            != nuovo_stato
        ):

            print(
                "Stato aggiornato: "
                f"{bando.get('nome')} "
                f"-> {nuovo_stato}"
            )

            bando[
                "stato"
            ] = nuovo_stato

            modifiche += 1

    return modifiche


# ============================================================
# INDICE DATABASE
# ============================================================

def indicizza_bandi(
    bandi
):

    indice = {}

    for bando in bandi:

        url = bando.get(
            "url",
            ""
        )

        if url:

            indice[
                url.rstrip("/")
            ] = bando

    return indice


# ============================================================
# AGGIUNTA NUOVI BANDI
# ============================================================

def aggiungi_nuovi_bandi(
    database,
    trovati
):

    indice = indicizza_bandi(
        database
    )

    aggiunti = 0

    for nuovo in trovati:

        url = nuovo.get(
            "url",
            ""
        ).rstrip("/")

        if not url:

            continue

        if url in indice:

            esistente = indice[
                url
            ]

            esistente[
                "ultimoControllo"
            ] = nuovo.get(
                "ultimoControllo"
            )

            continue

        database.append(
            nuovo
        )

        indice[
            url
        ] = nuovo

        aggiunti += 1

        print(
            "NUOVO BANDO: "
            f"{nuovo.get('nome')}"
        )

    return aggiunti


# ============================================================
# CONTROLLO SINGOLA FONTE
# ============================================================

def controlla_fonte(
    fonte
):

    print()

    print(
        "=" * 60
    )

    print(
        "Controllo: "
        f"{fonte['nome']}"
    )

    print(
        fonte["url"]
    )

    try:

        pagina = scarica_pagina(
            fonte["url"]
        )

    except Exception as e:

        print(
            "Errore download fonte: "
            f"{e}"
        )

        return []

    links = estrai_link(
        pagina,
        fonte["url"]
    )

    print(
        "Link candidati trovati: "
        f"{len(links)}"
    )

    risultati = []

    # Limite di sicurezza:
    # massimo 30 pagine per fonte.
    for link in links[:30]:

        try:

            bando = analizza_bando(
                link,
                fonte
            )

            risultati.append(
                bando
            )

        except Exception as e:

            print(
                "Errore analisi "
                f"{link.get('titolo')}: "
                f"{e}"
            )

    return risultati


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "======================================"
    )

    print(
        "BandiAP - aggiornamento automatico V6"
    )

    print(
        "======================================"
    )

    print(
        f"Database: {BANDI_FILE}"
    )

    database = carica_bandi()

    print(
        "Bandi iniziali nel database: "
        f"{len(database)}"
    )

    # ------------------------------------
    # 1. Aggiornamento bandi già presenti
    # ------------------------------------

    modifiche_scadenze = (
        aggiorna_scadenze(
            database
        )
    )

    # ------------------------------------
    # 2. Ricerca nuovi bandi
    # ------------------------------------

    tutti_trovati = []

    for fonte in FONTI:

        trovati = controlla_fonte(
            fonte
        )

        tutti_trovati.extend(
            trovati
        )

    print()

    print(
        "Candidati complessivi trovati: "
        f"{len(tutti_trovati)}"
    )

    # ------------------------------------
    # 3. Confronto con database
    # ------------------------------------

    aggiunti = aggiungi_nuovi_bandi(
        database,
        tutti_trovati
    )

    # ------------------------------------
    # 4. Ordinamento database
    # ------------------------------------

    database.sort(
        key=lambda b: (
            (
                b.get("stato")
                == "SCADUTO"
            ),
            (
                b.get("scadenza")
                or "9999-12-31"
            ),
            b.get(
                "nome",
                ""
            ).lower(),
        )
    )

    # ------------------------------------
    # 5. Salvataggio
    # ------------------------------------

    if (
        aggiunti > 0
        or modifiche_scadenze > 0
    ):

        salva_bandi(
            database
        )

        print()

        print(
            "Database salvato."
        )

    else:

        print()

        print(
            "Nessuna modifica "
            "al database."
        )

    # ------------------------------------
    # 6. Riepilogo
    # ------------------------------------

    print()

    print(
        "Nuovi bandi aggiunti: "
        f"{aggiunti}"
    )

    print(
        "Stati aggiornati: "
        f"{modifiche_scadenze}"
    )

    print(
        "Totale bandi nel database: "
        f"{len(database)}"
    )

    print(
        "======================================"
    )


# ============================================================
# AVVIO
# ============================================================

if __name__ == "__main__":

    main()
