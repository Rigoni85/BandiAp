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
# Versione 8
#
# Obiettivo:
# pubblicare solo opportunità ragionevolmente utili
# a imprese/professionisti/organizzazioni del territorio
# di Ascoli Piceno e delle Marche.
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
# FILTRI GENERALI
# ============================================================

PAROLE_BANDO = (
    "bando",
    "avviso pubblico",
    "contribut",
    "voucher",
    "incentiv",
    "agevol",
    "finanziamento",
    "finanziamenti",
    "sostegno",
)


PAROLE_IMPRESA = (
    "impresa",
    "imprese",
    "imprenditor",
    "professionist",
    "lavoratori autonom",
    "startup",
    "start up",
    "pmi",
    "mpmi",
    "microimpres",
    "artigian",
    "commerc",
    "azienda",
    "aziende",
    "agricol",
    "allevator",
    "acquacoltura",
    "pesca",
    "operatori economici",
    "terzo settore",
    "associazioni",
)


CODICI_AMMESSI = (
    "srd",
    "srg",
    "srh",
    "feampa",
    "csr",
)


GAL_ESCLUSI = (
    "gal colli esini",
    "colli esini san vicino",
    "gal montefeltro",
    "montefeltro sviluppo",
    "gal fermano",
    "fermano leader",
    "gal sibilla",
)


TITOLI_ESCLUSI = (
    "bandi e contributi",
    "bandi di contributo e opportunita",
    "archivio bandi contributi",
    "i progetti finanziati",
    "vai al contenuto",
    "vai alla navigazione",
    "avvia la tua impresa",
    "gestisci la tua impresa",
    "fai crescere la tua impresa",
    "tutela impresa e consumatore",
    "gestisci crisi impresa e insolvenza",
)


PAROLE_DOCUMENTO = (
    "manuale",
    "modulistica",
    "allegato",
    "fac simile",
    "facsimile",
    "istruzioni",
    "informativa privacy",
    "schema domanda",
    "modello domanda",
    "graduatoria",
    "decreto liquidazione",
)


PAROLE_ENTI_PUBBLICI = (
    "ai comuni",
    "dei comuni",
    "comuni non capoluogo",
    "enti locali",
    "amministrazioni pubbliche",
    "pubbliche amministrazioni",
    "unioni di comuni",
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
            "(compatible; BandiAP/8.0)"
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

    for formato in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ):

        try:
            d = datetime.strptime(
                data.strip(),
                formato
            )

            return d.strftime("%Y-%m-%d")

        except ValueError:
            pass

    return ""


def estrai_date(testo):

    risultati = []

    patterns = (
        r"\b([0-3]?\d/[01]?\d/20\d{2})\b",
        r"\b([0-3]?\d-[01]?\d-20\d{2})\b",
        r"\b(20\d{2}-[01]\d-[0-3]\d)\b",
    )

    for pattern in patterns:

        for valore in re.findall(pattern, testo):

            data = converti_data(valore)

            if data and data not in risultati:
                risultati.append(data)

    return risultati


def estrai_scadenza(testo):

    patterns = (
        r"scadenza.{0,100}?([0-3]?\d/[01]?\d/20\d{2})",
        r"scadenza.{0,100}?([0-3]?\d-[01]?\d-20\d{2})",
        r"entro.{0,100}?([0-3]?\d/[01]?\d/20\d{2})",
        r"entro.{0,100}?([0-3]?\d-[01]\d-20\d{2})",
        r"termine.{0,100}?([0-3]?\d/[01]?\d/20\d{2})",
        r"termine.{0,100}?([0-3]?\d-[01]?\d-20\d{2})",
    )

    testo_norm = normalizza_testo(testo)

    for pattern in patterns:

        match = re.search(
            pattern,
            testo_norm,
            re.I
        )

        if match:

            data = converti_data(
                match.group(1)
            )

            if data:
                return data

    future = []

    for valore in estrai_date(testo):

        try:
            data = datetime.strptime(
                valore,
                "%Y-%m-%d"
            ).date()

            if data >= OGGI:
                future.append(data)

        except ValueError:
            pass

    if future:

        return min(
            future
        ).strftime("%Y-%m-%d")

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
# STATO
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
        "risorse esaurite",
        "fondi esauriti",
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
            data = datetime.strptime(
                scadenza,
                "%Y-%m-%d"
            ).date()

            if data < OGGI:
                return "SCADUTO"

        except ValueError:
            pass

    return "APERTO"


# ============================================================
# FILTRO TERRITORIALE
# ============================================================

def territorio_ammesso(testo):

    t = normalizza_testo(testo)

    if any(
        gal in t
        for gal in GAL_ESCLUSI
    ):
        return False

    return True


# ============================================================
# FILTRO DOCUMENTI
# ============================================================

def documento_accessorio(titolo, url):

    t = normalizza_testo(titolo)

    if any(
        parola in t
        for parola in PAROLE_DOCUMENTO
    ):
        return True

    # Un PDF viene ammesso soltanto se il titolo
    # sembra chiaramente il bando vero e proprio.
    if url.lower().split("?")[0].endswith(".pdf"):

        if not any(
            parola in t
            for parola in (
                "bando",
                "avviso pubblico",
            )
        ):
            return True

    return False


# ============================================================
# FILTRO ENTI PUBBLICI
# ============================================================

def solo_ente_pubblico(testo):

    t = normalizza_testo(testo)

    ente = any(
        frase in t
        for frase in PAROLE_ENTI_PUBBLICI
    )

    impresa = any(
        parola in t
        for parola in PAROLE_IMPRESA
    )

    return ente and not impresa


# ============================================================
# FILTRO TITOLI
# ============================================================

def titolo_valido(titolo):

    t = normalizza_testo(titolo)

    if len(t) < 12:
        return False

    if t in TITOLI_ESCLUSI:
        return False

    if any(
        escluso == t
        for escluso in TITOLI_ESCLUSI
    ):
        return False

    if re.fullmatch(
        r"intervento s[a-z]{2}[0-9]+(?: [a-z])?",
        t
    ):
        return False

    if re.fullmatch(
        r"(i|ii|iii|iv|v|vi|vii|viii|ix|x) pubblicazione.*",
        t
    ):
        return False

    if re.fullmatch(
        r"sottomisura [0-9a-z .]+",
        t
    ):
        return False

    # Esclusione annualità chiaramente vecchie.
    anni = re.findall(
        r"\b(20\d{2})\b",
        titolo
    )

    if anni:

        anni_numerici = [
            int(anno)
            for anno in anni
        ]

        if max(anni_numerici) < ANNO_CORRENTE:
            return False

    return True


# ============================================================
# DOMINIO
# ============================================================

def dominio_consentito(url, fonte):

    dominio = urlparse(
        url
    ).netloc.lower()

    return any(
        dominio == consentito
        or dominio.endswith(
            "." + consentito
        )
        for consentito in fonte["domini"]
    )


# ============================================================
# PUNTEGGIO CANDIDATO
# ============================================================

def punteggio_candidato(titolo):

    t = normalizza_testo(titolo)

    punti = 0

    if "bando" in t:
        punti += 4

    if "avviso pubblico" in t:
        punti += 4

    if "contribut" in t:
        punti += 3

    if "voucher" in t:
        punti += 3

    if "finanziamento" in t:
        punti += 2

    if "incentiv" in t:
        punti += 2

    if "agevol" in t:
        punti += 2

    if any(
        parola in t
        for parola in PAROLE_IMPRESA
    ):
        punti += 3

    if any(
        codice in t
        for codice in CODICI_AMMESSI
    ):
        punti += 1

    if "gal piceno" in t:
        punti += 3

    return punti


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

        if not titolo_valido(
            titolo
        ):
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

        if documento_accessorio(
            titolo,
            url
        ):
            continue

        if not territorio_ammesso(
            titolo
        ):
            continue

        if solo_ente_pubblico(
            titolo
        ):
            continue

        punti = punteggio_candidato(
            titolo
        )

        # Soglia prudenziale.
        if punti < 4:
            continue

        chiave = (
            normalizza_testo(titolo),
            url.rstrip("/")
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
                "punteggio": punti,
            }
        )

    return risultati


# ============================================================
# CLASSIFICAZIONE PROFILI
# ============================================================

def classifica_profili(testo):

    t = normalizza_testo(testo)

    profili = []

    regole = {
        "nuova": (
            "nuova impresa",
            "nuove imprese",
            "creazione impresa",
            "avvio impresa",
            "startup",
            "start up",
        ),
        "micro": (
            "microimpresa",
            "micro impresa",
            "micro imprese",
            "mpmi",
        ),
        "piccola": (
            "piccola impresa",
            "piccole imprese",
            "pmi",
            "mpmi",
        ),
        "media": (
            "media impresa",
            "medie imprese",
            "pmi",
            "mpmi",
        ),
        "agricola": (
            "agricol",
            "zootec",
            "allevator",
        ),
        "acquacoltura": (
            "acquacoltura",
            "feampa",
        ),
        "professionista": (
            "professionist",
            "lavoratore autonomo",
            "lavoratori autonomi",
        ),
        "associazione": (
            "associazioni",
            "terzo settore",
            "ets",
        ),
    }

    for profilo, parole in regole.items():

        if any(
            parola in t
            for parola in parole
        ):
            profili.append(profilo)

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


# ============================================================
# CLASSIFICAZIONE SETTORI
# ============================================================

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
            "allevator",
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
# ANALISI DETTAGLIO
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
            f"  ESCLUSO: errore lettura ({e})"
        )

        return None

    testo_completo = (
        titolo
        + " "
        + testo[:30000]
    )

    # Secondo filtro territoriale sul dettaglio.
    if not territorio_ammesso(
        titolo
    ):
        print(
            "  ESCLUSO: territorio GAL non pertinente"
        )
        return None

    if solo_ente_pubblico(
        titolo
    ):
        print(
            "  ESCLUSO: destinatari enti pubblici"
        )
        return None

    scadenza = estrai_scadenza(
        testo_completo
    )

    stato = rileva_stato(
        testo_completo,
        scadenza
    )

    if stato != "APERTO":

        print(
            "  ESCLUSO: chiuso/scaduto"
        )

        return None

    return {
        "id": genera_id(
            fonte["nome"],
            titolo
        ),
        "nome": titolo,
        "ente": fonte["nome"],
        "stato": "APERTO",
        "scadenza": scadenza,
        "scadenzaTesto": data_testo(
            scadenza
        ),
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
            "Verificare beneficiari, requisiti "
            "e spese ammissibili sulla fonte ufficiale."
        ),
        "dotazione": (
            "Verificare sulla fonte ufficiale"
        ),
        "territorio": fonte["territorio"],
        "url": url,
        "fonteAutomatica": True,
        "versioneMotore": 8,
        "punteggioAutomatico": link[
            "punteggio"
        ],
        "ultimoControllo": OGGI.strftime(
            "%Y-%m-%d"
        ),
    }


# ============================================================
# PULIZIA VERSIONI PRECEDENTI
# ============================================================

def pulisci_database_automatico(database):

    puliti = []
    eliminati = 0

    for bando in database:

        # I record manuali/originali vengono sempre
        # preservati.
        if bando.get(
            "fonteAutomatica"
        ) is True:

            eliminati += 1
            continue

        puliti.append(
            bando
        )

    return puliti, eliminati


# ============================================================
# AGGIORNAMENTO SCADENZE
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

        if bando.get(
            "stato"
        ) != nuovo_stato:

            bando["stato"] = nuovo_stato

            modifiche += 1

    return modifiche


# ============================================================
# DUPLICATI
# ============================================================

def aggiungi_nuovi_bandi(
    database,
    trovati
):

    urls = {
        b.get("url", "")
        .rstrip("/")
        .lower()
        for b in database
        if b.get("url")
    }

    nomi = {
        normalizza_testo(
            b.get("nome", "")
        )
        for b in database
    }

    aggiunti = 0

    for nuovo in trovati:

        url = (
            nuovo.get("url", "")
            .rstrip("/")
            .lower()
        )

        nome = normalizza_testo(
            nuovo.get("nome", "")
        )

        if url and url in urls:
            continue

        if nome and nome in nomi:
            continue

        database.append(
            nuovo
        )

        if url:
            urls.add(url)

        if nome:
            nomi.add(nome)

        aggiunti += 1

        print(
            "NUOVO BANDO V8: "
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
        "Candidati V8 dopo filtri: "
        f"{len(links)}"
    )

    risultati = []

    for link in links[:30]:

        bando = analizza_bando(
            link,
            fonte
        )

        if bando:
            risultati.append(
                bando
            )

    print(
        "Bandi V8 validati: "
        f"{len(risultati)}"
    )

    return risultati


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("BandiAP - aggiornamento automatico V8")
    print("=" * 60)

    database_originale = carica_bandi()

    print(
        "Record iniziali: "
        f"{len(database_originale)}"
    )

    # --------------------------------------------------------
    # 1. Ripristino base manuale
    # --------------------------------------------------------

    database, automatici_eliminati = (
        pulisci_database_automatico(
            database_originale
        )
    )

    print(
        "Record automatici precedenti eliminati: "
        f"{automatici_eliminati}"
    )

    print(
        "Record originali preservati: "
        f"{len(database)}"
    )

    # --------------------------------------------------------
    # 2. Scadenze record originali
    # --------------------------------------------------------

    modifiche_scadenze = (
        aggiorna_scadenze(
            database
        )
    )

    # --------------------------------------------------------
    # 3. Ricerca fonti
    # --------------------------------------------------------

    trovati = []

    for fonte in FONTI:

        risultati = controlla_fonte(
            fonte
        )

        trovati.extend(
            risultati
        )

    print()
    print(
        "Bandi V8 validati complessivi: "
        f"{len(trovati)}"
    )

    # --------------------------------------------------------
    # 4. Inserimento
    # --------------------------------------------------------

    aggiunti = aggiungi_nuovi_bandi(
        database,
        trovati
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
    # RIEPILOGO
    # --------------------------------------------------------

    print()
    print("=" * 60)

    print(
        "Automatici precedenti eliminati: "
        f"{automatici_eliminati}"
    )

    print(
        "Nuovi bandi V8 aggiunti: "
        f"{aggiunti}"
    )

    print(
        "Stati originali aggiornati: "
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
