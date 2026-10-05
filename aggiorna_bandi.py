import json
import re
import html as html_lib
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse


# ============================================================
# BandiAP - Motore automatico bandi
# Versione 9.1
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BANDI_FILE = BASE_DIR / "bandi.json"

OGGI = datetime.now().date()
ANNO = OGGI.year


# ============================================================
# FONTI
# ============================================================

FONTI = [
    {
        "nome": "Regione Marche",
        "url": (
            "https://www.regione.marche.it/Entra-in-Regione/"
            "Bandi-e-opportunita/Bandi-attivi"
        ),
        "territorio": "Regione Marche",
        "tipo": "regione",
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
        "tipo": "camera",
        "domini": (
            "marche.camcom.it",
            "www.marche.camcom.it",
        ),
    },
    {
        "nome": "GAL Piceno",
        "url": "https://galpiceno.it/bandi/",
        "territorio": "GAL Piceno",
        "tipo": "gal_piceno",
        "domini": (
            "galpiceno.it",
            "www.galpiceno.it",
        ),
    },
]


GAL_ESCLUSI = (
    "gal colli esini",
    "colli esini san vicino",
    "gal montefeltro",
    "montefeltro sviluppo",
    "gal fermano",
    "fermano leader",
    "gal sibilla",
)


DOCUMENTI_ESCLUSI = (
    "manuale",
    "modulistica",
    "fac simile",
    "facsimile",
    "istruzioni",
    "informativa privacy",
    "schema domanda",
    "modello domanda",
    "graduatoria",
    "liquidazione",
    "faq",
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
        flags=re.I | re.S,
    )

    testo = re.sub(
        r"<style.*?</style>",
        " ",
        testo,
        flags=re.I | re.S,
    )

    testo = re.sub(
        r"<[^>]+>",
        " ",
        testo,
    )

    testo = html_lib.unescape(testo)

    return re.sub(
        r"\s+",
        " ",
        testo,
    ).strip()


def normalizza(testo):

    testo = pulisci_testo(testo).lower()

    for a, b in {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
    }.items():

        testo = testo.replace(a, b)

    testo = re.sub(
        r"[^a-z0-9]+",
        " ",
        testo,
    )

    return re.sub(
        r"\s+",
        " ",
        testo,
    ).strip()


# ============================================================
# DATABASE
# ============================================================

def carica_database():

    if not BANDI_FILE.exists():
        return []

    try:

        with open(
            BANDI_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            dati = json.load(f)

        if isinstance(dati, list):
            return dati

        if isinstance(dati, dict):
            return dati.get("bandi", [])

    except Exception as e:

        print(
            f"Errore database: {e}"
        )

    return []


def salva_database(database):

    with open(
        BANDI_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            database,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# DOWNLOAD
# ============================================================

def scarica(url):

    req = Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 (compatible; BandiAP/9.1)",
            "Accept-Language":
                "it-IT,it;q=0.9",
        },
    )

    with urlopen(
        req,
        timeout=30,
    ) as risposta:

        return risposta.read().decode(
            "utf-8",
            errors="ignore",
        )


# ============================================================
# DATE - CORREZIONE V9.1
# ============================================================

def converti_data(valore):

    for formato in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ):

        try:

            return datetime.strptime(
                valore.strip(),
                formato,
            ).strftime("%Y-%m-%d")

        except ValueError:
            pass

    return ""


def estrai_scadenza(testo):

    """
    IMPORTANTE:
    ricerca sul testo originale, NON normalizzato.
    Così / e - delle date vengono conservati.
    """

    testo = pulisci_testo(testo)

    patterns = (
        r"scadenza.{0,150}?([0-3]?\d/[01]?\d/20\d{2})",
        r"scadenza.{0,150}?([0-3]?\d-[01]?\d-20\d{2})",

        r"entro.{0,150}?([0-3]?\d/[01]?\d/20\d{2})",
        r"entro.{0,150}?([0-3]?\d-[01]?\d-20\d{2})",

        r"termine.{0,150}?([0-3]?\d/[01]?\d/20\d{2})",
        r"termine.{0,150}?([0-3]?\d-[01]?\d-20\d{2})",

        r"fino al.{0,150}?([0-3]?\d/[01]?\d/20\d{2})",
        r"fino al.{0,150}?([0-3]?\d-[01]?\d-20\d{2})",

        r"presentazione.{0,150}?([0-3]?\d/[01]?\d/20\d{2})",
        r"presentazione.{0,150}?([0-3]?\d-[01]?\d-20\d{2})",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            testo,
            flags=re.I,
        )

        if match:

            data = converti_data(
                match.group(1)
            )

            if data:
                return data

    return ""


def formatta_data(data):

    if not data:
        return "Verificare sulla fonte ufficiale"

    try:

        d = datetime.strptime(
            data,
            "%Y-%m-%d",
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

def verifica_stato(testo, scadenza):

    t = normalizza(testo)

    chiusure = (
        "bando chiuso",
        "avviso chiuso",
        "procedura chiusa",
        "sportello chiuso",
        "domande chiuse",
        "termini chiusi",
        "chiusura anticipata",
        "risorse esaurite",
        "fondi esauriti",
        "esaurimento delle risorse",
        "esaurimento risorse",
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
                "%Y-%m-%d",
            ).date()

            if d < OGGI:
                return "SCADUTO"

            return "APERTO"

        except ValueError:
            pass

    # Segnali positivi espliciti
    aperture = (
        "bando aperto",
        "avviso aperto",
        "sportello aperto",
        "presentare domanda",
        "presentazione delle domande",
        "presentazione domanda",
    )

    if any(
        frase in t
        for frase in aperture
    ):
        return "APERTO"

    return "DA_VERIFICARE"


# ============================================================
# ESTRATTO LOCALE DELLA PAGINA
# ============================================================

def estrai_contesto(titolo, testo):

    """
    Evita di classificare un bando usando tutto
    il footer/menu della pagina.

    Cerca il titolo nella pagina e usa una
    finestra circostante.
    """

    testo_pulito = pulisci_testo(testo)

    titolo_breve = pulisci_testo(
        titolo
    )[:120]

    posizione = testo_pulito.lower().find(
        titolo_breve.lower()
    )

    if posizione >= 0:

        inizio = max(
            0,
            posizione - 500,
        )

        fine = min(
            len(testo_pulito),
            posizione + 8000,
        )

        return testo_pulito[
            inizio:fine
        ]

    # Se il titolo non è individuabile,
    # usiamo soltanto l'inizio della pagina.
    return testo_pulito[:10000]


# ============================================================
# BENEFICIARIO
# ============================================================

def classifica_beneficiario(titolo, contesto):

    titolo_n = normalizza(titolo)
    contesto_n = normalizza(contesto)

    # Il titolo ha priorità sul corpo pagina.
    testo = (
        titolo_n
        + " "
        + contesto_n[:12000]
    )

    # ----------------------------------------
    # NUOVE IMPRESE
    # ----------------------------------------

    if any(
        x in testo
        for x in (
            "creazione nuove imprese",
            "creazione di nuove imprese",
            "nuove imprese",
            "nuova impresa",
            "avvio impresa",
            "avvio di impresa",
            "startup",
            "start up",
        )
    ):
        return "NUOVA_IMPRESA"

    # ----------------------------------------
    # AGRICOLTURA
    # ----------------------------------------

    if any(
        x in testo
        for x in (
            "imprese agricole",
            "imprenditori agricoli",
            "aziende agricole",
            "azienda agricola",
            "allevatori",
            "zootecn",
        )
    ):
        return "AGRICOLTURA"

    # ----------------------------------------
    # PROFESSIONISTI
    # ----------------------------------------

    if any(
        x in testo
        for x in (
            "liberi professionisti",
            "libero professionista",
            "lavoratori autonomi",
        )
    ):
        return "PROFESSIONISTA"

    # ----------------------------------------
    # IMPRESE
    # ----------------------------------------

    if any(
        x in testo
        for x in (
            "micro piccole e medie imprese",
            "micro piccole medie imprese",
            "microimprese",
            "micro imprese",
            "mpmi",
            "pmi",
            "imprese beneficiarie",
            "imprese ammesse",
            "imprese marchigiane",
            "imprese della regione marche",
            "imprese con sede",
            "imprese aventi sede",
            "operatori economici",
        )
    ):
        return "IMPRESA"

    # ----------------------------------------
    # ENTI PUBBLICI
    # ----------------------------------------

    if any(
        x in titolo_n
        for x in (
            "contributi ai comuni",
            "contributo ai comuni",
            "comuni non capoluogo",
            "iscrizione al registro regionale dei comuni",
        )
    ):
        return "ENTE_PUBBLICO"

    # ----------------------------------------
    # INTERMEDIARI
    # ----------------------------------------

    if any(
        x in titolo_n
        for x in (
            "portatori di interessi collettivi",
            "organismi non imprenditoriali",
            "its academy",
            "borse di studio its",
        )
    ):
        return "INTERMEDIARIO_ORGANIZZAZIONE"

    # ----------------------------------------
    # TERZO SETTORE
    # ----------------------------------------

    if any(
        x in testo
        for x in (
            "enti del terzo settore",
            "organizzazioni di volontariato",
            "associazioni di promozione sociale",
        )
    ):
        return "ASSOCIAZIONE_ETS"

    # ----------------------------------------
    # Impresa generica
    # ----------------------------------------

    if (
        "bando internazionalizzazione"
        in titolo_n
    ):
        return "IMPRESA"

    if (
        "voucher"
        in titolo_n
    ):
        return "IMPRESA"

    return "NON_DETERMINATO"


def pubblicabile(tipo):

    return tipo in (
        "IMPRESA",
        "NUOVA_IMPRESA",
        "PROFESSIONISTA",
        "AGRICOLTURA",
        "ASSOCIAZIONE_ETS",
    )


# ============================================================
# PROFILI
# ============================================================

def profili(tipo):

    return {
        "IMPRESA": [
            "micro",
            "piccola",
            "media",
        ],
        "NUOVA_IMPRESA": [
            "nuova",
        ],
        "PROFESSIONISTA": [
            "professionista",
        ],
        "AGRICOLTURA": [
            "agricola",
        ],
        "ASSOCIAZIONE_ETS": [
            "associazione",
        ],
    }.get(
        tipo,
        ["altro"],
    )


# ============================================================
# SETTORI
# ============================================================

def settori(testo):

    t = normalizza(testo)

    risultato = []

    regole = {
        "commercio": (
            "commerc",
            "retail",
        ),
        "turismo": (
            "turism",
            "ricettiv",
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
        ),
        "pesca": (
            "pesca",
            "acquacoltura",
            "feampa",
        ),
    }

    for nome, parole in regole.items():

        if any(
            p in t
            for p in parole
        ):
            risultato.append(nome)

    return risultato or ["altro"]


# ============================================================
# TERRITORIO
# ============================================================

def territorio_valido(testo):

    t = normalizza(testo)

    return not any(
        gal in t
        for gal in GAL_ESCLUSI
    )


# ============================================================
# ANNO
# ============================================================

def anno_vecchio(titolo):

    """
    Esclude esplicitamente bandi 2022/2023/2024/2025
    quando il titolo identifica chiaramente l'annualità.
    """

    t = normalizza(titolo)

    patterns = (
        r"\banno\s+(20\d{2})\b",
        r"\bsemestre\s+(20\d{2})\b",
        r"\bmarche\s+(20\d{2})\b",
        r"\bimpresa\s+(20\d{2})\b",
        r"\bformazione lavoro\s+(20\d{2})\b",
        r"\bpid\s+(20\d{2})\b",
        r"\bagricole\s+(20\d{2})\b",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            t,
        )

        if (
            match
            and int(match.group(1)) < ANNO
        ):
            return True

    return False


# ============================================================
# DOCUMENTI
# ============================================================

def documento_escluso(titolo):

    t = normalizza(titolo)

    if any(
        parola in t
        for parola in DOCUMENTI_ESCLUSI
    ):
        return True

    if (
        "bors" in t
        and "studio" in t
        and "its" in t
    ):
        return True

    return False


# ============================================================
# DOMINIO
# ============================================================

def dominio_valido(url, fonte):

    dominio = urlparse(
        url
    ).netloc.lower()

    return any(
        dominio == d
        or dominio.endswith("." + d)
        for d in fonte["domini"]
    )


# ============================================================
# ESTRAZIONE LINK STANDARD
# ============================================================

def estrai_link_standard(html, fonte):

    risultati = []
    visti = set()

    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.I | re.S,
    )

    for href, contenuto in pattern.findall(html):

        titolo = pulisci_testo(
            contenuto
        )

        if len(titolo) < 10:
            continue

        if anno_vecchio(titolo):
            continue

        if documento_escluso(titolo):
            continue

        if not territorio_valido(titolo):
            continue

        url = urljoin(
            fonte["url"],
            html_lib.unescape(href),
        )

        if not dominio_valido(
            url,
            fonte,
        ):
            continue

        t = normalizza(titolo)

        interessante = any(
            x in t
            for x in (
                "bando",
                "avviso",
                "voucher",
                "contribut",
            )
        )

        if not interessante:
            continue

        chiave = (
            t,
            url.rstrip("/"),
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
# GAL PICENO
# ============================================================

def estrai_link_gal(html, fonte):

    """
    Primo livello:
    individua pagine INTERVENTO SRG/SRD.

    Secondo livello:
    entra nella pagina intervento e cerca
    Bando / Avviso / documenti principali.
    """

    risultati = []
    visti = set()

    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.I | re.S,
    )

    pagine_intervento = []

    for href, contenuto in pattern.findall(html):

        titolo = pulisci_testo(
            contenuto
        )

        t = normalizza(titolo)

        url = urljoin(
            fonte["url"],
            html_lib.unescape(href),
        )

        if not dominio_valido(
            url,
            fonte,
        ):
            continue

        if any(
            codice in t
            for codice in (
                "srg",
                "srd",
                "srh",
            )
        ):

            pagine_intervento.append(
                {
                    "titolo": titolo,
                    "url": url,
                }
            )

    # Deduplica pagine intervento
    pagine_uniche = []

    urls_viste = set()

    for pagina in pagine_intervento:

        url = pagina["url"].rstrip("/")

        if url in urls_viste:
            continue

        urls_viste.add(url)
        pagine_uniche.append(pagina)

    # Secondo livello
    for intervento in pagine_uniche[:20]:

        try:

            html_intervento = scarica(
                intervento["url"]
            )

        except Exception as e:

            print(
                "  GAL: impossibile aprire "
                f"{intervento['titolo']} ({e})"
            )

            continue

        trovati_interni = 0

        for href, contenuto in pattern.findall(
            html_intervento
        ):

            titolo = pulisci_testo(
                contenuto
            )

            t = normalizza(titolo)

            if len(t) < 8:
                continue

            if documento_escluso(titolo):
                continue

            if anno_vecchio(titolo):
                continue

            interessante = (
                "bando" in t
                or "avviso" in t
            )

            if not interessante:
                continue

            url = urljoin(
                intervento["url"],
                html_lib.unescape(href),
            )

            if not dominio_valido(
                url,
                fonte,
            ):
                continue

            chiave = (
                t,
                url.rstrip("/"),
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

            trovati_interni += 1

        # Se non troviamo un vero link Bando,
        # conserviamo la pagina intervento
        # come candidato da verificare.
        if trovati_interni == 0:

            titolo = intervento["titolo"]
            url = intervento["url"]

            chiave = (
                normalizza(titolo),
                url.rstrip("/"),
            )

            if chiave not in visti:

                visti.add(chiave)

                risultati.append(
                    {
                        "titolo": titolo,
                        "url": url,
                    }
                )

    return risultati


def estrai_link(html, fonte):

    if fonte["tipo"] == "gal_piceno":

        return estrai_link_gal(
            html,
            fonte,
        )

    return estrai_link_standard(
        html,
        fonte,
    )


# ============================================================
# ID
# ============================================================

def genera_id(ente, titolo):

    valore = (
        ente.lower()
        + "|"
        + normalizza(titolo)
    )

    return hashlib.sha256(
        valore.encode("utf-8")
    ).hexdigest()[:16]


# ============================================================
# ANALISI
# ============================================================

def analizza(link, fonte):

    titolo = link["titolo"]
    url = link["url"]

    print(
        f"Analizzo: {titolo}"
    )

    try:

        html = scarica(url)

    except Exception as e:

        print(
            f"  DA VERIFICARE: errore lettura ({e})"
        )

        return {
            "esito": "DA_VERIFICARE"
        }

    contesto = estrai_contesto(
        titolo,
        html,
    )

    if not territorio_valido(
        titolo
    ):

        print(
            "  ESCLUSO: territorio"
        )

        return {
            "esito": "ESCLUSO"
        }

    beneficiario = classifica_beneficiario(
        titolo,
        contesto,
    )

    if not pubblicabile(
        beneficiario
    ):

        print(
            "  ESCLUSO: beneficiario "
            f"{beneficiario}"
        )

        return {
            "esito": "ESCLUSO"
        }

    scadenza = estrai_scadenza(
        contesto
    )

    stato = verifica_stato(
        contesto,
        scadenza,
    )

    if stato == "SCADUTO":

        print(
            "  SCADUTO/CHIUSO"
        )

        return {
            "esito": "SCADUTO",
            "titolo": titolo,
            "url": url,
        }

    if stato == "DA_VERIFICARE":

        print(
            "  DA VERIFICARE: "
            "apertura non certa"
        )

        return {
            "esito": "DA_VERIFICARE",
            "titolo": titolo,
            "url": url,
        }

    print(
        "  PUBBLICABILE: "
        f"{beneficiario} | "
        f"{scadenza or 'apertura esplicita'}"
    )

    return {
        "esito": "PUBBLICABILE",
        "bando": {
            "id": genera_id(
                fonte["nome"],
                titolo,
            ),
            "nome": titolo,
            "ente": fonte["nome"],
            "stato": "APERTO",
            "scadenza": scadenza,
            "scadenzaTesto": formatta_data(
                scadenza
            ),
            "profili": profili(
                beneficiario
            ),
            "settori": settori(
                titolo + " " + contesto
            ),
            "beneficiarioTipo": beneficiario,
            "descrizione": (
                "Opportunità verificata automaticamente "
                "da BandiAP su fonte ufficiale."
            ),
            "requisiti": (
                "Consultare la fonte ufficiale "
                "per requisiti e spese ammissibili."
            ),
            "dotazione":
                "Verificare sulla fonte ufficiale",
            "territorio":
                fonte["territorio"],
            "url": url,
            "fonteAutomatica": True,
            "versioneMotore": 9.1,
            "ultimoControllo":
                OGGI.strftime("%Y-%m-%d"),
        },
    }


# ============================================================
# PULIZIA V9 PRECEDENTE
# ============================================================

def prepara_database(database):

    """
    V9 non aveva pubblicato nuovi record.
    Manteniamo:
    - record manuali
    - eventuali record già V9.1

    Eliminiamo eventuali automatici
    delle versioni precedenti.
    """

    risultato = []
    eliminati = 0

    for bando in database:

        if (
            bando.get("fonteAutomatica") is True
            and bando.get("versioneMotore") != 9.1
        ):

            eliminati += 1
            continue

        risultato.append(
            bando
        )

    return risultato, eliminati


# ============================================================
# DUPLICATI / AGGIORNAMENTO
# ============================================================

def trova_esistente(database, nuovo):

    url_n = (
        nuovo.get("url", "")
        .rstrip("/")
        .lower()
    )

    nome_n = normalizza(
        nuovo.get("nome", "")
    )

    for bando in database:

        url = (
            bando.get("url", "")
            .rstrip("/")
            .lower()
        )

        nome = normalizza(
            bando.get("nome", "")
        )

        if (
            url_n
            and url
            and url_n == url
        ):
            return bando

        if (
            nome_n
            and nome
            and nome_n == nome
        ):
            return bando

    return None


def inserisci_o_aggiorna(
    database,
    nuovo,
):

    esistente = trova_esistente(
        database,
        nuovo,
    )

    if esistente is None:

        database.append(
            nuovo
        )

        return "NUOVO"

    modificato = False

    campi = (
        "stato",
        "scadenza",
        "scadenzaTesto",
        "profili",
        "settori",
        "beneficiarioTipo",
        "territorio",
        "url",
    )

    for campo in campi:

        if (
            esistente.get(campo)
            != nuovo.get(campo)
        ):

            esistente[campo] = (
                nuovo.get(campo)
            )

            modificato = True

    if esistente.get(
        "fonteAutomatica"
    ) is True:

        esistente["versioneMotore"] = 9.1

    esistente["ultimoControllo"] = (
        OGGI.strftime("%Y-%m-%d")
    )

    return (
        "AGGIORNATO"
        if modificato
        else "INVARIATO"
    )


# ============================================================
# RICONTROLLO AUTOMATICI
# ============================================================

def ricontrolla_esistenti(database):

    chiusi = 0

    for bando in database:

        if not (
            bando.get("fonteAutomatica") is True
            and bando.get("versioneMotore") == 9.1
        ):
            continue

        url = bando.get("url")

        if not url:
            continue

        try:

            html = scarica(url)

        except Exception:
            continue

        contesto = estrai_contesto(
            bando.get("nome", ""),
            html,
        )

        scadenza = estrai_scadenza(
            contesto
        )

        stato = verifica_stato(
            contesto,
            scadenza,
        )

        if (
            stato == "SCADUTO"
            and bando.get("stato") != "SCADUTO"
        ):

            bando["stato"] = "SCADUTO"

            chiusi += 1

            print(
                "CHIUSO: "
                f"{bando.get('nome')}"
            )

        elif stato == "APERTO":

            bando["stato"] = "APERTO"

            if scadenza:

                bando["scadenza"] = scadenza
                bando["scadenzaTesto"] = (
                    formatta_data(scadenza)
                )

        bando["ultimoControllo"] = (
            OGGI.strftime("%Y-%m-%d")
        )

    return chiusi


# ============================================================
# CONTROLLO FONTE
# ============================================================

def controlla_fonte(fonte):

    print()
    print("=" * 60)
    print(
        f"Controllo: {fonte['nome']}"
    )
    print(
        fonte["url"]
    )

    try:

        html = scarica(
            fonte["url"]
        )

    except Exception as e:

        print(
            f"ERRORE FONTE: {e}"
        )

        return []

    links = estrai_link(
        html,
        fonte,
    )

    print(
        f"Candidati V9.1: {len(links)}"
    )

    risultati = []

    for link in links[:50]:

        risultati.append(
            analizza(
                link,
                fonte,
            )
        )

    return risultati


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        "BandiAP - aggiornamento automatico V9.1"
    )
    print("=" * 60)

    database = carica_database()

    print(
        f"Record iniziali: {len(database)}"
    )

    database, eliminati = (
        prepara_database(database)
    )

    print(
        "Automatici precedenti eliminati: "
        f"{eliminati}"
    )

    print(
        "Record preservati: "
        f"{len(database)}"
    )

    chiusi = ricontrolla_esistenti(
        database
    )

    risultati = []

    for fonte in FONTI:

        risultati.extend(
            controlla_fonte(fonte)
        )

    nuovi = 0
    aggiornati = 0
    invariati = 0
    verificare = 0
    esclusi = 0
    scaduti = 0

    for risultato in risultati:

        esito = risultato.get(
            "esito"
        )

        if esito == "PUBBLICABILE":

            operazione = inserisci_o_aggiorna(
                database,
                risultato["bando"],
            )

            if operazione == "NUOVO":

                nuovi += 1

                print(
                    "NUOVO PUBBLICATO: "
                    f"{risultato['bando']['nome']}"
                )

            elif operazione == "AGGIORNATO":
                aggiornati += 1

            else:
                invariati += 1

        elif esito == "DA_VERIFICARE":
            verificare += 1

        elif esito == "ESCLUSO":
            esclusi += 1

        elif esito == "SCADUTO":
            scaduti += 1

    database.sort(
        key=lambda b: (
            b.get("stato") == "SCADUTO",
            b.get("scadenza")
            or "9999-12-31",
            b.get("nome", "").lower(),
        )
    )

    salva_database(
        database
    )

    print()
    print("=" * 60)
    print("RIEPILOGO V9.1")
    print("=" * 60)

    print(
        f"Automatici vecchi eliminati: {eliminati}"
    )

    print(
        f"NUOVI PUBBLICATI: {nuovi}"
    )

    print(
        f"AGGIORNATI: {aggiornati}"
    )

    print(
        f"INVARIATI: {invariati}"
    )

    print(
        f"CHIUSI: {chiusi}"
    )

    print(
        f"SCADUTI NON PUBBLICATI: {scaduti}"
    )

    print(
        f"DA VERIFICARE: {verificare}"
    )

    print(
        f"ESCLUSI: {esclusi}"
    )

    print(
        f"TOTALE DATABASE: {len(database)}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
