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
# VERSIONE 10.3
# ============================================================

VERSIONE = "10.4"

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
                "Mozilla/5.0 (compatible; BandiAP/10.4)",
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

    risultati = []
    visti = set()

    def aggiungi(inizio, fine):
        if not inizio or not fine:
            return
        chiave = (inizio, fine)
        if chiave not in visti:
            visti.add(chiave)
            risultati.append(chiave)

    pattern_num = re.compile(
        r"(?:dal|dall['’]?)\s*"
        r"([0-3]?\d[/-][01]?\d[/-]20\d{2})"
        r".{0,100}?"
        r"(?:al|fino al)\s*"
        r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",
        flags=re.I,
    )

    for inizio, fine in pattern_num.findall(testo):
        aggiungi(converti_data(inizio), converti_data(fine))

    mesi_re = "|".join(MESI.keys())

    pattern_testo_anno_finale = re.compile(
        rf"(?:dal|dall['’]?)\s*"
        rf"([0-3]?\d)\s+({mesi_re})\s*"
        rf"(?:al|fino al)\s*"
        rf"([0-3]?\d)\s+({mesi_re})\s+(20\d{{2}})",
        flags=re.I,
    )

    for g1, m1, g2, m2, anno in pattern_testo_anno_finale.findall(testo):
        aggiungi(
            converti_data(f"{g1} {m1} {anno}"),
            converti_data(f"{g2} {m2} {anno}"),
        )

    pattern_testo_completo = re.compile(
        rf"(?:dal|dall['’]?)\s*"
        rf"([0-3]?\d)\s+({mesi_re})\s+(20\d{{2}})"
        rf".{{0,40}}?"
        rf"(?:al|fino al)\s*"
        rf"([0-3]?\d)\s+({mesi_re})\s+(20\d{{2}})",
        flags=re.I,
    )

    for g1, m1, a1, g2, m2, a2 in pattern_testo_completo.findall(testo):
        aggiungi(
            converti_data(f"{g1} {m1} {a1}"),
            converti_data(f"{g2} {m2} {a2}"),
        )

    risultati.sort()
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

    # FORMAZIONE / SOGGETTI EROGATORI
    # Se il bando riguarda l'erogazione o la presentazione di progetti formativi,
    # il beneficiario diretto è normalmente il soggetto attuatore/formatore,
    # non l'impresa o il lavoratore destinatario finale.
    if any(
        x in t
        for x in (
            "erogazione della formazione",
            "presentazione dei progetti relativi ad azioni di formazione",
            "azioni di formazione continua",
            "soggetti attuatori",
            "organismi di formazione",
            "enti di formazione",
            "agenzie formative",
        )
    ):
        return "INTERMEDIARIO_ORGANIZZAZIONE"

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


def raffina_beneficiario_da_titolo(titolo, categoria):

    """
    Raffina la classificazione quando la Regione viene letta solo dalla
    pagina elenco e non abbiamo il dettaglio completo dei beneficiari.

    Obiettivo: evitare che una semplice parola "impresa" nel titolo
    renda pubblicabile un bando rivolto in realtà a Comuni, partenariati,
    enti formativi o altri soggetti intermediari.
    """

    t = normalizza(titolo)

    # Esclusioni forti: il destinatario diretto non è la singola impresa.
    esclusioni = (
        "contributi ai comuni",
        "contributo ai comuni",
        "comuni per",
        "registro regionale dei comuni",
        "partenariato pubblico privato",
        "partenariati pubblico privati",
        "aggregazioni su territorio sub gal",
        "centro servizi territoriale",
        "sistema di centri servizi",
        "formazione trasversale e di base",
        "formazione continua",
        "azioni di formazione continua",
        "erogazione della formazione",
        "infrastrutture irrigue",
        "infrastrutture di bonifica",
    )

    if any(x in t for x in esclusioni):
        return "INTERMEDIARIO_ORGANIZZAZIONE"

    # Casi in cui il titolo indica chiaramente un beneficiario economico diretto.
    if any(
        x in t
        for x in (
            "aiuti alle imprese turistiche",
            "imprese di vendita di prodotti tipici",
            "allevatori",
            "imprese agricole",
            "aziende agricole",
            "imprenditori agricoli",
            "micro piccole e medie imprese",
            "pmi",
            "mpmi",
            "nuove imprese",
            "nuova impresa",
            "avvio di impresa",
            "startup",
            "start up",
        )
    ):
        if any(x in t for x in ("agricol", "allevator", "zootec")):
            return "AGRICOLTURA"
        if any(x in t for x in ("nuove imprese", "nuova impresa", "avvio di impresa", "startup", "start up")):
            return "NUOVA_IMPRESA"
        return "IMPRESA"

    # Se la classificazione originaria è già affidabile, la manteniamo.
    return categoria


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

    url = REGIONE_URL + "/p/1/t/112?idb=" + str(idb)

    try:
        html = scarica(url)
    except Exception as e:
        print(f"  ERRORE Regione ID {idb}: {e}")
        return {"esito": "DA_VERIFICARE", "titolo": f"Regione Marche ID {idb}", "url": url}

    testo = pulisci_html(html)
    titolo = ""

    patterns_titolo = (
        r"Titolo\s*:?\s*(.*?)\s+(?:Area organizzativa|Struttura|Data di pubblicazione|Scadenza)\s*: ?",
        r"(?:^|\s)Titolo\s*:?\s*(.{20,500}?)(?=\s{2,}|Area organizzativa|Struttura|Scadenza)",
    )

    for pattern in patterns_titolo:
        m = re.search(pattern, testo, flags=re.I | re.S)
        if m:
            candidato = re.sub(r"\s+", " ", m.group(1)).strip(" -|:")
            if len(candidato) >= 10:
                titolo = candidato
                break

    if not titolo:
        headings = re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", html, flags=re.I | re.S)
        for h in headings:
            candidato = pulisci_html(h).strip()
            n = normalizza(candidato)
            if len(candidato) >= 15 and "bandi e opportunita" not in n and "bandi attivi" not in n and "regione marche" not in n:
                titolo = candidato
                break

    if not titolo:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        if m:
            titolo = pulisci_html(m.group(1))
            titolo = re.sub(r"\s*[-|]\s*Regione Marche.*$", "", titolo, flags=re.I).strip()

    if not titolo:
        titolo = f"Regione Marche ID {idb}"

    beneficiari = ""
    for pattern in (
        r"Soggetti ammessi beneficiari\s*:?\s*(.*?)\s+(?:Note|Scadenza|Allegati|Contatto)\s*: ?",
        r"(?:Beneficiari|Destinatari)\s*:?\s*(.*?)\s+(?:Note|Scadenza|Allegati|Contatto)\s*: ?",
    ):
        m = re.search(pattern, testo, flags=re.I | re.S)
        if m:
            beneficiari = re.sub(r"\s+", " ", m.group(1)).strip()
            if beneficiari:
                break

    note = testo[:20000]

    if chiusura_esplicita(note):
        return {"esito": "CHIUSO", "titolo": titolo, "url": url}

    finestra = finestra_attuale(note)
    if finestra:
        if finestra["stato"] == "PROGRAMMATO":
            return {
                "esito": "PROGRAMMATO",
                "titolo": titolo,
                "url": url,
                "prossimaApertura": finestra["prossimaApertura"],
            }
        scadenza_effettiva = finestra["scadenza"]
    else:
        scadenza_effettiva = ""
        for pattern in (
            r"Scadenza\s*:?\s*([0-3]?\d[/-][01]?\d[/-]20\d{2})",
            r"Scadenza\s*:?\s*([0-3]?\d\s+[a-zàèéìòù]+\s+20\d{2})",
            r"Scadenza.{0,80}?([0-3]?\d[/-][01]?\d[/-]20\d{2})",
            r"Scadenza.{0,80}?([0-3]?\d\s+[a-zàèéìòù]+\s+20\d{2})",
        ):
            m = re.search(pattern, testo, flags=re.I)
            if m:
                scadenza_effettiva = converti_data(m.group(1))
                if scadenza_effettiva:
                    break

    d = data_obj(scadenza_effettiva)
    if not d:
        return {"esito": "DA_VERIFICARE", "titolo": titolo, "url": url}
    if d < OGGI:
        return {"esito": "CHIUSO", "titolo": titolo, "url": url}

    categoria = classifica_beneficiario(titolo, beneficiari, note)
    if not pubblicabile(categoria):
        return {"esito": "ESCLUSO", "titolo": titolo, "categoria": categoria, "url": url}

    return {
        "esito": "PUBBLICABILE",
        "bando": {
            "id": genera_id("Regione Marche", idb),
            "idFonte": str(idb),
            "nome": titolo,
            "ente": "Regione Marche",
            "stato": "APERTO",
            "scadenza": scadenza_effettiva,
            "scadenzaTesto": formatta_data(scadenza_effettiva),
            "profili": profili(categoria),
            "settori": classifica_settori(titolo + " " + beneficiari + " " + note),
            "beneficiarioTipo": categoria,
            "beneficiari": beneficiari,
            "descrizione": "Bando presente nella fonte ufficiale Regione Marche.",
            "requisiti": beneficiari or "Consultare la fonte ufficiale.",
            "dotazione": "Verificare sulla fonte ufficiale",
            "territorio": "Regione Marche",
            "url": url,
            "fonteAutomatica": True,
            "versioneMotore": VERSIONE,
            "ultimoControllo": OGGI.isoformat(),
        },
    }



def controlla_regione():

    print()
    print("=" * 60)
    print("REGIONE MARCHE")
    print("=" * 60)

    risultati = []

    # Le schede di dettaglio Regione possono rispondere con una pagina
    # di protezione ("We apologize..."). La pagina elenco, invece,
    # contiene già titolo, ID e scadenza: usiamo quella come fonte.
    urls = [REGIONE_URL]

    for pagina in range(2, 8):
        urls.append(f"{REGIONE_URL}/p/{pagina}")

    visti = set()
    candidati = []

    for url_lista in urls:

        try:
            html = scarica(url_lista)

        except Exception as e:
            print(f"Errore pagina Regione {url_lista}: {e}")
            continue

        testo = pulisci_html(html)

        # Ciascun record contiene:
        # titolo ... Identificativo bando : 12345 Scadenza: 23/10/2026
        pattern = re.compile(
            r"(?:Bando per la concessione di contributi|Avviso Pubblico)"
            r"\s+(.*?)\s+"
            r"Identificativo bando\s*:\s*(\d+)\s+"
            r"Scadenza\s*:\s*"
            r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",
            flags=re.I | re.S,
        )

        for titolo, idb, data_testo in pattern.findall(testo):

            titolo = re.sub(r"\s+", " ", titolo).strip(" -|:")
            scadenza = converti_data(data_testo)

            if not titolo or not scadenza:
                continue

            if idb in visti:
                continue

            visti.add(idb)

            candidati.append(
                {
                    "idb": idb,
                    "titolo": titolo,
                    "scadenza": scadenza,
                }
            )

    print(f"Bandi Regione letti da elenco: {len(candidati)}")

    for item in candidati:

        idb = item["idb"]
        titolo = item["titolo"]
        scadenza = item["scadenza"]
        d = data_obj(scadenza)

        url = (
            REGIONE_URL
            + "/p/1/t/112?idb="
            + str(idb)
        )

        if not d:
            risultato = {
                "esito": "DA_VERIFICARE",
                "titolo": titolo,
                "url": url,
            }

        elif d < OGGI:
            risultato = {
                "esito": "CHIUSO",
                "titolo": titolo,
                "url": url,
            }

        else:
            # Classificazione basata sul titolo dell'elenco.
            categoria = classifica_beneficiario(
                titolo,
                "",
                "",
            )

            # V10.4: raffinamento prudenziale per evitare falsi positivi.
            categoria = raffina_beneficiario_da_titolo(
                titolo,
                categoria,
            )

            if not pubblicabile(categoria):

                risultato = {
                    "esito": "ESCLUSO",
                    "titolo": titolo,
                    "categoria": categoria,
                    "url": url,
                }

            else:

                risultato = {
                    "esito": "PUBBLICABILE",
                    "bando": {
                        "id": genera_id("Regione Marche", idb),
                        "idFonte": str(idb),
                        "nome": titolo,
                        "ente": "Regione Marche",
                        "stato": "APERTO",
                        "scadenza": scadenza,
                        "scadenzaTesto": formatta_data(scadenza),
                        "profili": profili(categoria),
                        "settori": classifica_settori(titolo),
                        "beneficiarioTipo": categoria,
                        "beneficiari": "",
                        "descrizione": (
                            "Bando presente nell'elenco ufficiale "
                            "dei bandi attivi della Regione Marche."
                        ),
                        "requisiti": (
                            "Consultare la scheda ufficiale del bando."
                        ),
                        "dotazione": (
                            "Verificare sulla fonte ufficiale"
                        ),
                        "territorio": "Regione Marche",
                        "url": url,
                        "fonteAutomatica": True,
                        "versioneMotore": VERSIONE,
                        "ultimoControllo": OGGI.isoformat(),
                    },
                }

        esito = risultato["esito"]

        nome_log = (
            risultato.get("titolo")
            or risultato.get("bando", {}).get("nome", "")
        )

        if esito == "ESCLUSO" and risultato.get("categoria"):
            print(
                f"[{idb}] {esito} ({risultato.get('categoria')}): "
                f"{nome_log}"
            )
        else:
            print(f"[{idb}] {esito}: {nome_log}")
        risultati.append(risultato)

    return risultati


def estrai_link_camera(html):

    risultati = []
    visti = set()
    pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', flags=re.I | re.S)

    for href, contenuto in pattern.findall(html):
        titolo = pulisci_html(contenuto)
        t = normalizza(titolo)
        href_dec = html_lib.unescape(href).strip()

        if len(t) < 10:
            continue
        if re.search(r"\.(?:pdf|docx?|xlsx?)(?:$|[?#])", href_dec, flags=re.I):
            continue
        if re.search(r"\.(?:pdf|docx?|xlsx?)\b", titolo, flags=re.I):
            continue
        if any(parola in t for parola in ("allegato", "modello", "modulistica", "determina", "graduatoria", "elenco")):
            continue
        if not any(parola in t for parola in ("bando", "avviso", "voucher")):
            continue

        anni = re.findall(r"\b20\d{2}\b", t)
        if anni:
            anni_recenti = [int(x) for x in anni if int(x) >= 2022]
            if anni_recenti and max(anni_recenti) < ANNO:
                continue

        url = urljoin(CAMERA_URL, href_dec)
        if "marche.camcom.it" not in urlparse(url).netloc.lower():
            continue

        chiave = url.rstrip("/")
        if chiave in visti:
            continue
        visti.add(chiave)
        risultati.append({"titolo": titolo, "url": url})

    return risultati


def analizza_camera(link):

    titolo = link["titolo"]
    url = link["url"]

    try:
        html = scarica(url)
    except Exception:
        return {"esito": "DA_VERIFICARE", "titolo": titolo, "url": url}

    testo = pulisci_html(html)

    if chiusura_esplicita(testo):
        return {"esito": "CHIUSO", "titolo": titolo, "url": url}

    scadenza = ""
    for pattern in (
        r"Scadenza\s+termini\s+partecipazione\s*(?:[:|–—-]\s*)?([0-3]?\d[/-][01]?\d[/-]20\d{2})",
        r"Scadenza\s+termini\s+partecipazione\s*(?:[:|–—-]\s*)?([0-3]?\d\s+[a-zàèéìòù]+\s+20\d{2})",
        r"entro il\s+([0-3]?\d[/-][01]?\d[/-]20\d{2})",
        r"entro il\s+([0-3]?\d\s+[a-zàèéìòù]+\s+20\d{2})",
        r"fino al\s+([0-3]?\d[/-][01]?\d[/-]20\d{2})",
    ):
        m = re.search(pattern, testo, flags=re.I)
        if m:
            scadenza = converti_data(m.group(1))
            if scadenza:
                break

    d = data_obj(scadenza)
    if not d:
        return {"esito": "DA_VERIFICARE", "titolo": titolo, "url": url}
    if d < OGGI:
        return {"esito": "CHIUSO", "titolo": titolo, "url": url}

    categoria = classifica_beneficiario(titolo, testo[:7000], "")
    if not pubblicabile(categoria):
        return {"esito": "ESCLUSO", "titolo": titolo, "categoria": categoria, "url": url}

    return {
        "esito": "PUBBLICABILE",
        "bando": {
            "id": genera_id("Camera Marche", url),
            "nome": titolo,
            "ente": "Camera di Commercio delle Marche",
            "stato": "APERTO",
            "scadenza": scadenza,
            "scadenzaTesto": formatta_data(scadenza),
            "profili": profili(categoria),
            "settori": classifica_settori(titolo + " " + testo[:7000]),
            "beneficiarioTipo": categoria,
            "descrizione": "Opportunità verificata sulla fonte ufficiale della Camera di Commercio delle Marche.",
            "requisiti": "Consultare la fonte ufficiale.",
            "dotazione": "Verificare sulla fonte ufficiale",
            "territorio": "Regione Marche",
            "url": url,
            "fonteAutomatica": True,
            "versioneMotore": VERSIONE,
            "ultimoControllo": OGGI.isoformat(),
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
    visti = set()

    # La pagina bandi GAL contiene direttamente i bandi operativi,
    # con la formula "Scadenza per la presentazione delle domande".
    # Evitiamo i link di menu SRG05/SRG06/SRG07, che non sono
    # necessariamente bandi aperti.
    pattern = re.compile(
        r"((?:Bando|Avviso)[^§]{0,1800}?)"
        r"Scadenza\s+per\s+la\s+presentazione\s+delle\s+domande\s*:?\s*"
        r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",
        flags=re.I | re.S,
    )

    matches = pattern.findall(testo)

    # Fallback specifico per le pagine che iniziano direttamente con
    # "Intervento SRGxx ..." prima della parola Bando.
    if not matches:
        pattern = re.compile(
            r"((?:Intervento\s+SR[GDH]\d{2}).{0,2200}?)"
            r"Scadenza\s+per\s+la\s+presentazione\s+delle\s+domande\s*:?\s*"
            r"([0-3]?\d[/-][01]?\d[/-]20\d{2})",
            flags=re.I | re.S,
        )
        matches = pattern.findall(testo)

    print(f"Bandi GAL con scadenza esplicita: {len(matches)}")

    for blocco, data_testo in matches:

        blocco = re.sub(r"\s+", " ", blocco).strip()
        scadenza = converti_data(data_testo)

        if not scadenza:
            continue

        # Ricava un titolo compatto dal blocco.
        titolo = blocco

        # Se nel blocco compare "Bando SRGxx..." usiamo quella porzione.
        m = re.search(
            r"(Bando\s+SR[GDH]\d{2}.*?)(?:Reg\.|Scadenza|Dotazione|Circolare)",
            blocco,
            flags=re.I | re.S,
        )

        if m:
            titolo = m.group(1).strip()

        else:
            # Altrimenti limita la lunghezza senza troncare troppo.
            titolo = titolo[:700].strip()

        titolo = re.sub(r"\s+", " ", titolo).strip(" -|:")

        # Chiave stabile: codice SRG/SRD/SRH + scadenza + titolo.
        codici = re.findall(
            r"\b(SR[GDH]\d{2})\b",
            titolo,
            flags=re.I,
        )

        codice = codici[0].upper() if codici else "GAL"
        chiave = codice + "|" + scadenza + "|" + normalizza(titolo)[:120]

        if chiave in visti:
            continue

        visti.add(chiave)

        d = data_obj(scadenza)

        if not d:
            continue

        if d < OGGI:
            risultati.append(
                {
                    "esito": "CHIUSO",
                    "titolo": titolo,
                    "url": GAL_URL,
                }
            )
            print(f"CHIUSO: {titolo}")
            continue

        categoria = classifica_beneficiario(
            titolo,
            blocco,
            "",
        )

        # PPP / aggregazioni GAL sono mantenuti come opportunità
        # territoriale anche se non classificabili come impresa singola.
        if (
            categoria == "NON_DETERMINATO"
            and any(
                x in normalizza(blocco)
                for x in (
                    "partenariato pubblico privato",
                    "operatori privati",
                    "imprese",
                    "aggregazioni",
                )
            )
        ):
            categoria = "INTERMEDIARIO_ORGANIZZAZIONE"

        # Pubblica solo beneficiari effettivamente ammessi a BandiAP.
        # PPP, aggregazioni e soggetti intermediari non vengono pubblicati.
        ammesso_gal = pubblicabile(categoria)

        if not ammesso_gal:
            risultati.append(
                {
                    "esito": "ESCLUSO",
                    "titolo": titolo,
                    "url": GAL_URL,
                }
            )
            print(f"ESCLUSO: {titolo}")
            continue

        bando = {
            "id": genera_id("GAL Piceno", chiave),
            "nome": titolo,
            "ente": "GAL Piceno",
            "stato": "APERTO",
            "scadenza": scadenza,
            "scadenzaTesto": formatta_data(scadenza),
            "profili": (
                profili(categoria)
                if pubblicabile(categoria)
                else ["altro"]
            ),
            "settori": classifica_settori(
                titolo + " " + blocco
            ),
            "beneficiarioTipo": categoria,
            "descrizione": (
                "Opportunità territoriale presente "
                "nella pagina bandi del GAL Piceno."
            ),
            "requisiti": (
                "Consultare il bando ufficiale GAL Piceno."
            ),
            "dotazione": (
                "Verificare sulla fonte ufficiale"
            ),
            "territorio": "GAL Piceno",
            "url": GAL_URL,
            "fonteAutomatica": True,
            "versioneMotore": VERSIONE,
            "ultimoControllo": OGGI.isoformat(),
        }

        risultati.append(
            {
                "esito": "PUBBLICABILE",
                "bando": bando,
            }
        )

        print(
            f"PUBBLICABILE: {titolo} -> {scadenza}"
        )

    return risultati


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
        "BandiAP - aggiornamento automatico V10.4"
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
    print("RIEPILOGO V10.4")
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
