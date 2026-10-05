import json
import re
import html as html_lib
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse, parse_qs


# ============================================================
# BandiAP - Motore automatico bandi
# VERSIONE 10
# ============================================================

VERSIONE = 10

BASE_DIR = Path(__file__).resolve().parent
BANDI_FILE = BASE_DIR / "bandi.json"

OGGI = datetime.now().date()
ANNO = OGGI.year


REGIONE_URL = (
    "https://www.regione.marche.it/"
    "Entra-in-Regione/Bandi-e-opportunita/Bandi-attivi"
)

CAMERA_URL = (
    "https://www.marche.camcom.it/"
    "fai-crescere-la-tua-impresa/bandi-e-contributi"
)

GAL_URL = "https://galpiceno.it/bandi/"


# ============================================================
# TESTO
# ============================================================

def pulisci_html(testo):

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

    testo = pulisci_html(testo).lower()

    sostituzioni = {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
        "’": "'",
    }

    for a, b in sostituzioni.items():
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
# DOWNLOAD
# ============================================================

def scarica(url):

    req = Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 (compatible; BandiAP/10.0)",
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

        print(f"Errore database: {e}")

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
# DATE
# ============================================================

MESI = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}


def converti_data(testo):

    if not testo:
        return ""

    testo = testo.strip().lower()

    # gg/mm/aaaa
    match = re.search(
        r"([0-3]?\d)[/-]([01]?\d)[/-](20\d{2})",
        testo,
    )

    if match:

        try:

            d = datetime(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1)),
            ).date()

            return d.isoformat()

        except ValueError:
            pass

    # gg mese aaaa
    pattern_mesi = (
        r"([0-3]?\d)\s+("
        + "|".join(MESI.keys())
        + r")\s+(20\d{2})"
    )

    match = re.search(
        pattern_mesi,
        testo,
        flags=re.I,
    )

    if match:

        try:

            d = datetime(
                int(match.group(3)),
                MESI[match.group(2).lower()],
                int(match.group(1)),
            ).date()

            return d.isoformat()

        except ValueError:
            pass

    return ""


def data_obj(data):

    try:
        return datetime.strptime(
            data,
            "%Y-%m-%d",
        ).date()

    except Exception:
        return None


def formatta_data(data):

    d = data_obj(data)

    if not d:
        return "Verificare sulla fonte ufficiale"

    nomi = [
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
        f"{nomi[d.month]} "
        f"{d.year}"
    )


# ============================================================
# FINESTRE DI PRESENTAZIONE
# ============================================================

def estrai_finestre(testo):

    """
    Cerca intervalli tipo:

    dal 16/09/2026 al 16/10/2026
    dal 01/09/2027 al 30/09/2027
    """

    risultati = []

    pattern = re.compile(
        r"(?:dal|d\s*al)\s*"
        r"([0-3]?\d[/-][01]?\d[/-]20\d{2})"
        r".{0,80}?"
        r"(?:al|fino al)\s*"
        r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",
        flags=re.I,
    )

    for inizio, fine in pattern.findall(testo):

        data_inizio = converti_data(inizio)
        data_fine = converti_data(fine)

        if data_inizio and data_fine:

            risultati.append(
                (
                    data_inizio,
                    data_fine,
                )
            )

    return risultati


def finestra_attuale(testo):

    finestre = estrai_finestre(testo)

    for inizio, fine in finestre:

        di = data_obj(inizio)
        df = data_obj(fine)

        if (
            di
            and df
            and di <= OGGI <= df
        ):
            return {
                "stato": "APERTO",
                "scadenza": fine,
                "prossimaApertura": "",
            }

    # Nessuna finestra attuale.
    # Cerchiamo la prossima.
    future = []

    for inizio, fine in finestre:

        di = data_obj(inizio)

        if di and di > OGGI:
            future.append(
                (inizio, fine)
            )

    if future:

        future.sort()

        return {
            "stato": "PROGRAMMATO",
            "scadenza": future[0][1],
            "prossimaApertura": future[0][0],
        }

    return None


# ============================================================
# CHIUSURE / SOSPENSIONI
# ============================================================

def chiusura_esplicita(testo):

    t = normalizza(testo)

    frasi = (
        "chiusura anticipata",
        "sportello chiuso",
        "bando chiuso",
        "avviso chiuso",
        "domande chiuse",
        "termini chiusi",
        "risorse terminate",
        "risorse esaurite",
        "fondi esauriti",
        "esaurimento delle risorse",
        "sospesa la possibilita di inviare nuove domande",
        "sospesa la presentazione delle domande",
        "non e piu possibile presentare",
    )

    return any(
        frase in t
        for frase in frasi
    )


# ============================================================
# CLASSIFICAZIONE BENEFICIARIO
# ============================================================

def classifica_beneficiario(
    titolo,
    beneficiari,
    note="",
):

    t = normalizza(
        titolo
        + " "
        + beneficiari
        + " "
        + note[:3000]
    )

    # ENTI PUBBLICI
    if any(
        x in t
        for x in (
            "beneficiari comuni",
            "contributi ai comuni",
            "contributo ai comuni",
            "comuni non capoluogo",
            "unioni di comuni",
            "egato",
            "enti locali",
        )
    ):
        return "ENTE_PUBBLICO"

    # NUOVE IMPRESE
    if any(
        x in t
        for x in (
            "creazione di nuove imprese",
            "creazione nuove imprese",
            "avvio di impresa",
            "avvio impresa",
            "nuova impresa",
            "nuove imprese",
            "startup",
            "start up",
        )
    ):
        return "NUOVA_IMPRESA"

    # AGRICOLTURA
    if any(
        x in t
        for x in (
            "imprenditori agricoli",
            "imprese agricole",
            "aziende agricole",
            "azienda agricola",
            "allevatori",
            "zootec",
        )
    ):
        return "AGRICOLTURA"

    # PROFESSIONISTI
    if any(
        x in t
        for x in (
            "liberi professionisti",
            "libero professionista",
            "lavoratori autonomi",
        )
    ):
        return "PROFESSIONISTA"

    # ETS
    if any(
        x in t
        for x in (
            "enti del terzo settore",
            "organizzazioni di volontariato",
            "associazioni di promozione sociale",
        )
    ):
        return "ASSOCIAZIONE_ETS"

    # INTERMEDIARI
    if any(
        x in t
        for x in (
            "portatori di interessi collettivi",
            "fondazioni its",
            "its academy",
        )
    ):
        return "INTERMEDIARIO_ORGANIZZAZIONE"

    # IMPRESE
    if any(
        x in t
        for x in (
            "micro piccole e medie imprese",
            "micro piccole medie imprese",
            "imprese attive",
            "imprese beneficiarie",
            "imprese marchigiane",
            "imprese della regione marche",
            "mpmi",
            "pmi",
            "operatori economici",
        )
    ):
        return "IMPRESA"

    # Titoli fortemente indicativi
    titolo_n = normalizza(titolo)

    if "internazionalizzazione" in titolo_n:
        return "IMPRESA"

    if "voucher" in titolo_n:
        return "IMPRESA"

    return "NON_DETERMINATO"


# ============================================================
# PUBBLICABILITÀ
# ============================================================

def pubblicabile(tipo):

    return tipo in (
        "IMPRESA",
        "NUOVA_IMPRESA",
        "PROFESSIONISTA",
        "AGRICOLTURA",
        "ASSOCIAZIONE_ETS",
    )


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

def classifica_settori(testo):

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
            "ospitalita",
        ),
        "agricoltura": (
            "agricol",
            "zootec",
            "allevator",
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
            risultato.append(settore)

    return risultato or ["altro"]


# ============================================================
# ID
# ============================================================

def genera_id(fonte, chiave):

    valore = (
        normalizza(fonte)
        + "|"
        + normalizza(str(chiave))
    )

    return hashlib.sha256(
        valore.encode("utf-8")
    ).hexdigest()[:16]


# ============================================================
# REGIONE MARCHE
# ============================================================

def estrai_id_regione(html):

    ids = set()

    # idb=12345
    for valore in re.findall(
        r"[?&]idb=(\d+)",
        html,
        flags=re.I,
    ):

        ids.add(valore)

    return sorted(ids)


def campo_regione(testo, nome, prossimo=None):

    """
    Estrae campi dalla scheda Regione convertita in testo.
    """

    if prossimo:

        pattern = (
            re.escape(nome)
            + r"\s*:\s*(.*?)\s*"
            + re.escape(prossimo)
            + r"\s*:"
        )

    else:

        pattern = (
            re.escape(nome)
            + r"\s*:\s*(.*)"
        )

    match = re.search(
        pattern,
        testo,
        flags=re.I | re.S,
    )

    if match:
        return match.group(1).strip()

    return ""


def analizza_regione_id(idb):

    url = (
        REGIONE_URL
        + "?idb="
        + str(idb)
    )

    try:
        html = scarica(url)

    except Exception as e:

        print(
            f"  ERRORE Regione ID {idb}: {e}"
        )
        return None

    testo = pulisci_html(html)

    # Titolo: prendiamo il primo heading utile dopo Titolo
    match_titolo = re.search(
        r"Titolo\s*:\s*(.*?)"
        r"(?:Area organizzativa|Struttura)\s*:",
        testo,
        flags=re.I | re.S,
    )

    if not match_titolo:
        return None

    titolo = match_titolo.group(1).strip()

    # Elimina eventuali rumori
    titolo = re.sub(
        r"^[-|:\s]+",
        "",
        titolo,
    ).strip()

    if not titolo:
        return None

    beneficiari = campo_regione(
        testo,
        "Soggetti ammessi beneficiari",
        "Note",
    )

    note = campo_regione(
        testo,
        "Note",
        "Allegati",
    )

    # Scadenza nominale
    match_scadenza = re.search(
        r"Scadenza\s*:\s*(.*?)"
        r"(?:Contatto|Email contatto)\s*:",
        testo,
        flags=re.I | re.S,
    )

    scadenza_nominale = ""

    if match_scadenza:

        scadenza_nominale = converti_data(
            match_scadenza.group(1)
        )

    # ----------------------------------------
    # 1. CHIUSURA / SOSPENSIONE
    # ----------------------------------------

    if chiusura_esplicita(note):

        return {
            "esito": "CHIUSO",
            "titolo": titolo,
            "url": url,
        }

    # ----------------------------------------
    # 2. FINESTRE SPECIFICHE
    # ----------------------------------------

    finestra = finestra_attuale(note)

    if finestra:

        if finestra["stato"] == "PROGRAMMATO":

            return {
                "esito": "PROGRAMMATO",
                "titolo": titolo,
                "url": url,
                "prossimaApertura":
                    finestra["prossimaApertura"],
            }

        scadenza_effettiva = (
            finestra["scadenza"]
        )

    else:

        scadenza_effettiva = (
            scadenza_nominale
        )

    # ----------------------------------------
    # 3. SCADENZA
    # ----------------------------------------

    d = data_obj(
        scadenza_effettiva
    )

    if not d:

        return {
            "esito": "DA_VERIFICARE",
            "titolo": titolo,
            "url": url,
        }

    if d < OGGI:

        return {
            "esito": "CHIUSO",
            "titolo": titolo,
            "url": url,
        }

    # ----------------------------------------
    # 4. BENEFICIARIO
    # ----------------------------------------

    categoria = classifica_beneficiario(
        titolo,
        beneficiari,
        note,
    )

    if not pubblicabile(categoria):

        return {
            "esito": "ESCLUSO",
            "titolo": titolo,
            "categoria": categoria,
            "url": url,
        }

    # ----------------------------------------
    # PUBBLICABILE
    # ----------------------------------------

    return {
        "esito": "PUBBLICABILE",
        "bando": {
            "id": genera_id(
                "Regione Marche",
                idb,
            ),
            "idFonte": str(idb),
            "nome": titolo,
            "ente": "Regione Marche",
            "stato": "APERTO",
            "scadenza": scadenza_effettiva,
            "scadenzaTesto": formatta_data(
                scadenza_effettiva
            ),
            "profili": profili(categoria),
            "settori": classifica_settori(
                titolo
                + " "
                + beneficiari
                + " "
                + note
            ),
            "beneficiarioTipo": categoria,
            "beneficiari": beneficiari,
            "descrizione": (
                "Bando presente nella fonte "
                "ufficiale Regione Marche."
            ),
            "requisiti": beneficiari or (
                "Consultare la fonte ufficiale."
            ),
            "dotazione":
                "Verificare sulla fonte ufficiale",
            "territorio": "Regione Marche",
            "url": url,
            "fonteAutomatica": True,
            "versioneMotore": VERSIONE,
            "ultimoControllo":
                OGGI.isoformat(),
        },
    }


def controlla_regione():

    print()
    print("=" * 60)
    print("REGIONE MARCHE")
    print("=" * 60)

    risultati = []

    # La pagina è paginata.
    # Controlliamo più pagine.
    urls = [REGIONE_URL]

    for pagina in range(2, 8):

        urls.append(
            f"{REGIONE_URL}/p/{pagina}"
        )

    ids = set()

    for url in urls:

        try:

            html = scarica(url)

            ids.update(
                estrai_id_regione(html)
            )

        except Exception as e:

            print(
                f"Errore pagina Regione {url}: {e}"
            )

    print(
        f"ID Regione trovati: {len(ids)}"
    )

    for idb in sorted(ids):

        risultato = analizza_regione_id(
            idb
        )

        if not risultato:
            continue

        esito = risultato["esito"]

        titolo = (
            risultato.get("titolo")
            or risultato.get(
                "bando", {}
            ).get("nome", "")
        )

        print(
            f"[{idb}] {esito}: {titolo}"
        )

        risultati.append(
            risultato
        )

    return risultati


# ============================================================
# CAMERA DI COMMERCIO
# ============================================================

def estrai_link_camera(html):

    risultati = []
    visti = set()

    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)</a>',
        flags=re.I | re.S,
    )

    for href, contenuto in pattern.findall(html):

        titolo = pulisci_html(
            contenuto
        )

        t = normalizza(titolo)

        if len(t) < 10:
            continue

        if not any(
            parola in t
            for parola in (
                "bando",
                "avviso",
                "voucher",
            )
        ):
            continue

        # vecchie annualità
        anni = re.findall(
            r"\b20\d{2}\b",
            t,
        )

        if anni:

            anni_recenti = [
                int(x)
                for x in anni
                if int(x) >= 2022
            ]

            if (
                anni_recenti
                and max(anni_recenti) < ANNO
            ):
                continue

        url = urljoin(
            CAMERA_URL,
            html_lib.unescape(href),
        )

        dominio = urlparse(
            url
        ).netloc.lower()

        if "marche.camcom.it" not in dominio:
            continue

        # niente documenti
        if url.lower().split("?")[0].endswith(
            (
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
            )
        ):
            continue

        chiave = url.rstrip("/")

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


def analizza_camera(link):

    titolo = link["titolo"]
    url = link["url"]

    try:
        html = scarica(url)

    except Exception:

        return {
            "esito": "DA_VERIFICARE",
            "titolo": titolo,
            "url": url,
        }

    testo = pulisci_html(html)

    # Chiusura anticipata prevale su tutto
    if chiusura_esplicita(testo):

        return {
            "esito": "CHIUSO",
            "titolo": titolo,
            "url": url,
        }

    # Campo Camera:
    # Scadenza termini partecipazione
    match = re.search(
        r"Scadenza termini partecipazione\s*:\s*"
        r"(.{0,100})",
        testo,
        flags=re.I,
    )

    scadenza = ""

    if match:
        scadenza = converti_data(
            match.group(1)
        )

    # Altre formulazioni
    if not scadenza:

        patterns = (
            r"entro il\s+"
            r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",

            r"entro il\s+"
            r"([0-3]?\d\s+[a-zàèéìòù]+\s+20\d{2})",

            r"fino al\s+"
            r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",
        )

        for pattern in patterns:

            m = re.search(
                pattern,
                testo,
                flags=re.I,
            )

            if m:

                scadenza = converti_data(
                    m.group(1)
                )

                if scadenza:
                    break

    d = data_obj(scadenza)

    if not d:

        return {
            "esito": "DA_VERIFICARE",
            "titolo": titolo,
            "url": url,
        }

    if d < OGGI:

        return {
            "esito": "CHIUSO",
            "titolo": titolo,
            "url": url,
        }

    categoria = classifica_beneficiario(
        titolo,
        testo[:5000],
        "",
    )

    if not pubblicabile(categoria):

        return {
            "esito": "ESCLUSO",
            "titolo": titolo,
            "categoria": categoria,
            "url": url,
        }

    return {
        "esito": "PUBBLICABILE",
        "bando": {
            "id": genera_id(
                "Camera Marche",
                url,
            ),
            "nome": titolo,
            "ente":
                "Camera di Commercio delle Marche",
            "stato": "APERTO",
            "scadenza": scadenza,
            "scadenzaTesto":
                formatta_data(scadenza),
            "profili": profili(categoria),
            "settori":
                classifica_settori(
                    titolo + " " + testo[:5000]
                ),
            "beneficiarioTipo": categoria,
            "descrizione": (
                "Opportunità verificata sulla "
                "fonte ufficiale della Camera "
                "di Commercio delle Marche."
            ),
            "requisiti":
                "Consultare la fonte ufficiale.",
            "dotazione":
                "Verificare sulla fonte ufficiale",
            "territorio": "Regione Marche",
            "url": url,
            "fonteAutomatica": True,
            "versioneMotore": VERSIONE,
            "ultimoControllo":
                OGGI.isoformat(),
        },
    }


def controlla_camera():

    print()
    print("=" * 60)
    print("CAMERA DI COMMERCIO")
    print("=" * 60)

    try:
        html = scarica(CAMERA_URL)

    except Exception as e:

        print(f"Errore Camera: {e}")
        return []

    links = estrai_link_camera(html)

    print(
        f"Candidati Camera: {len(links)}"
    )

    risultati = []

    for link in links:

        risultato = analizza_camera(
            link
        )

        titolo = (
            risultato.get("titolo")
            or risultato.get(
                "bando", {}
            ).get("nome", "")
        )

        print(
            f"{risultato['esito']}: {titolo}"
        )

        risultati.append(
            risultato
        )

    return risultati


# ============================================================
# GAL PICENO
# ============================================================

def controlla_gal():

    print()
    print("=" * 60)
    print("GAL PICENO")
    print("=" * 60)

    try:
        html = scarica(GAL_URL)

    except Exception as e:

        print(f"Errore GAL: {e}")
        return []

    testo = pulisci_html(html)

    risultati = []

    # Cerchiamo blocchi SRG/SRD attuali.
    pattern_link = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)</a>',
        flags=re.I | re.S,
    )

    visti = set()

    for href, contenuto in pattern_link.findall(
        html
    ):

        titolo = pulisci_html(
            contenuto
        )

        t = normalizza(titolo)

        if not any(
            codice in t
            for codice in (
                "srg",
                "srd",
                "srh",
            )
        ):
            continue

        if not any(
            parola in t
            for parola in (
                "bando",
                "intervento",
            )
        ):
            continue

        url = urljoin(
            GAL_URL,
            html_lib.unescape(href),
        )

        if "galpiceno.it" not in urlparse(
            url
        ).netloc.lower():
            continue

        chiave = url.rstrip("/")

        if chiave in visti:
            continue

        visti.add(chiave)

        try:
            dettaglio_html = scarica(url)

        except Exception:
            continue

        dettaglio = pulisci_html(
            dettaglio_html
        )

        # Cerca scadenze nel contesto
        scadenze = []

        patterns = (
            r"scadenza.{0,100}?"
            r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",

            r"scadenza.{0,100}?"
            r"([0-3]?\d\s+[a-zàèéìòù]+\s+20\d{2})",

            r"entro.{0,100}?"
            r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",

            r"entro.{0,100}?"
            r"([0-3]?\d\s+[a-zàèéìòù]+\s+20\d{2})",
        )

        for pattern in patterns:

            for valore in re.findall(
                pattern,
                dettaglio,
                flags=re.I,
            ):

                data = converti_data(
                    valore
                )

                if data:
                    scadenze.append(data)

        # Preferiamo la prima scadenza futura
        scadenze_future = sorted(
            {
                d
                for d in scadenze
                if data_obj(d)
                and data_obj(d) >= OGGI
            }
        )

        if not scadenze_future:

            risultati.append(
                {
                    "esito": "DA_VERIFICARE",
                    "titolo": titolo,
                    "url": url,
                }
            )

            print(
                f"DA_VERIFICARE: {titolo}"
            )

            continue

        scadenza = scadenze_future[0]

        if chiusura_esplicita(
            dettaglio
        ):

            risultati.append(
                {
                    "esito": "CHIUSO",
                    "titolo": titolo,
                    "url": url,
                }
            )

            print(
                f"CHIUSO: {titolo}"
            )

            continue

        categoria = classifica_beneficiario(
            titolo,
            dettaglio[:7000],
            "",
        )

        # GAL: PPP/aggregazioni sono utili a BandiAP
        # anche se il beneficiario non è una singola impresa.
        if (
            categoria == "NON_DETERMINATO"
            and any(
                x in normalizza(dettaglio[:7000])
                for x in (
                    "partenariato pubblico privato",
                    "aggregazioni",
                    "operatori privati",
                    "imprese",
                )
            )
        ):
            categoria = (
                "INTERMEDIARIO_ORGANIZZAZIONE"
            )

        # Manteniamo GAL rilevanti anche come
        # opportunità territoriale.
        ammesso_gal = (
            pubblicabile(categoria)
            or categoria
            == "INTERMEDIARIO_ORGANIZZAZIONE"
        )

        if not ammesso_gal:

            risultati.append(
                {
                    "esito": "ESCLUSO",
                    "titolo": titolo,
                    "url": url,
                }
            )

            print(
                f"ESCLUSO: {titolo}"
            )

            continue

        bando = {
            "id": genera_id(
                "GAL Piceno",
                url,
            ),
            "nome": titolo,
            "ente": "GAL Piceno",
            "stato": "APERTO",
            "scadenza": scadenza,
            "scadenzaTesto":
                formatta_data(scadenza),
            "profili": (
                profili(categoria)
                if pubblicabile(categoria)
                else ["altro"]
            ),
            "settori":
                classifica_settori(
                    titolo
                    + " "
                    + dettaglio[:7000]
                ),
            "beneficiarioTipo": categoria,
            "descrizione": (
                "Opportunità territoriale "
                "del GAL Piceno."
            ),
            "requisiti": (
                "Consultare il bando ufficiale "
                "GAL Piceno."
            ),
            "dotazione":
                "Verificare sulla fonte ufficiale",
            "territorio": "GAL Piceno",
            "url": url,
            "fonteAutomatica": True,
            "versioneMotore": VERSIONE,
            "ultimoControllo":
                OGGI.isoformat(),
        }

        risultati.append(
            {
                "esito": "PUBBLICABILE",
                "bando": bando,
            }
        )

        print(
            f"PUBBLICABILE: {titolo} "
            f"-> {scadenza}"
        )

    return risultati


# ============================================================
# DATABASE V10
# ============================================================

def prepara_database(database):

    """
    Prima esecuzione V10:
    conserva i record manuali.

    Elimina eventuali automatici prodotti
    dalle vecchie versioni.

    Dalla seconda esecuzione i record V10
    vengono mantenuti e aggiornati.
    """

    risultato = []
    eliminati = 0

    for bando in database:

        automatico = (
            bando.get("fonteAutomatica")
            is True
        )

        versione = bando.get(
            "versioneMotore"
        )

        if (
            automatico
            and versione != VERSIONE
        ):

            eliminati += 1
            continue

        risultato.append(
            bando
        )

    return risultato, eliminati


def trova_esistente(
    database,
    nuovo,
):

    nuovo_id = nuovo.get("id")

    nuovo_url = (
        nuovo.get("url", "")
        .rstrip("/")
        .lower()
    )

    nuovo_nome = normalizza(
        nuovo.get("nome", "")
    )

    for bando in database:

        if (
            nuovo_id
            and bando.get("id") == nuovo_id
        ):
            return bando

        url = (
            bando.get("url", "")
            .rstrip("/")
            .lower()
        )

        if (
            nuovo_url
            and url
            and nuovo_url == url
        ):
            return bando

        nome = normalizza(
            bando.get("nome", "")
        )

        if (
            nuovo_nome
            and nome
            and nuovo_nome == nome
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

        database.append(nuovo)
        return "NUOVO"

    modificato = False

    campi = (
        "nome",
        "ente",
        "stato",
        "scadenza",
        "scadenzaTesto",
        "profili",
        "settori",
        "beneficiarioTipo",
        "beneficiari",
        "descrizione",
        "requisiti",
        "dotazione",
        "territorio",
        "url",
    )

    for campo in campi:

        if campo not in nuovo:
            continue

        if (
            esistente.get(campo)
            != nuovo.get(campo)
        ):

            esistente[campo] = (
                nuovo.get(campo)
            )

            modificato = True

    if (
        esistente.get("fonteAutomatica")
        is True
    ):

        esistente["versioneMotore"] = (
            VERSIONE
        )

    esistente["ultimoControllo"] = (
        OGGI.isoformat()
    )

    if modificato:
        return "AGGIORNATO"

    return "INVARIATO"


# ============================================================
# DEDUPLICAZIONE GAL / REGIONE
# ============================================================

def probabile_duplicato(
    database,
    nuovo,
):

    nome_n = normalizza(
        nuovo.get("nome", "")
    )

    # Codici SRG/SRD/SRH
    codici = re.findall(
        r"\b(sr[gdhe]\d{2})\b",
        nome_n,
    )

    if not codici:
        return None

    for bando in database:

        nome = normalizza(
            bando.get("nome", "")
        )

        if any(
            codice in nome
            for codice in codici
        ):

            # Regione prevale come record principale
            if (
                bando.get("ente")
                == "Regione Marche"
            ):
                return bando

    return None


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        "BandiAP - aggiornamento automatico V10"
    )
    print("=" * 60)

    database = carica_database()

    print(
        f"Record iniziali: {len(database)}"
    )

    database, eliminati = prepara_database(
        database
    )

    print(
        "Automatici pre-V10 eliminati: "
        f"{eliminati}"
    )

    print(
        "Record preservati: "
        f"{len(database)}"
    )

    risultati = []

    # ----------------------------------------
    # TRE PARSER SEPARATI
    # ----------------------------------------

    risultati.extend(
        controlla_regione()
    )

    risultati.extend(
        controlla_camera()
    )

    risultati.extend(
        controlla_gal()
    )

    # ----------------------------------------
    # CONTATORI
    # ----------------------------------------

    nuovi = 0
    aggiornati = 0
    invariati = 0
    chiusi = 0
    programmati = 0
    verificare = 0
    esclusi = 0
    duplicati = 0

    # ----------------------------------------
    # RISULTATI
    # ----------------------------------------

    for risultato in risultati:

        esito = risultato.get(
            "esito"
        )

        if esito == "PUBBLICABILE":

            nuovo = risultato["bando"]

            # Prima deduplica normale
            esistente = trova_esistente(
                database,
                nuovo,
            )

            # Poi deduplica GAL / Regione
            if (
                esistente is None
                and nuovo.get("ente")
                == "GAL Piceno"
            ):

                duplicato = probabile_duplicato(
                    database,
                    nuovo,
                )

                if duplicato:

                    duplicati += 1

                    print(
                        "DUPLICATO GAL/REGIONE: "
                        f"{nuovo['nome']}"
                    )

                    continue

            operazione = inserisci_o_aggiorna(
                database,
                nuovo,
            )

            if operazione == "NUOVO":

                nuovi += 1

                print(
                    "NUOVO PUBBLICATO: "
                    f"{nuovo['nome']}"
                )

            elif operazione == "AGGIORNATO":

                aggiornati += 1

            else:

                invariati += 1

        elif esito == "CHIUSO":

            chiusi += 1

        elif esito == "PROGRAMMATO":

            programmati += 1

            print(
                "PROGRAMMATO: "
                f"{risultato.get('titolo')} "
                f"- prossima apertura "
                f"{risultato.get('prossimaApertura')}"
            )

        elif esito == "DA_VERIFICARE":

            verificare += 1

        elif esito == "ESCLUSO":

            esclusi += 1

    # ----------------------------------------
    # AGGIORNA STATO RECORD V10 NON PIÙ APERTI
    # ----------------------------------------

    pubblicati_ids = {
        r["bando"]["id"]
        for r in risultati
        if r.get("esito") == "PUBBLICABILE"
        and r.get("bando")
    }

    for bando in database:

        if not (
            bando.get("fonteAutomatica")
            is True
            and bando.get("versioneMotore")
            == VERSIONE
        ):
            continue

        if bando.get("id") not in pubblicati_ids:

            if bando.get("stato") == "APERTO":

                bando["stato"] = "SCADUTO"

                print(
                    "ARCHIVIATO: "
                    f"{bando.get('nome')}"
                )

    # ----------------------------------------
    # ORDINA
    # ----------------------------------------

    database.sort(
        key=lambda b: (
            b.get("stato") != "APERTO",
            b.get("scadenza")
            or "9999-12-31",
            b.get("nome", "").lower(),
        )
    )

    salva_database(database)

    # ----------------------------------------
    # RIEPILOGO
    # ----------------------------------------

    print()
    print("=" * 60)
    print("RIEPILOGO V10")
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
        f"CHIUSI/NON CANDIDABILI: {chiusi}"
    )

    print(
        f"PROGRAMMATI: {programmati}"
    )

    print(
        f"DA VERIFICARE: {verificare}"
    )

    print(
        f"ESCLUSI PER BENEFICIARIO: {esclusi}"
    )

    print(
        f"DUPLICATI GAL/REGIONE: {duplicati}"
    )

    print(
        f"TOTALE DATABASE: {len(database)}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
