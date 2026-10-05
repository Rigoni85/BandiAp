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
# Versione 9
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


# ============================================================
# PAROLE CHIAVE
# ============================================================

PAROLE_BANDO = (
    "bando",
    "avviso pubblico",
    "contribut",
    "voucher",
    "incentiv",
    "agevol",
    "finanziamento",
    "sostegno",
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


DOCUMENTI_ESCLUSI = (
    "manuale",
    "modulistica",
    "fac simile",
    "facsimile",
    "istruzioni",
    "informativa",
    "schema domanda",
    "modello domanda",
    "graduatoria",
    "liquidazione",
    "faq",
)


TITOLI_GENERICI = (
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


# ============================================================
# UTILITY TESTO
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

    testo = re.sub(
        r"\s+",
        " ",
        testo,
    )

    return testo.strip()


def normalizza(testo):

    testo = pulisci_testo(testo).lower()

    sostituzioni = {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
        "’": "'",
    }

    for vecchio, nuovo in sostituzioni.items():
        testo = testo.replace(
            vecchio,
            nuovo,
        )

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

        print(
            f"Database non trovato: {BANDI_FILE}"
        )

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

        if (
            isinstance(dati, dict)
            and isinstance(dati.get("bandi"), list)
        ):
            return dati["bandi"]

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

    richiesta = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; BandiAP/9.0)"
            ),
            "Accept-Language": (
                "it-IT,it;q=0.9"
            ),
        },
    )

    with urlopen(
        richiesta,
        timeout=30,
    ) as risposta:

        return risposta.read().decode(
            "utf-8",
            errors="ignore",
        )


# ============================================================
# DATE
# ============================================================

def converti_data(valore):

    if not valore:
        return ""

    for formato in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ):

        try:

            data = datetime.strptime(
                valore.strip(),
                formato,
            )

            return data.strftime(
                "%Y-%m-%d"
            )

        except ValueError:
            pass

    return ""


def estrai_scadenza(testo):

    testo_norm = normalizza(testo)

    patterns = (
        r"scadenza.{0,120}?([0-3]?\d/[01]?\d/20\d{2})",
        r"scadenza.{0,120}?([0-3]?\d-[01]?\d-20\d{2})",
        r"entro.{0,120}?([0-3]?\d/[01]?\d/20\d{2})",
        r"entro.{0,120}?([0-3]?\d-[01]?\d-20\d{2})",
        r"termine.{0,120}?([0-3]?\d/[01]?\d/20\d{2})",
        r"termine.{0,120}?([0-3]?\d-[01]?\d-20\d{2})",
        r"fino al.{0,120}?([0-3]?\d/[01]?\d/20\d{2})",
        r"fino al.{0,120}?([0-3]?\d-[01]?\d-20\d{2})",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            testo_norm,
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
# STATO DEL BANDO
# ============================================================

def verifica_stato(testo, scadenza):

    t = normalizza(testo)

    frasi_chiusura = (
        "bando chiuso",
        "avviso chiuso",
        "procedura chiusa",
        "sportello chiuso",
        "domande chiuse",
        "termini chiusi",
        "chiusura anticipata",
        "esaurimento risorse",
        "esaurimento delle risorse",
        "risorse esaurite",
        "fondi esauriti",
        "non e piu possibile presentare",
        "non e possibile presentare",
    )

    if any(
        frase in t
        for frase in frasi_chiusura
    ):
        return "SCADUTO"

    if scadenza:

        try:

            data = datetime.strptime(
                scadenza,
                "%Y-%m-%d",
            ).date()

            if data < OGGI:
                return "SCADUTO"

            return "APERTO"

        except ValueError:
            pass

    # Nessuna prova positiva sufficiente
    return "DA_VERIFICARE"


# ============================================================
# BENEFICIARI
# ============================================================

def classifica_beneficiario(testo):

    t = normalizza(testo)

    # Enti pubblici
    if any(
        x in t
        for x in (
            "contributi ai comuni",
            "contributo ai comuni",
            "comuni non capoluogo",
            "riservato ai comuni",
            "enti locali",
            "unioni di comuni",
            "pubbliche amministrazioni",
        )
    ):
        return "ENTE_PUBBLICO"

    # Intermediari / organismi
    if any(
        x in t
        for x in (
            "portatori di interessi collettivi",
            "fondazioni its",
            "its academy",
            "organismi non imprenditoriali",
        )
    ):
        return "INTERMEDIARIO_ORGANIZZAZIONE"

    # Nuove imprese
    if any(
        x in t
        for x in (
            "creazione di nuove imprese",
            "creazione nuove imprese",
            "nuova impresa",
            "nuove imprese",
            "avvio di impresa",
            "avvio impresa",
            "startup",
            "start up",
        )
    ):
        return "NUOVA_IMPRESA"

    # Professionisti
    if any(
        x in t
        for x in (
            "liberi professionisti",
            "libero professionista",
            "professionisti",
            "lavoratori autonomi",
        )
    ):
        return "PROFESSIONISTA"

    # Agricoltura
    if any(
        x in t
        for x in (
            "imprenditori agricoli",
            "imprese agricole",
            "azienda agricola",
            "aziende agricole",
            "allevatori",
            "zootecn",
        )
    ):
        return "AGRICOLTURA"

    # ETS / associazioni
    if any(
        x in t
        for x in (
            "enti del terzo settore",
            "terzo settore",
            "associazioni",
            "ets",
        )
    ):
        return "ASSOCIAZIONE_ETS"

    # Imprese
    if any(
        x in t
        for x in (
            "imprese",
            "impresa",
            "pmi",
            "mpmi",
            "microimprese",
            "micro imprese",
            "operatori economici",
        )
    ):
        return "IMPRESA"

    return "NON_DETERMINATO"


# ============================================================
# BENEFICIARI PUBBLICABILI
# ============================================================

def beneficiario_pubblicabile(tipo):

    return tipo in (
        "IMPRESA",
        "NUOVA_IMPRESA",
        "PROFESSIONISTA",
        "AGRICOLTURA",
        "ASSOCIAZIONE_ETS",
    )


# ============================================================
# SETTORI
# ============================================================

def classifica_settori(testo):

    t = normalizza(testo)

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
            settori.append(settore)

    if not settori:
        settori = ["altro"]

    return settori


def profili_da_beneficiario(tipo):

    mappa = {
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
    }

    return mappa.get(
        tipo,
        ["altro"],
    )


# ============================================================
# FILTRI TERRITORIALI
# ============================================================

def territorio_valido(testo):

    t = normalizza(testo)

    if any(
        gal in t
        for gal in GAL_ESCLUSI
    ):
        return False

    return True


# ============================================================
# FILTRI TITOLI
# ============================================================

def titolo_generico(titolo):

    t = normalizza(titolo)

    if not t:
        return True

    if len(t) < 10:
        return True

    if t in TITOLI_GENERICI:
        return True

    if re.fullmatch(
        r"(i|ii|iii|iv|v|vi|vii|viii|ix|x) pubblicazione.*",
        t,
    ):
        return True

    return False


def documento_accessorio(titolo, url):

    t = normalizza(titolo)

    if any(
        parola in t
        for parola in DOCUMENTI_ESCLUSI
    ):
        return True

    # Borse di studio ITS non sono
    # opportunità standard BandiAP imprese
    if (
        "bors" in t
        and "studio" in t
        and "its" in t
    ):
        return True

    if url.lower().split("?")[0].endswith(".pdf"):

        # PDF ammesso solo se il titolo indica
        # chiaramente il vero bando/avviso.
        if not (
            t.startswith("bando ")
            or t.startswith("avviso pubblico ")
        ):
            return True

    return False


def annualita_vecchia(titolo):

    anni = re.findall(
        r"\b(20\d{2})\b",
        titolo,
    )

    if not anni:
        return False

    anni = [
        int(x)
        for x in anni
    ]

    # Non usiamo date normative 2021/2115 ecc.
    # come prova che il bando sia vecchio.
    anni_recenti = [
        x
        for x in anni
        if x >= 2024
    ]

    if not anni_recenti:
        return False

    return max(anni_recenti) < ANNO


# ============================================================
# DOMINI
# ============================================================

def dominio_valido(url, fonte):

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
# LINK STANDARD
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

        url = urljoin(
            fonte["url"],
            html_lib.unescape(href),
        )

        if titolo_generico(titolo):
            continue

        if annualita_vecchia(titolo):
            continue

        if not territorio_valido(titolo):
            continue

        if not dominio_valido(
            url,
            fonte,
        ):
            continue

        if documento_accessorio(
            titolo,
            url,
        ):
            continue

        t = normalizza(titolo)

        if not any(
            parola in t
            for parola in PAROLE_BANDO
        ):
            continue

        chiave = (
            normalizza(titolo),
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
# LINK GAL PICENO
# ============================================================

def estrai_link_gal_piceno(html, fonte):

    """
    GAL Piceno richiede una logica meno rigida.

    Le pagine possono essere presentate come
    INTERVENTO SRGxx e il vero bando può essere
    raggiunto da link interni successivi.
    """

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

        url = urljoin(
            fonte["url"],
            html_lib.unescape(href),
        )

        if not dominio_valido(
            url,
            fonte,
        ):
            continue

        if documento_accessorio(
            titolo,
            url,
        ):
            continue

        t = normalizza(titolo)

        # Eliminiamo vecchie misure 19.x
        if (
            "misura 19" in t
            or "sottomisura 19" in t
        ):
            continue

        # Cerchiamo programmazione CSR 2023-2027
        # e interventi SRG/SRD attuali.
        interessante = (
            "bando" in t
            or "avviso" in t
            or "srg" in t
            or "srd" in t
            or "csr" in t
        )

        if not interessante:
            continue

        if annualita_vecchia(titolo):
            continue

        chiave = (
            normalizza(titolo),
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
# ESTRAZIONE LINK
# ============================================================

def estrai_link(html, fonte):

    if fonte["tipo"] == "gal_piceno":

        return estrai_link_gal_piceno(
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
        ente.lower().strip()
        + "|"
        + normalizza(titolo)
    )

    return hashlib.sha256(
        valore.encode("utf-8")
    ).hexdigest()[:16]


# ============================================================
# ANALISI CANDIDATO
# ============================================================

def analizza_candidato(link, fonte):

    titolo = link["titolo"]
    url = link["url"]

    print(
        f"Analizzo: {titolo}"
    )

    try:

        html = scarica(url)
        testo = pulisci_testo(html)

    except Exception as e:

        print(
            f"  DA VERIFICARE: errore lettura ({e})"
        )

        return {
            "esito": "DA_VERIFICARE",
            "titolo": titolo,
        }

    testo_completo = (
        titolo
        + " "
        + testo[:40000]
    )

    # ----------------------------------------
    # Territorio
    # ----------------------------------------

    if not territorio_valido(titolo):

        print(
            "  ESCLUSO: territorio non pertinente"
        )

        return {
            "esito": "ESCLUSO",
            "titolo": titolo,
        }

    # ----------------------------------------
    # Beneficiario
    # ----------------------------------------

    beneficiario = classifica_beneficiario(
        testo_completo
    )

    if not beneficiario_pubblicabile(
        beneficiario
    ):

        print(
            "  ESCLUSO: beneficiario "
            f"{beneficiario}"
        )

        return {
            "esito": "ESCLUSO",
            "titolo": titolo,
        }

    # ----------------------------------------
    # Scadenza e stato
    # ----------------------------------------

    scadenza = estrai_scadenza(
        testo_completo
    )

    stato = verifica_stato(
        testo_completo,
        scadenza,
    )

    if stato == "SCADUTO":

        print(
            "  ESCLUSO: bando chiuso/scaduto"
        )

        return {
            "esito": "SCADUTO",
            "titolo": titolo,
            "url": url,
        }

    if stato == "DA_VERIFICARE":

        print(
            "  DA VERIFICARE: "
            "nessuna prova certa di apertura"
        )

        return {
            "esito": "DA_VERIFICARE",
            "titolo": titolo,
            "url": url,
        }

    # ----------------------------------------
    # Pubblicabile
    # ----------------------------------------

    bando = {
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
        "profili": profili_da_beneficiario(
            beneficiario
        ),
        "settori": classifica_settori(
            testo_completo
        ),
        "beneficiarioTipo": beneficiario,
        "descrizione": (
            "Opportunità verificata automaticamente "
            "da BandiAP su fonte ufficiale."
        ),
        "requisiti": (
            "Consultare la fonte ufficiale per "
            "requisiti e spese ammissibili."
        ),
        "dotazione": (
            "Verificare sulla fonte ufficiale"
        ),
        "territorio": fonte["territorio"],
        "url": url,
        "fonteAutomatica": True,
        "versioneMotore": 9,
        "ultimoControllo": OGGI.strftime(
            "%Y-%m-%d"
        ),
    }

    print(
        "  PUBBLICABILE: "
        f"{beneficiario} - "
        f"scadenza {scadenza}"
    )

    return {
        "esito": "PUBBLICABILE",
        "bando": bando,
    }


# ============================================================
# PRIMA MIGRAZIONE V9
# ============================================================

def migra_database(database):

    """
    Elimina soltanto record automatici
    prodotti da versioni precedenti alla V9.

    I record V9, dalle esecuzioni successive,
    vengono conservati.
    """

    risultato = []
    eliminati = 0

    for bando in database:

        automatico = (
            bando.get("fonteAutomatica")
            is True
        )

        versione = bando.get(
            "versioneMotore",
            0,
        )

        if automatico and versione < 9:

            eliminati += 1
            continue

        risultato.append(
            bando
        )

    return risultato, eliminati


# ============================================================
# TROVA BANDO ESISTENTE
# ============================================================

def trova_esistente(database, nuovo):

    url_nuovo = (
        nuovo.get("url", "")
        .rstrip("/")
        .lower()
    )

    nome_nuovo = normalizza(
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
            url_nuovo
            and url
            and url_nuovo == url
        ):
            return bando

        if (
            nome_nuovo
            and nome
            and nome_nuovo == nome
        ):
            return bando

    return None


# ============================================================
# INSERIMENTO / AGGIORNAMENTO
# ============================================================

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

    esistente["ultimoControllo"] = (
        OGGI.strftime("%Y-%m-%d")
    )

    if esistente.get(
        "fonteAutomatica"
    ) is True:

        esistente["versioneMotore"] = 9

    if modificato:
        return "AGGIORNATO"

    return "INVARIATO"


# ============================================================
# CONTROLLO BANDO V9 ESISTENTE
# ============================================================

def ricontrolla_bandi_v9(database):

    chiusi = 0
    aggiornati = 0

    for bando in database:

        if not (
            bando.get("fonteAutomatica")
            is True
            and bando.get("versioneMotore") == 9
        ):
            continue

        url = bando.get("url")

        if not url:
            continue

        try:

            html = scarica(url)
            testo = pulisci_testo(html)

        except Exception:

            continue

        scadenza = estrai_scadenza(
            testo
        )

        stato = verifica_stato(
            testo,
            scadenza,
        )

        vecchio_stato = bando.get(
            "stato"
        )

        if stato == "SCADUTO":

            bando["stato"] = "SCADUTO"

            if vecchio_stato != "SCADUTO":

                chiusi += 1

                print(
                    "CHIUSO: "
                    f"{bando.get('nome')}"
                )

        elif stato == "APERTO":

            if (
                scadenza
                and scadenza
                != bando.get("scadenza")
            ):

                bando["scadenza"] = scadenza
                bando["scadenzaTesto"] = (
                    formatta_data(scadenza)
                )

                aggiornati += 1

                print(
                    "AGGIORNATO: "
                    f"{bando.get('nome')}"
                )

        bando["ultimoControllo"] = (
            OGGI.strftime("%Y-%m-%d")
        )

    return aggiornati, chiusi


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
            f"Errore fonte: {e}"
        )

        return []

    links = estrai_link(
        html,
        fonte,
    )

    print(
        "Candidati trovati: "
        f"{len(links)}"
    )

    risultati = []

    for link in links[:40]:

        risultato = analizza_candidato(
            link,
            fonte,
        )

        risultati.append(
            risultato
        )

    return risultati


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        "BandiAP - aggiornamento automatico V9"
    )
    print("=" * 60)

    database = carica_database()

    print(
        f"Record iniziali: {len(database)}"
    )

    # --------------------------------------------------------
    # 1. MIGRAZIONE DA V8
    # --------------------------------------------------------

    database, vecchi_eliminati = (
        migra_database(database)
    )

    print(
        "Record automatici pre-V9 eliminati: "
        f"{vecchi_eliminati}"
    )

    print(
        "Record preservati: "
        f"{len(database)}"
    )

    # --------------------------------------------------------
    # 2. RICONTROLLO BANDI V9 GIÀ PRESENTI
    # --------------------------------------------------------

    aggiornati_esistenti, chiusi = (
        ricontrolla_bandi_v9(
            database
        )
    )

    # --------------------------------------------------------
    # 3. RICERCA NUOVI BANDI
    # --------------------------------------------------------

    risultati = []

    for fonte in FONTI:

        risultati.extend(
            controlla_fonte(fonte)
        )

    # --------------------------------------------------------
    # 4. ELABORAZIONE RISULTATI
    # --------------------------------------------------------

    nuovi = 0
    aggiornati = aggiornati_esistenti
    da_verificare = 0
    esclusi = 0
    scaduti_rilevati = 0

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

        elif esito == "DA_VERIFICARE":

            da_verificare += 1

        elif esito == "ESCLUSO":

            esclusi += 1

        elif esito == "SCADUTO":

            scaduti_rilevati += 1

    # --------------------------------------------------------
    # 5. ORDINAMENTO
    # --------------------------------------------------------

    database.sort(
        key=lambda b: (
            b.get("stato") == "SCADUTO",
            b.get("scadenza")
            or "9999-12-31",
            b.get("nome", "").lower(),
        )
    )

    # --------------------------------------------------------
    # 6. SALVATAGGIO
    # --------------------------------------------------------

    salva_database(
        database
    )

    # --------------------------------------------------------
    # 7. RIEPILOGO
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("RIEPILOGO V9")
    print("=" * 60)

    print(
        "Pre-V9 eliminati: "
        f"{vecchi_eliminati}"
    )

    print(
        "NUOVI PUBBLICATI: "
        f"{nuovi}"
    )

    print(
        "AGGIORNATI: "
        f"{aggiornati}"
    )

    print(
        "CHIUSI: "
        f"{chiusi}"
    )

    print(
        "SCADUTI trovati ma non pubblicati: "
        f"{scaduti_rilevati}"
    )

    print(
        "DA VERIFICARE: "
        f"{da_verificare}"
    )

    print(
        "ESCLUSI: "
        f"{esclusi}"
    )

    print(
        "TOTALE DATABASE: "
        f"{len(database)}"
    )

    print("=" * 60)


# ============================================================
# AVVIO
# ============================================================

if __name__ == "__main__":
    main()
