import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import time
from bs4 import BeautifulSoup

# --- KONFIGURACE ---
try:
    INSTANCE_URL = st.secrets["DAKTELA_URL"]
    ACCESS_TOKEN = st.secrets["DAKTELA_TOKEN"]
except:
    INSTANCE_URL = "" 
    ACCESS_TOKEN = ""

DB_FILE = "daktela_data.db"

# --- POMOCNÉ FUNKCE (DB & HTML) ---
def clean_daktela_html(html_content):
    if not html_content or not isinstance(html_content, str): return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for script_or_style in soup(['script', 'style', 'head', 'title', 'meta']):
        script_or_style.decompose()
    for br in soup.find_all("br"): br.replace_with("\n")
    text = soup.get_text(separator="\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (ticket_id INTEGER PRIMARY KEY, title TEXT, category TEXT, user TEXT, created_at TIMESTAMP, edited_at TIMESTAMP, last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS activities (activity_id TEXT PRIMARY KEY, ticket_id INTEGER, time TIMESTAMP, type TEXT, sender TEXT, text_body TEXT, FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id))''')
    conn.commit()
    return conn

def get_db_ticket_map():
    conn = init_db()
    try:
        df = pd.read_sql("SELECT ticket_id, edited_at FROM tickets", conn)
        return dict(zip(df.ticket_id, df.edited_at)) if not df.empty else {}
    except: return {}
    finally: conn.close()

# --- CALLBACKY PRO DATUM ---
def set_date_range(d_from, d_to):
    st.session_state.db_date_from = d_from
    st.session_state.db_date_to = d_to

def cb_this_year(): set_date_range(date(date.today().year, 1, 1), date.today())
def cb_last_year(): 
    last_year = date.today().year - 1
    set_date_range(date(last_year, 1, 1), date(last_year, 12, 31))
def cb_last_month():
    today = date.today()
    first = today.replace(day=1)
    last_prev = first - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    set_date_range(first_prev, last_prev)
def cb_this_month(): set_date_range(date.today().replace(day=1), date.today())
def cb_this_week():
    today = date.today()
    start = today - timedelta(days=today.weekday())
    set_date_range(start, today)
def cb_yesterday():
    yesterday = date.today() - timedelta(days=1)
    set_date_range(yesterday, yesterday)
def cb_today(): set_date_range(date.today(), date.today())

# --- HLAVNÍ RENDER FUNKCE ---
def render_db_update():
    # Inicializace session state
    if 'db_date_from' not in st.session_state: st.session_state.db_date_from = date.today() - timedelta(days=30)
    if 'db_date_to' not in st.session_state: st.session_state.db_date_to = date.today()
    if 'db_cat_index' not in st.session_state: st.session_state.db_cat_index = 0

    # --- HEADER ---
    col_back, col_title, col_void = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu", key="db_menu_btn"):
            st.session_state.current_app = "main_menu"
            st.rerun()
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📥 Stažení dat</h2>", unsafe_allow_html=True)
    st.divider()

    # --- NAČTENÍ KATEGORIÍ ---
    if 'categories' not in st.session_state:
        try:
            with st.spinner("Načítám kategorie..."):
                res = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
                st.session_state['categories'] = sorted(res.json().get('result', {}).get('data', []), key=lambda x: x.get('title', '').lower())
        except Exception as e:
            st.error(f"Chyba kategorií: {e}"); st.stop()

    cat_map = {"VŠE (bez filtru)": "ALL"}
    cat_map.update({c['title']: c['name'] for c in st.session_state.get('categories', [])})

    # --- INPUTY ---
    st.info("Smart Sync: Stahuje pouze nové nebo upravené tickety.")
    
    col1, col2, col3 = st.columns(3)
    d_from = col1.date_input("Datum od (edited)", key="db_date_from")
    d_to = col2.date_input("Datum do (edited)", key="db_date_to")
    cat_label = col3.selectbox("Kategorie", options=list(cat_map.keys()), index=st.session_state.db_cat_index, key="db_cat_select")
    
    # Uložení stavu
    st.session_state.db_cat_index = list(cat_map.keys()).index(cat_label)
    selected_cat_id = cat_map[cat_label]

    # --- RYCHLÁ VOLBA DATA (TLAČÍTKA) ---
    st.caption("Rychlý výběr:")
    
    # 1. Řada tlačítek (4 sloupce)
    r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)
    r1_col1.button("Dnes", on_click=cb_today, use_container_width=True)
    r1_col2.button("Včera", on_click=cb_yesterday, use_container_width=True)
    r1_col3.button("Tento týden", on_click=cb_this_week, use_container_width=True)
    r1_col4.button("Tento měsíc", on_click=cb_this_month, use_container_width=True)

    # 2. Řada tlačítek (4 sloupce, poslední prázdný pro zarovnání)
    r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)
    r2_col1.button("Minulý měsíc", on_click=cb_last_month, use_container_width=True)
    r2_col2.button("Tento rok", on_click=cb_this_year, use_container_width=True)
    r2_col3.button("Minulý rok", on_click=cb_last_year, use_container_width=True)
    # r2_col4 zůstává prázdný

    st.divider()

    # --- LOGIKA TLAČÍTKA SPUSTIT ---
    if st.button("🚀 Spustit synchronizaci", type="primary", use_container_width=True):
        if not ACCESS_TOKEN: st.error("Chybí token!"); st.stop()

        status_box = st.status("Krok 1: Získávám seznam ticketů...", expanded=True)
        
        params = {
            "filter[logic]": "and",
            "filter[filters][0][field]": "edited",
            "filter[filters][0][operator]": "gte",
            "filter[filters][0][value]": f"{d_from} 00:00:00",
            "filter[filters][1][field]": "edited",
            "filter[filters][1][operator]": "lte",
            "filter[filters][1][value]": f"{d_to} 23:59:59",
            "fields[0]": "name", "fields[1]": "title", "fields[2]": "created",
            "fields[3]": "edited", "fields[4]": "category", "fields[5]": "user",
            "take": 1000
        }
        if selected_cat_id != "ALL":
            params["filter[filters][2][field]"] = "category"
            params["filter[filters][2][operator]"] = "eq"
            params["filter[filters][2][value]"] = selected_cat_id

        try:
            res = requests.get(f"{INSTANCE_URL}/api/v6/tickets.json", params=params, headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
            res.raise_for_status()
            api_tickets = res.json().get("result", {}).get("data", [])
            status_box.write(f"✅ API vrátilo {len(api_tickets)} záznamů.")
        except Exception as e:
            status_box.update(label="❌ Chyba API", state="error"); st.error(f"Detail: {e}"); st.stop()

        # Filtrace
        status_box.write("Krok 2: Hledám změny...")
        db_map = get_db_ticket_map()
        tickets_to_process = [t for t in api_tickets if t['name'] not in db_map or str(t['edited']) > str(db_map[t['name']])]
        
        if not tickets_to_process:
            status_box.update(label="✅ Hotovo! Žádné změny.", state="complete", expanded=False)
            st.success("Databáze je aktuální."); st.stop()

        status_box.write(f"🔍 Ke stažení: **{len(tickets_to_process)}** ticketů.")
        status_box.update(label="⬇️ Stahuji data...", state="running", expanded=True)

        # Stahování
        progress_bar = st.progress(0)
        eta_text = st.empty()
        conn = init_db(); cursor = conn.cursor()
        start_time = time.time()
        
        for i, t in enumerate(tickets_to_process):
            t_id = t['name']
            # Upsert Ticket
            t_cat = t.get('category', {}).get('title') if isinstance(t.get('category'), dict) else str(t.get('category'))
            t_user = t.get('user', {}).get('title') if isinstance(t.get('user'), dict) else str(t.get('user'))
            
            cursor.execute('''INSERT OR REPLACE INTO tickets (ticket_id, title, category, user, created_at, edited_at, last_synced) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                           (t_id, t.get('title'), t_cat, t_user, t.get('created'), t.get('edited')))

            # Stáhnout aktivity
            try:
                act_res = requests.get(f"{INSTANCE_URL}/api/v6/tickets/{t_id}/activities.json", headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
                if act_res.status_code == 200:
                    activities = act_res.json().get("result", {}).get("data", [])
                    cursor.execute("DELETE FROM activities WHERE ticket_id = ?", (t_id,))
                    for act in activities:
                        raw = act.get('description') or act.get('text') or ""
                        sender = act['user'].get('title', 'Unknown') if act.get('user') else (act.get('item', {}).get('address', 'System'))
                        cursor.execute('''INSERT INTO activities (activity_id, ticket_id, time, type, sender, text_body) VALUES (?, ?, ?, ?, ?, ?)''', 
                                       (act['name'], t_id, act['time'], act.get('type'), sender, clean_daktela_html(raw)))
                conn.commit()
            except Exception as e: print(f"Chyba {t_id}: {e}")
            
            # ETA Výpočet
            elapsed = time.time() - start_time
            if i > 0:
                avg_time = elapsed / i
                remaining = int((len(tickets_to_process) - i) * avg_time)
                eta_text.caption(f"⏱️ Zbývá cca: **{remaining} s**")
                
            progress_bar.progress((i + 1) / len(tickets_to_process))
            time.sleep(0.05)

        conn.close()
        status_box.update(label="🎉 Hotovo!", state="complete", expanded=False)
        st.success(f"Zpracováno {len(tickets_to_process)} ticketů.")
        
        with st.expander("👀 Náhled dat"):
            conn = init_db()
            st.dataframe(pd.read_sql("SELECT * FROM activities ORDER BY time DESC LIMIT 10", conn))
            conn.close()