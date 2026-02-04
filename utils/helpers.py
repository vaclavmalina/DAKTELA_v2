import re
import unicodedata
from datetime import datetime
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import streamlit as st
from config import CARRIERS_DATA

@st.cache_resource
def load_anonymizer():
    return AnalyzerEngine(), AnonymizerEngine()

analyzer, anonymizer = load_anonymizer()
 
def slugify(text):
    if not text: return "export"
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)

def anonymize_text(text):
    if not text: return ""
    text = re.sub(r'(?i)(heslo|password|pwd|pass|access_token)(\s*[:=]\s*)(\S+)', r'\1\2[HESLO]', text)
    text = re.sub(r'(\+?420\s?|(?:\b))(\d{3}\s?\d{3}\s?\d{3})\b', '[TELEFON]', text)
    results = analyzer.analyze(text=text, entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "IP_ADDRESS"], language='en')
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized_result.text

def clean_html(raw_html):
    if not raw_html: return ""
    cleantext = raw_html.replace('</p>', '\n').replace('<br>', '\n').replace('<br />', '\n').replace('</div>', '\n').replace('&nbsp;', ' ')
    cleanr = re.compile('<style.*?>.*?</style>|<script.*?>.*?</script>', re.DOTALL)
    cleantext = re.sub(cleanr, '', cleantext)
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', cleantext)
    cleantext = cleantext.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    patterns = [r'From:.*', r'Dne\s.*\snapsal/a:', r'----------\s*Původní zpráva\s*----------', r'On\s.*\swrote:', r'____________________________________________']
    for pattern in patterns:
        cleantext = re.split(pattern, cleantext, flags=re.IGNORECASE)[0]
    cleantext = re.sub(r'\n\s*\n', '\n\n', cleantext)
    return anonymize_text(cleantext.strip())

def format_date_split(date_str):
    if not date_str: return "N/A", "N/A"
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%d.%m.%Y'), dt.strftime('%H:%M:%S')
    except: return date_str, "N/A"

def identify_side(title, email, is_user=False):
    if is_user:
        return f"Balíkobot ({title})" if title and title.lower() != "balikobot" else "Balíkobot"
    clean_title = title.lower() if title else ""
    clean_email = email.lower() if email else ""
    if "balikobot" in clean_email or "balikobot" in clean_title:
        return f"Balíkobot ({title})" if title and title.lower() != "balikobot" else "Balíkobot"
    for slug, name in CARRIERS_DATA.items():
        if (slug and f"@{slug}." in clean_email) or (slug and clean_email.endswith(f"@{slug}.com")) or (name.lower() in clean_title):
            return f"Dopravce ({name})"
    return f"Klient ({title})" if title else "Klient"