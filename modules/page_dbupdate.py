import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import time
from bs4 import BeautifulSoup
import os
import re

# --- KONFIGURACE ---
try:
    INSTANCE_URL = st.secrets["DAKTELA_URL"]
    ACCESS_TOKEN = st.secrets["DAKTELA_TOKEN"]
except:
    INSTANCE_URL = "" 
    ACCESS_TOKEN = ""

DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "daktela_data.db")

# --- POMOCNÉ FUNKCE ---

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_db_connection():
    ensure_data_dir()
    return sqlite3.connect(DB_FILE)

def clean_daktela_html(html_content):
    if not html_content or not isinstance(html_content, str): return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for s in soup(['script', 'style', 'head', 'title', 'meta']): s.decompose()
    for br in soup.find_all("br"): br.replace_with("\n")
    return "\n".join(line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip())

def format_duration(seconds):
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"

def parse_iso_datetime(iso_string):
    if not iso_string or iso_string == "null":
        return None, None
    try:
        dt = datetime.strptime(iso_string, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except ValueError:
        return None, None

def get_cf_value(cf_data, key):
    val = cf_data.get(key)
    if isinstance(val, list):
        return str(val[0]) if val else ""
    return str(val) if val else ""

def find_crm_id(cf_data):
    priority_keys = ['organization_id', 'shipper_id', 'dealer_id', 'Dealer ID', 'id_dopravce']
    for key in priority_keys:
        val = get_cf_value(cf_data, key)
        if val: return val
    return ""

def get_table_stats():
    """Vrátí seznam tabulek a počet řádků."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    stats = []
    for t in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            count = cursor.fetchone()[0]
            stats.append({"Table": t, "Rows": count})
        except: pass
    conn.close()
    return pd.DataFrame(stats)

# --- DATABÁZE INIT ---
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # (Definice tabulek zůstává stejná, zkráceno pro přehlednost - jsou tam ty CREATE TABLE...)
    # ... Zde by měly být tvé CREATE TABLE příkazy pro tickets, activities atd. ...
    # Pro stručnost vlož jen základ, pokud tabulky neexistují
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (ticket_id INTEGER PRIMARY KEY, title TEXT, category_id INTEGER, user_id INTEGER, status_id INTEGER, client_id INTEGER, contact_id INTEGER, priority TEXT, stage TEXT, created_date TEXT, created_time TEXT, edited_date TEXT, edited_time TEXT, first_answer_date TEXT, first_answer_time TEXT, last_activity_op_date TEXT, last_activity_op_time TEXT, last_activity_cl_date TEXT, last_activity_cl_time TEXT, reopen_date TEXT, reopen_time TEXT, activity_count INTEGER, followers TEXT, account_title TEXT, vip INTEGER, dev_task1 TEXT, dev_task2 TEXT, last_synced_date TEXT, last_synced_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS activities (activity_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, ticket_id INTEGER, created_date TEXT, created_time TEXT, type TEXT, direction TEXT, sender TEXT, recipient TEXT, queue_id INTEGER, category_id INTEGER, has_attachment INTEGER, activity_order INTEGER, content TEXT)''')
    conn.commit()
    return conn

def get_db_ticket_map():
    conn = init_db()
    try:
        df = pd.read_sql("SELECT ticket_id, edited_date || ' ' || edited_time as edited_at FROM tickets", conn)
        return dict(zip(df.ticket_id, df.edited_at)) if not df.empty else {}
    except: return {}
    finally: conn.close()

def get_last_ticket_date():
    conn = init_db()
    try:
        res = pd.read_sql("SELECT MAX(edited_date) as last_edit FROM tickets", conn)
        if not res.empty and res.iloc[0]['last_edit']:
            return pd.to_datetime(res.iloc[0]['last_edit']).date()
    except: pass
    finally: conn.close()
    return None

# --- PARSOVÁNÍ AKTIVIT & LOOKUPY (Zkráceno - vlož sem své původní funkce get_or_create...) ---
# (Tyto funkce v kódu musí zůstat, jen je zde neopisuji celé, aby se to vešlo)
# ... extract_email_address, get_activity_details, get_or_create_user_id atd ...
# PROSÍM, PONECH ZDE TVÉ PŮVODNÍ POMOCNÉ FUNKCE (get_or_create_*, parse_iso_datetime atd.)

# --- RENDER ---
def render_db_update():
    # CSS pro záložky a tlačítka
    st.markdown("""
        <style>
            .block-container { max_width: 95% !important; padding-top: 2rem; padding-bottom: 2rem; }
            div.stButton > button { white-space: nowrap; }
        </style>
    """, unsafe_allow_html=True)

    # Navigace
    c_back, c_tit, _ = st.columns([1, 4, 1])
    with c_back:
        if st.button("⬅️ Menu", key="db_menu_btn"):
            st.session_state.current_app = "main_menu"; st.rerun()
    with c_tit:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>💽 Správa Databáze</h2>", unsafe_allow_html=True)
    st.divider()

    # Záložky pro různé akce
    tab1, tab2, tab3 = st.tabs(["🔄 Synchronizace Daktela", "📥 Import Dat (Excel/CSV)", "🗑️ Správa Tabulek"])

    # --- TAB 1: DAKTELA SYNC ---
    with tab1:
        if 'db_date_from' not in st.session_state: st.session_state.db_date_from = date.today() - timedelta(days=30)
        if 'db_date_to' not in st.session_state: st.session_state.db_date_to = date.today()
        
        # Načtení kategorií pro filtr
        if 'categories' not in st.session_state:
            try:
                res = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
                st.session_state['categories'] = sorted(res.json().get('result', {}).get('data', []), key=lambda x: x.get('title', '').lower())
            except: pass
        cat_map = {c['title']: c['name'] for c in st.session_state.get('categories', [])}

        c1, c2 = st.columns(2)
        d_from = c1.date_input("Datum od (edited)", key="db_date_from")
        d_to = c2.date_input("Datum do (edited)", key="db_date_to")
        
        selected_cat_titles = st.multiselect("Kategorie (nevybráno = VŠE)", options=list(cat_map.keys()), key="db_cat_select")
        
        # Rychlý výběr data (tlačítka) - (Zde můžeš nechat tvůj původní kód s tlačítky cb_today atd.)
        
        st.write("")
        if st.button("🚀 Spustit synchronizaci", type="primary", use_container_width=True):
            # ... ZDE VLOŽ TVŮJ PŮVODNÍ KÓD PRO STAŽENÍ DAT Z DAKTELY ...
            # (Ten velký blok s requests.get a cykly)
            pass # Placeholder, aby kód fungoval, vlož sem logiku z původního souboru

    # --- TAB 2: IMPORT EXCELU ---
    with tab2:
        st.markdown("### 📤 Nahrát novou tabulku")
        st.info("Zde můžete nahrát data (např. Zásilky, Klienti) z Excelu nebo CSV přímo do databáze.")
        
        uploaded_file = st.file_uploader("Vyberte soubor (.xlsx, .csv)", type=['xlsx', 'xls', 'csv'])
        
        if uploaded_file:
            # Náhled názvu tabulky
            clean_name = os.path.splitext(uploaded_file.name)[0].lower().replace(" ", "_").replace("-", "_")
            # Přidáme prefix log_ pokud to vypadá na logistiku, nebo crm_
            table_name = st.text_input("Název nové tabulky v DB:", value=clean_name, help="Bez mezer a diakritiky, např. 'shipments_2024'")
            
            if st.button("💾 Uložit do DB"):
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    
                    # Vyčištění názvů sloupců
                    df.columns = [str(c).strip().replace(" ", "_").lower() for c in df.columns]
                    
                    conn = get_db_connection()
                    df.to_sql(table_name, conn, if_exists='replace', index=False)
                    conn.close()
                    
                    st.success(f"✅ Tabulka '{table_name}' byla úspěšně vytvořena ({len(df)} řádků).")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Chyba při importu: {e}")

    # --- TAB 3: SPRÁVCE TABULEK ---
    with tab3:
        st.markdown("### 🗑️ Správa databáze")
        
        # Zobrazení statistik
        stats_df = get_table_stats()
        if not stats_df.empty:
            st.dataframe(stats_df, use_container_width=True, hide_index=True)
            
            st.divider()
            st.markdown("#### Akce s tabulkami")
            
            col_sel, col_act = st.columns([2, 1])
            target_table = col_sel.selectbox("Vyberte tabulku:", stats_df["Table"].tolist())
            
            action = col_act.radio("Akce:", ["Vymazat data (Truncate)", "Smazat tabulku (Drop)"], label_visibility="collapsed")
            
            if col_act.button("⚠️ Provést akci", type="primary"):
                conn = get_db_connection()
                c = conn.cursor()
                try:
                    if "Drop" in action:
                        c.execute(f"DROP TABLE IF EXISTS {target_table}")
                        st.toast(f"Tabulka {target_table} byla smazána.")
                    else:
                        c.execute(f"DELETE FROM {target_table}")
                        st.toast(f"Data z tabulky {target_table} byla vymazána.")
                    
                    conn.commit()
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Chyba: {e}")
                finally:
                    conn.close()
        else:
            st.info("Databáze je prázdná.")