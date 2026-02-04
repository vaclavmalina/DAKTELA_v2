import sys
import os

# --- BARVY PRO TERMINÁL ---
if sys.platform == 'win32': os.system('color')
C_HEADER = '\033[95m'; C_BLUE = '\033[94m'; C_CYAN = '\033[96m'; C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'; C_RED = '\033[91m'; C_END = '\033[0m'; C_BOLD = '\033[1m'

# --- SEZNAM DOPRAVCŮ ---
CARRIERS_DATA = {
    "cp": "Česká pošta", "ppl": "PPL", "dpd": "DPD", "geis": "Geis", "gls": "GLS",
    "zasilkovna": "Zásilkovna", "intime": "We Do", "toptrans": "Top Trans", "pbh": "Pošta Bez Hranic",
    "dhl": "DHL", "sp": "Slovenská pošta", "ups": "UPS", "tnt": "TNT", "sps": "SK Parcel Service",
    "gw": "Gebrüder Weiss SK", "gwcz": "Gebrüder Weiss CZ", "dhlde": "DHL DE", "messenger": "Messenger",
    "fofr": "Fofr", "fedex": "Fedex", "dachser": "Dachser", "raben": "Raben", "dhlfreightec": "DHL Freight Euroconnect",
    "dhlparcel": "DHL Parcel Europe", "liftago": "Kurýr na přesný čas", "dbschenker": "DB Schenker",
    "dsv": "DSV", "spring": "Spring", "kurier": "123 Kuriér", "airway": "Airway", "japo": "JAPO Transport",
    "magyarposta": "Magyar Posta", "sameday": "Sameday", "sds": "SLOVENSKÝ DORUČOVACÍ SYSTÉM",
    "inpost": "InPost", "onebyallegro": "One by Allegro"
}

# --- REGEXY ---
NOISE_PATTERNS = [
    r"Potvrzujeme, že Vaše zpráva byla úspěšně doručena", 
    r"Jelikož Vám chceme poskytnout nejlepší servis", 
    r"dnes ve dnech .* čerpám dovolenou"
]

CUT_OFF_PATTERNS = [
    r"S pozdravem", r"S pozdravom", r"Kind regards", r"Regards", r"S přáním pěkného dne", 
    r"S přáním hezkého dne", r"Děkuji\n", r"Ďakujem\n", r"Díky\n", r"Tento e-mail nepředstavuje nabídku", 
    r"Pro případ, že tato zpráva obsahuje návrh smlouvy", r"Disclaimer:", r"Confidentiality Notice:", 
    r"Myslete na životní prostředí", r"Please think about the environment"
]

HISTORY_PATTERNS = [
    r"-{5,}", r"_{5,}", r"---------- Odpovězená zpráva ----------", 
    r"Dne .* odesílatel .* napsal\(a\):", r"Od: .* Posláno: .*", r"---------- Původní e-mail ----------"
]