import json
import re
import html as html_lib
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse


# ============================================================
# BandiAP - Motore automatico aggiornamento bandi
# Versione 7
#
# Obiettivi:
# - preservare i bandi inseriti manualmente
# - eliminare i falsi positivi automatici della V6
# - cercare nuovi bandi su fonti ufficiali
# - escludere menu, archivi e pagine generiche
# - escludere opportunità chiaramente vecchie
# - evitare duplicati
# ============================================================


# ============================================================
# CONFIGURAZIONE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BANDI_FILE = BASE_DIR / "bandi.json"

OGGI = datetime.now().date()
ANNO_CORRENTE = OGGI.year


FONTI = [
    {
        "nome": "Regione Marche",
        "url": (
            "https://www.regione.marche.it/Entra-in-Regione/"
            "Bandi-e-opportunita/Bandi-attivi"
        ),
        "territorio": "Regione Marche",
        "domini": (
            "regione.marche.it",
            "www.regione.marche.it",
            "static.regione.marche.it",
        ),
    },
    {
        "nome": "Camera di Commercio delle Marche",
        "url": (
            "https://www.marche.camcom.it/"
            "fai-crescere-la-tua-impresa/bandi-e-contributi"
        ),
        "territorio": "Regione Marche",
        "domini": (
            "marche.camcom.it",
            "www.marche.camcom.it",
        ),
    },
    {
        "nome": "GAL Piceno",
        "url": "https://galpiceno.it/bandi/",
        "territorio": "GAL Piceno",
        "domini": (
            "galpiceno.it",
            "www.galpiceno.it",
        ),
    },
]


# ============================================================
# PAROLE CHIAVE
# ============================================================

PAROLE_FORTI_BANDO = (
    "bando",
    "avviso pubblico",
    "concessione di contribut",
    "contributi",
    "voucher",
    "incentiv",
    "agevolaz",
    "finanziamento",
    "finanziamenti",
)


PAROLE_UTILI = (
    "impresa",
    "imprese",
    "profession",
    "startup",
    "start up",
    "microimpres",
    "pmi",
    "mpmi",
    "agricol",
    "turism",
    "artigian",
    "commerc",
    "digital",
    "innovazione",
    "internazional",
    "investiment",
    "acquacoltura",
    "pesca",
    "feampa",
    "srd",
    "srg",
    "csr",
)


TITOLI_ESCLUSI_ESATTI = {
    "bandi di contributo e opportunita",
    "vai al contenuto",
    "vai alla navigazione del sito",
    "avvia la tua impresa",
    "gestisci la tua impresa",
    "fai crescere la tua impresa",
    "tutela impresa e consumatore",
    "gestisci crisi impresa e insolvenza",
    "i progetti finanziati",
    "i pubblicazione",
    "ii pubblicazione",
    "iii pubblicazione",
    "iv pubblicazione",
    "v pubblicazione",
    "vi pubblicazione",
}


FRASI_ESCLUSE = (
    "privacy",
    "cookie",
    "facebook",
    "instagram",
    "youtube",
    "linkedin",
    "newsletter",
    "amministrazione trasparente",
    "accessibilita",
    "mappa del sito",
    "contatti",
    "login",
    "accedi",
    "sostegno preparatorio",
    "gestione e animazione",
    "supporto interventi strategia clld",
)


# ============================================================
# DATABASE
# ============================================================

def carica_bandi():

    if not BANDI_FILE.exists():
        print(f"Database non trovato: {BANDI_FILE}")
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

    testo = html_lib.unescape(testo)

    testo = re.sub(
        r"\s+",
        " ",
        testo
    )

    return testo.strip()


def normalizza_testo(testo):

    testo = pulisci_testo(testo).lower()

    sostituzioni = {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
        "’": "'",
        "“": '"',
        "”": '"',
    }

    for vecchio, nuovo in sostituzioni.items():
        testo = testo.replace(vecchio, nuovo)

    testo = re.sub(
        r"[^a-z0-9]+",
        " ",
        testo
    )

    return re.sub(
        r"\s+",
        " ",
        testo
    ).strip()


# ============================================================
# DOWNLOAD
# ============================================================

def scarica_pagina(url):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; BandiAP/7.0)"
        ),
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
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
# DATE
# ============================================================

def converti_data(data):

    if not data:
        return ""

    data = data.strip()

    for formato in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ):

        try:
            d = datetime.strptime(
                data,
                formato
            )

            return d.strftime("%Y-%m-%d")

        except ValueError:
            pass

    return ""


def estrai_date(testo):

    date_trovate = []

    patterns = (
        r"\b([0-3]?\d/[01]?\d/20\d{2})\b",
        r"\b([0-3]?\d-[01]?\d-20\d{2})\b",
        r"\b(20\d{2}-[01]\d-[0-3]\d)\b",
    )

    for pattern in patterns:

        for valore in re.findall(pattern, testo):

            data = converti_data(valore)

            if data and data not in date_trovate:
                date_trovate.append(data)

    return date_trovate


def estrai_scadenza(testo):

    testo_norm = normalizza_testo(testo)

    patterns_scadenza = (
        r"scadenza.{0,80}?([0-3]?\d/[01]?\d/20\d{2})",
        r"scadenza.{0,80}?([0-3]?\d-[01]?\d-20\d{2})",
        r"entro.{0,80}?([0-3]?\d/[01]?\d/20\d{2})",
        r"entro.{0,80}?([0-3]?\d-[01]?\d-20\d{2})",
        r"termine.{0,80}?([0-3]?\d/[01]?\d/20\d{2})",
        r"termine.{0,80}?([0-3]?\d-[01]?\d-20\d{2})",
    )

    for pattern in patterns_scadenza:

        match = re.search(
            pattern,
            testo_norm,
            flags=re.I
        )

        if match:

            data = converti_data(
                match.group(1)
            )

            if data:
                return data

    date = estrai_date(testo)

    future = []

    for data in date:

        try:
            d = datetime.strptime(
                data,
                "%Y-%m-%d"
            ).date()

            if d >= OGGI:
                future.append(d)

        except ValueError:
            pass

    if future:
        return min(future).strftime("%Y-%m-%d")

    return ""


def data_testo(data):

    if not data:
        return "Verificare sulla fonte ufficiale"

    try:

        d = datetime.strptime(
            data,
            "%Y-%m-%d"
        )

    except ValueError:
        return data

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


# ============================================================
# STATO BANDO
# ============================================================

def rileva_stato(testo, scadenza):

    t = normalizza_testo(testo)

    chiusure = (
        "bando chiuso",
        "avviso chiuso",
        "procedura chiusa",
        "sportello chiuso",
        "domande chiuse",
        "termini chiusi",
        "chiusura anticipata",
        "esaurimento delle risorse",
        "esaurimento risorse",
        "fondi esauriti",
        "risorse esaurite",
        "non e piu possibile presentare",
        "non e possibile presentare",
    )

    if any(
        frase in t
        for frase in chiusure
    ):
        return "SCADUTO"

    if scadenza:

        try:
            d = datetime.strptime(
                scadenza,
                "%Y-%m-%d"
            ).date()

            if d < OGGI:
                return "SCADUTO"

        except ValueError:
            pass

    return "APERTO"


# ============================================================
# FILTRI
# ============================================================

def dominio_consentito(url, fonte):

    dominio = urlparse(
        url
    ).netloc.lower()

    return any(
        dominio == consentito
        or dominio.endswith("." + consentito)
        for consentito in fonte["domini"]
    )


def titolo_generico(titolo):

    t = normalizza_testo(titolo)

    if not t:
        return True

    if t in TITOLI_ESCLUSI_ESATTI:
        return True

    if len(t) < 12:
        return True

    if re.fullmatch(
        r"(i|ii|iii|iv|v|vi|vii|viii|ix|x) pubblicazione.*",
        t
    ):
        return True

    if re.fullmatch(
        r"sottomisura [0-9 .a-z]+",
        t
    ):
        return True

    if re.fullmatch(
        r"misura [0-9 .a-z]+",
        t
    ):
        return True

    if any(
        frase in t
        for frase in FRASI_ESCLUSE
    ):
        return True

    return False


def contiene_anno_vecchio(titolo):

    anni = re.findall(
        r"\b(20\d{2})\b",
        titolo
    )

    if not anni:
        return False

    anni = [
        int(anno)
        for anno in anni
    ]

    anno_massimo = max(anni)

    # Se il titolo parla esplicitamente solo
    # di annualità precedenti, lo scartiamo.
    if anno_massimo < ANNO_CORRENTE:
        return True

    return False


def sembra_bando(titolo):

    t = normalizza_testo(titolo)

    if titolo_generico(titolo):
        return False

    if contiene_anno_vecchio(titolo):
        return False

    forte = any(
        parola in t
        for parola in PAROLE_FORTI_BANDO
    )

    utile = any(
        parola in t
        for parola in PAROLE_UTILI
    )

    # Titoli con una parola forte sono candidati.
    if forte:
        return True

    # Interventi CSR/GAL devono almeno
    # contenere un riferimento economico/impresa.
    if (
        utile
        and any(
            codice in t
            for codice in (
                "srd",
                "srg",
                "csr",
                "feampa",
            )
        )
    ):
        return True

    return False


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
            "avvio impresa",
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

    return list(
        dict.fromkeys(profili)
    )


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
        settori = ["altro"]

    return settori


# ============================================================
# ID
# ============================================================

def genera_id(fonte, titolo):

    stringa = (
        fonte.strip().lower()
        + "|"
        + normalizza_testo(titolo)
    )

    return hashlib.sha256(
        stringa.encode("utf-8")
    ).hexdigest()[:16]


# ============================================================
# ESTRAZIONE LINK
# ============================================================

def estrai_link(pagina, fonte):

    risultati = []
    visti = set()

    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.I | re.S
    )

    for href, contenuto in pattern.findall(pagina):

        titolo = pulisci_testo(
            contenuto
        )

        if not sembra_bando(titolo):
            continue

        url = urljoin(
            fonte["url"],
            html_lib.unescape(href)
        )

        if not url.startswith(
            ("http://", "https://")
        ):
            continue

        if not dominio_consentito(
            url,
            fonte
        ):
            continue

        chiave = (
            normalizza_testo(titolo),
            url.rstrip("/")
        )

        if chiave in visti:
            continue

        visti.add(chiave)

        risultati.append(
            {
                "titolo": titolo,
                "url": url,
            }
        )

    return risultati


# ============================================================
# ANALISI BANDO
# ============================================================

def analizza_bando(link, fonte):

    titolo = link["titolo"]
    url = link["url"]

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
            f"  Errore dettaglio: {e}"
        )

        return None

    testo_completo = (
        titolo
        + " "
        + testo[:30000]
    )

    scadenza = estrai_scadenza(
        testo_completo
    )

    stato = rileva_stato(
        testo_completo,
        scadenza
    )

    # La V7 importa automaticamente
    # soltanto opportunità che risultano aperte.
    if stato != "APERTO":

        print(
            "  ESCLUSO: risulta chiuso/scaduto"
        )

        return None

    # Se non troviamo alcuna data futura,
    # manteniamo il candidato ma segnaliamo
    # che la scadenza va verificata.
    return {
        "id": genera_id(
            fonte["nome"],
            titolo
        ),
        "nome": titolo,
        "ente": fonte["nome"],
        "stato": stato,
        "scadenza": scadenza,
        "scadenzaTesto": data_testo(scadenza),
        "profili": classifica_profili(
            testo_completo
        ),
        "settori": classifica_settori(
            testo_completo
        ),
        "descrizione": (
            "Opportunità rilevata automaticamente "
            "da BandiAP su fonte ufficiale."
        ),
        "requisiti": (
            "Verificare beneficiari, requisiti, "
            "spese ammissibili e condizioni "
            "sulla fonte ufficiale."
        ),
        "dotazione": (
            "Verificare sulla fonte ufficiale"
        ),
        "territorio": fonte["territorio"],
        "url": url,
        "fonteAutomatica": True,
        "versioneMotore": 7,
        "ultimoControllo": OGGI.strftime(
            "%Y-%m-%d"
        ),
    }


# ============================================================
# PULIZIA V6
# ============================================================

def pulisci_database_v6(database):

    puliti = []
    eliminati = 0

    for bando in database:

        # Tutti i record creati automaticamente
        # dalla V6 vengono eliminati e rivalutati.
        if (
            bando.get("fonteAutomatica")
            is True
            and bando.get("versioneMotore") != 7
        ):
            eliminati += 1
            continue

        puliti.append(bando)

    return puliti, eliminati


# ============================================================
# SCADENZE DATABASE ESISTENTE
# ============================================================

def aggiorna_scadenze(database):

    modifiche = 0

    for bando in database:

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
            continue

        nuovo_stato = (
            "SCADUTO"
            if data < OGGI
            else "APERTO"
        )

        if bando.get("stato") != nuovo_stato:

            bando["stato"] = nuovo_stato
            modifiche += 1

            print(
                "Stato aggiornato: "
                f"{bando.get('nome')} "
                f"-> {nuovo_stato}"
            )

    return modifiche


# ============================================================
# DUPLICATI
# ============================================================

def chiave_bando(bando):

    url = (
        bando.get("url", "")
        .strip()
        .rstrip("/")
        .lower()
    )

    if url:
        return "url:" + url

    return (
        "nome:"
        + normalizza_testo(
            bando.get("nome", "")
        )
    )


def aggiungi_nuovi_bandi(database, trovati):

    chiavi = {
        chiave_bando(bando)
        for bando in database
    }

    nomi = {
        normalizza_testo(
            bando.get("nome", "")
        )
        for bando in database
    }

    aggiunti = 0

    for nuovo in trovati:

        chiave = chiave_bando(
            nuovo
        )

        nome = normalizza_testo(
            nuovo.get("nome", "")
        )

        if chiave in chiavi:
            continue

        # Seconda protezione contro duplicati:
        # stesso titolo ma URL differente.
        if nome and nome in nomi:
            continue

        database.append(
            nuovo
        )

        chiavi.add(
            chiave
        )

        nomi.add(
            nome
        )

        aggiunti += 1

        print(
            "NUOVO BANDO VALIDATO: "
            f"{nuovo.get('nome')}"
        )

    return aggiunti


# ============================================================
# CONTROLLO FONTE
# ============================================================

def controlla_fonte(fonte):

    print()
    print("=" * 60)
    print(f"Controllo: {fonte['nome']}")
    print(fonte["url"])

    try:

        pagina = scarica_pagina(
            fonte["url"]
        )

    except Exception as e:

        print(
            f"Errore download fonte: {e}"
        )

        return []

    links = estrai_link(
        pagina,
        fonte
    )

    print(
        "Candidati dopo filtro V7: "
        f"{len(links)}"
    )

    risultati = []

    # Limite prudenziale.
    for link in links[:30]:

        try:

            bando = analizza_bando(
                link,
                fonte
            )

            if bando:
                risultati.append(
                    bando
                )

        except Exception as e:

            print(
                "Errore analisi "
                f"{link.get('titolo')}: "
                f"{e}"
            )

    print(
        "Bandi validati dalla fonte: "
        f"{len(risultati)}"
    )

    return risultati


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("BandiAP - aggiornamento automatico V7")
    print("=" * 60)

    print(
        f"Database: {BANDI_FILE}"
    )

    database_originale = carica_bandi()

    print(
        "Record iniziali: "
        f"{len(database_originale)}"
    )

    # --------------------------------------------------------
    # 1. Rimozione importazioni automatiche errate della V6
    # --------------------------------------------------------

    database, eliminati_v6 = (
        pulisci_database_v6(
            database_originale
        )
    )

    print(
        "Record automatici V6 eliminati: "
        f"{eliminati_v6}"
    )

    print(
        "Record preservati: "
        f"{len(database)}"
    )

    # --------------------------------------------------------
    # 2. Aggiornamento scadenze record preservati
    # --------------------------------------------------------

    modifiche_scadenze = (
        aggiorna_scadenze(
            database
        )
    )

    # --------------------------------------------------------
    # 3. Ricerca
    # --------------------------------------------------------

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
        "Bandi automatici validati complessivi: "
        f"{len(tutti_trovati)}"
    )

    # --------------------------------------------------------
    # 4. Inserimento
    # --------------------------------------------------------

    aggiunti = aggiungi_nuovi_bandi(
        database,
        tutti_trovati
    )

    # --------------------------------------------------------
    # 5. Ordinamento
    # --------------------------------------------------------

    database.sort(
        key=lambda b: (
            b.get("stato") == "SCADUTO",
            b.get("scadenza") or "9999-12-31",
            b.get("nome", "").lower(),
        )
    )

    # --------------------------------------------------------
    # 6. Salvataggio
    # --------------------------------------------------------

    salva_bandi(
        database
    )

    # --------------------------------------------------------
    # 7. Riepilogo
    # --------------------------------------------------------

    print()
    print("=" * 60)

    print(
        "V6 eliminati: "
        f"{eliminati_v6}"
    )

    print(
        "Nuovi bandi V7 aggiunti: "
        f"{aggiunti}"
    )

    print(
        "Stati aggiornati: "
        f"{modifiche_scadenze}"
    )

    print(
        "Totale finale database: "
        f"{len(database)}"
    )

    print("=" * 60)


# ============================================================
# AVVIO
# ============================================================

if __name__ == "__main__":
    main()
