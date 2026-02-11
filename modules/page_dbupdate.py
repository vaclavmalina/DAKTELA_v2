import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import time
from bs4 import BeautifulSoup
import os  # PŘIDÁNO: Pro práci se složkami

# --- KONFIGURACE ---
try:
    INSTANCE_URL = st.secrets["DAKTELA_URL"]
    ACCESS_TOKEN = st.secrets["DAKTELA_TOKEN"]
except:
    INSTANCE_URL = "" 
    ACCESS_TOKEN = ""

# ZMĚNA: Cesta do složky 'data'
DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "daktela_data.db")

# --- POMOCNÉ FUNKCE ---

def ensure_data_dir():
    """Zajistí, že existuje složka pro data."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def clean_daktela_html(html_content):
    if not html_content or not isinstance(html_content, str): return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for s in soup(['script', 'style', 'head', 'title', 'meta']): s.decompose()
    for br in soup.find_all("br"): br.replace_with("\n")
    return "\n".join(line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip())

def init_db():
    ensure_data_dir() # Ujistíme se, že složka existuje
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Číselníky
    c.execute('''CREATE TABLE IF NOT EXISTS categories (category_id TEXT PRIMARY KEY, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, title TEXT, email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS statuses (status_id TEXT PRIMARY KEY, title TEXT, color TEXT)''')

    # 2. Hlavní tabulka TICKETŮ
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        ticket_id INTEGER PRIMARY KEY,
        title TEXT,
        category_id TEXT,
        user_id TEXT,
        created_at TIMESTAMP,
        edited_at TIMESTAMP,
        last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')

    # 3. Propojovací tabulka STATUSŮ (M:N)
    c.execute('''CREATE TABLE IF NOT EXISTS ticket_statuses (
        ticket_id INTEGER,
        status_id TEXT,
        PRIMARY KEY (ticket_id, status_id),
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id),
        FOREIGN KEY (status_id) REFERENCES statuses(status_id)
    )''')

    # 4. Tabulka CUSTOM FIELDS (1:N)
    c.execute('''CREATE TABLE IF NOT EXISTS ticket_custom_fields (
        ticket_id INTEGER,
        field_name TEXT,
        value TEXT,
        PRIMARY KEY (ticket_id, field_name),
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
    )''')

    # 5. Tabulka AKTIVIT
    c.execute('''CREATE TABLE IF NOT EXISTS activities (
        activity_id TEXT PRIMARY KEY,
        ticket_id INTEGER,
        time TIMESTAMP,
        type TEXT,
        sender TEXT,
        text_body TEXT,
        FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
    )''')
    conn.commit()
    return conn

def get_db_ticket_map():
    conn = init_db()
    try:
        df = pd.read_sql("SELECT ticket_id, edited_at FROM tickets", conn)
        return dict(zip(df.ticket_id, df.edited_at)) if not df.empty else {}
    except: return {}
    finally: conn.close()

# --- CALLBACKY ---
def set_date_range(d_from, d_to):
    st.session_state.db_date_from = d_from
    st.session_state.db_date_to = d_to

def cb_this_year(): set_date_range(date(date.today().year, 1, 1), date.today())
def cb_last_year(): set_date_range(date(date.today().year - 1, 1, 1), date(date.today().year - 1, 12, 31))
def cb_last_month():
    today = date.today(); first = today.replace(day=1)
    last_prev = first - timedelta(days=1); first_prev = last_prev.replace(day=1)
    set_date_range(first_prev, last_prev)
def cb_this_month(): set_date_range(date.today().replace(day=1), date.today())
def cb_this_week(): set_date_range(date.today() - timedelta(days=date.today().weekday()), date.today())
def cb_yesterday(): set_date_range(date.today() - timedelta(days=1), date.today() - timedelta(days=1))
def cb_today(): set_date_range(date.today(), date.today())

# --- RENDER ---
def render_db_update():
    if 'db_date_from' not in st.session_state: st.session_state.db_date_from = date.today() - timedelta(days=30)
    if 'db_date_to' not in st.session_state: st.session_state.db_date_to = date.today()
    if 'db_cat_index' not in st.session_state: st.session_state.db_cat_index = 0

    # CSS (bez wrapování tlačítek)
    st.markdown("""<style>div.stButton > button {white-space: nowrap;}</style>""", unsafe_allow_html=True)

    # HEADER
    col_back, col_title, _ = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu", key="db_menu_btn"):
            st.session_state.current_app = "main_menu"; st.rerun()
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📥 Stažení dat</h2>", unsafe_allow_html=True)
    st.divider()

    # KATEGORIE
    if 'categories' not in st.session_state:
        try:
            res = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
            st.session_state['categories'] = sorted(res.json().get('result', {}).get('data', []), key=lambda x: x.get('title', '').lower())
        except: pass

    cat_map = {"VŠE (bez filtru)": "ALL"}
    cat_map.update({c['title']: c['name'] for c in st.session_state.get('categories', [])})

    # INPUTY
    st.info(f"Slouží pouze pro aktualizaci dat v databázi podle nastaveného filtru níže.") # Informace pro uživatele
    c1, c2, c3 = st.columns(3)
    d_from = c1.date_input("Datum od (edited)", key="db_date_from")
    d_to = c2.date_input("Datum do (edited)", key="db_date_to")
    cat_label = c3.selectbox("Kategorie", options=list(cat_map.keys()), index=st.session_state.db_cat_index)
    st.session_state.db_cat_index = list(cat_map.keys()).index(cat_label)
    
    # Tlačítka (Grid 4x2)
    st.caption("Rychlý výběr:")
    r1 = st.columns(4); r2 = st.columns(4)
    r1[0].button("Dnes", on_click=cb_today, use_container_width=True)
    r1[1].button("Včera", on_click=cb_yesterday, use_container_width=True)
    r1[2].button("Tento týden", on_click=cb_this_week, use_container_width=True)
    r1[3].button("Tento měsíc", on_click=cb_this_month, use_container_width=True)
    r2[0].button("Minulý měsíc", on_click=cb_last_month, use_container_width=True)
    r2[1].button("Tento rok", on_click=cb_this_year, use_container_width=True)
    r2[2].button("Minulý rok", on_click=cb_last_year, use_container_width=True)

    st.divider()

    if st.button("🚀 Spustit synchronizaci", type="primary", use_container_width=True):
        if not ACCESS_TOKEN: st.error("Chybí token!"); st.stop()
        status_box = st.status("Krok 1: Získávám seznam ticketů...", expanded=True)

        params = {
            "filter[logic]": "and",
            "filter[filters][0][field]": "edited", "filter[filters][0][operator]": "gte", "filter[filters][0][value]": f"{d_from} 00:00:00",
            "filter[filters][1][field]": "edited", "filter[filters][1][operator]": "lte", "filter[filters][1][value]": f"{d_to} 23:59:59",
            "fields[0]": "name", "fields[1]": "title", "fields[2]": "created", "fields[3]": "edited", 
            "fields[4]": "category", "fields[5]": "user", "fields[6]": "statuses", "fields[7]": "customFields",
            "take": 1000
        }
        if cat_map[cat_label] != "ALL":
            params["filter[filters][2][field]"] = "category"
            params["filter[filters][2][operator]"] = "eq"
            params["filter[filters][2][value]"] = cat_map[cat_label]

        try:
            res = requests.get(f"{INSTANCE_URL}/api/v6/tickets.json", params=params, headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
            api_tickets = res.json().get("result", {}).get("data", [])
            status_box.write(f"✅ API vrátilo {len(api_tickets)} záznamů.")
        except Exception as e: status_box.update(label="❌ Chyba", state="error"); st.error(f"{e}"); st.stop()

        status_box.write("Krok 2: Hledám změny...")
        db_map = get_db_ticket_map()
        to_process = [t for t in api_tickets if t['name'] not in db_map or str(t['edited']) > str(db_map[t['name']])]

        if not to_process:
            status_box.update(label="✅ Hotovo! Žádné změny.", state="complete", expanded=False); st.success("Databáze je aktuální."); st.stop()

        status_box.write(f"🔍 Ke stažení: **{len(to_process)}** ticketů."); status_box.update(label="⬇️ Stahuji...", state="running", expanded=True)
        
        progress = st.progress(0); eta = st.empty()
        conn = init_db(); cur = conn.cursor(); start = time.time()

        for i, t in enumerate(to_process):
            t_id = t['name']
            
            # 1. KATEGORIE & USER
            cat_id = None
            if isinstance(t.get('category'), dict):
                cat_id = t['category'].get('name')
                cur.execute("INSERT OR IGNORE INTO categories (category_id, title) VALUES (?, ?)", (cat_id, t['category'].get('title')))
            
            user_id = None
            if isinstance(t.get('user'), dict):
                user_id = t['user'].get('name')
                cur.execute("INSERT OR IGNORE INTO users (user_id, title, email) VALUES (?, ?, ?)", (user_id, t['user'].get('title'), t['user'].get('email')))

            # 2. STATUSY
            cur.execute("DELETE FROM ticket_statuses WHERE ticket_id = ?", (t_id,))
            if isinstance(t.get('statuses'), list):
                for s in t['statuses']:
                    cur.execute("INSERT OR IGNORE INTO statuses (status_id, title, color) VALUES (?, ?, ?)", (s.get('name'), s.get('title'), s.get('color')))
                    cur.execute("INSERT INTO ticket_statuses (ticket_id, status_id) VALUES (?, ?)", (t_id, s.get('name')))

            # 3. CUSTOM FIELDS
            cur.execute("DELETE FROM ticket_custom_fields WHERE ticket_id = ?", (t_id,))
            if isinstance(t.get('customFields'), dict):
                for k, v in t['customFields'].items():
                    val = ", ".join([str(x) for x in v]) if isinstance(v, list) else str(v)
                    if val: cur.execute("INSERT INTO ticket_custom_fields (ticket_id, field_name, value) VALUES (?, ?, ?)", (t_id, k, val))

            # 4. TICKET
            cur.execute('''INSERT OR REPLACE INTO tickets (ticket_id, title, category_id, user_id, created_at, edited_at, last_synced) 
                           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                           (t_id, t.get('title'), cat_id, user_id, t.get('created'), t.get('edited')))

            # 5. AKTIVITY
            try:
                act_res = requests.get(f"{INSTANCE_URL}/api/v6/tickets/{t_id}/activities.json", headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
                if act_res.status_code == 200:
                    acts = act_res.json().get("result", {}).get("data", [])
                    cur.execute("DELETE FROM activities WHERE ticket_id = ?", (t_id,))
                    for act in acts:
                        sender = act['user'].get('title', 'Unknown') if act.get('user') else (act.get('item', {}).get('address', 'System'))
                        raw = act.get('description') or act.get('text') or ""
                        cur.execute('''INSERT INTO activities (activity_id, ticket_id, time, type, sender, text_body) VALUES (?, ?, ?, ?, ?, ?)''', 
                                       (act['name'], t_id, act['time'], act.get('type'), sender, clean_daktela_html(raw)))
                conn.commit()
            except: pass

            # ETA
            elapsed = time.time() - start
            if i > 0:
                rem = int((len(to_process) - i) * (elapsed / i))
                eta.caption(f"⏱️ Zbývá cca: **{rem} s**")
            progress.progress((i + 1) / len(to_process)); time.sleep(0.05)

        conn.close()
        status_box.update(label="🎉 Hotovo!", state="complete", expanded=False); st.success(f"Zpracováno {len(to_process)} ticketů.")
        
        with st.expander("👀 Náhled dat (Statusy & Custom Fields)"):
            conn = init_db()
            st.dataframe(pd.read_sql("""
                SELECT t.ticket_id, t.title, s.title as status, cf.field_name, cf.value
                FROM tickets t
                LEFT JOIN ticket_statuses ts ON t.ticket_id = ts.ticket_id
                LEFT JOIN statuses s ON ts.status_id = s.status_id
                LEFT JOIN ticket_custom_fields cf ON t.ticket_id = cf.ticket_id
                ORDER BY t.edited_at DESC LIMIT 15
            """, conn))
            conn.close()