import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import time
from bs4 import BeautifulSoup
import os

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
    """Zajistí, že existuje složka pro data."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def clean_daktela_html(html_content):
    if not html_content or not isinstance(html_content, str): return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for s in soup(['script', 'style', 'head', 'title', 'meta']): s.decompose()
    for br in soup.find_all("br"): br.replace_with("\n")
    return "\n".join(line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip())

def format_duration(seconds):
    """Formátuje sekundy na čitelný čas (např. 1h 2m 3s)."""
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    parts = []
    if h > 0: parts.append(f"{h}h")
    if m > 0: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

def init_db():
    ensure_data_dir()
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

# ZMĚNA: Funkce pro zjištění posledního data v DB
def get_last_ticket_date():
    conn = init_db()
    try:
        # Vybereme nejnovější 'edited_at' datum
        res = pd.read_sql("SELECT MAX(edited_at) as last_edit FROM tickets", conn)
        if not res.empty and res.iloc[0]['last_edit']:
            # Převedeme na objekt date
            return pd.to_datetime(res.iloc[0]['last_edit']).date()
    except: pass
    finally: conn.close()
    return None

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

# ZMĚNA: Callback pro navázání na poslední data
def cb_incremental():
    last_date = get_last_ticket_date()
    if last_date:
        set_date_range(last_date, date.today())
        st.toast(f"Nastaveno datum od: {last_date}")
    else:
        st.toast("Databáze je prázdná, nelze navázat. Vyberte datum ručně.", icon="⚠️")

# --- RENDER ---
def render_db_update():
    if 'db_date_from' not in st.session_state: st.session_state.db_date_from = date.today() - timedelta(days=30)
    if 'db_date_to' not in st.session_state: st.session_state.db_date_to = date.today()
    if 'db_cat_select' not in st.session_state: st.session_state.db_cat_select = []

    st.markdown("""<style>div.stButton > button {white-space: nowrap;}</style>""", unsafe_allow_html=True)

    # HEADER
    col_back, col_title, _ = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu", key="db_menu_btn"):
            st.session_state.current_app = "main_menu"; st.rerun()
    with col_title:
        # ZMĚNA: Nový nadpis
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>🔄 Aktualizace databáze</h2>", unsafe_allow_html=True)
    st.divider()

    # KATEGORIE - NAČTENÍ
    if 'categories' not in st.session_state:
        try:
            res = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
            st.session_state['categories'] = sorted(res.json().get('result', {}).get('data', []), key=lambda x: x.get('title', '').lower())
        except: pass

    cat_map = {c['title']: c['name'] for c in st.session_state.get('categories', [])}

    # INPUTY
    st.info(f"Slouží pro stažení a synchronizaci záznamů z Daktely do lokální databáze.") 
    
    c1, c2 = st.columns(2)
    d_from = c1.date_input("Datum od (edited)", key="db_date_from")
    d_to = c2.date_input("Datum do (edited)", key="db_date_to")
    
    selected_cat_titles = st.multiselect(
        "Kategorie (nevybráno = VŠE)", 
        options=list(cat_map.keys()), 
        key="db_cat_select",
        help="Můžete vybrat více kategorií. Pokud nevyberete nic, stahují se všechny."
    )
    
    # GRID TLAČÍTEK
    st.caption("Rychlý výběr data:")
    r1 = st.columns(4); r2 = st.columns(4)
    # ZMĚNA: Přidání tlačítka pro inkrementální update jako první možnost
    r1[0].button("Poslední aktualizace", on_click=cb_incremental, use_container_width=True, help="Nastaví datum 'Od' na poslední záznam v databázi.")
    r1[1].button("Dnes", on_click=cb_today, use_container_width=True)
    r1[2].button("Včera", on_click=cb_yesterday, use_container_width=True)
    r1[3].button("Tento týden", on_click=cb_this_week, use_container_width=True)
    
    r2[0].button("Tento měsíc", on_click=cb_this_month, use_container_width=True)
    r2[1].button("Minulý měsíc", on_click=cb_last_month, use_container_width=True)
    r2[2].button("Tento rok", on_click=cb_this_year, use_container_width=True)
    r2[3].button("Minulý rok", on_click=cb_last_year, use_container_width=True)

    st.divider()

    # TLAČÍTKO START
    if st.button("🚀 Spustit synchronizaci", type="primary", use_container_width=True):
        if not ACCESS_TOKEN: st.error("Chybí token!"); st.stop()
        
        stop_placeholder = st.empty()
        
        # ZMĚNA: Status box nyní slouží jako kontejner pro log
        status_box = st.status("Probíhá proces synchronizace...", expanded=True)
        
        # --- KROK 1 ---
        status_box.write("⏳ **KROK 1:** Zjišťuji počet záznamů přes API (stránkování)...")
        
        api_tickets = []
        skip = 0
        take = 1000 
        
        base_params = {
            "filter[logic]": "and",
            "filter[filters][0][field]": "edited", "filter[filters][0][operator]": "gte", "filter[filters][0][value]": f"{d_from} 00:00:00",
            "filter[filters][1][field]": "edited", "filter[filters][1][operator]": "lte", "filter[filters][1][value]": f"{d_to} 23:59:59",
            "fields[0]": "name", "fields[1]": "title", "fields[2]": "created", "fields[3]": "edited", 
            "fields[4]": "category", "fields[5]": "user", "fields[6]": "statuses", "fields[7]": "customFields",
            "take": take
        }

        if selected_cat_titles:
            selected_ids = [cat_map[t] for t in selected_cat_titles]
            base_params["filter[filters][2][field]"] = "category"
            base_params["filter[filters][2][operator]"] = "in"
            for idx, val in enumerate(selected_ids):
                base_params[f"filter[filters][2][value][{idx}]"] = val

        try:
            while True:
                if stop_placeholder.button("🛑 ZASTAVIT PROCES", key=f"stop_page_{skip}", type="secondary", use_container_width=True):
                    status_box.update(label="🛑 Zastaveno uživatelem", state="error")
                    st.stop()

                base_params["skip"] = skip
                # Jen malá vizuální indikace uvnitř kroku
                # status_box.write(f"&nbsp;&nbsp;&nbsp;➡️ Stahuji dávku: {skip}...")
                
                res = requests.get(f"{INSTANCE_URL}/api/v6/tickets.json", params=base_params, headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
                
                if res.status_code != 200:
                    status_box.update(label="❌ Chyba API", state="error"); st.error(f"API Error {res.status_code}: {res.text}"); st.stop()
                
                batch = res.json().get("result", {}).get("data", [])
                
                if not batch: break
                api_tickets.extend(batch)
                if len(batch) < take: break
                skip += take
                time.sleep(0.1)

            status_box.write(f"✅ **KROK 1 HOTOVO:** Nalezeno **{len(api_tickets)}** záznamů v API.")
            
        except Exception as e: 
            status_box.update(label="❌ Chyba", state="error"); st.error(f"{e}"); st.stop()

        # --- KROK 2 ---
        status_box.write("⏳ **KROK 2:** Porovnávám data s databází Balíkobotu...")
        db_map = get_db_ticket_map()
        
        to_process = [t for t in api_tickets if t['name'] not in db_map or str(t['edited']) > str(db_map[t['name']])]

        if not to_process:
            stop_placeholder.empty()
            status_box.write("✅ **KROK 2 HOTOVO:** Žádné nové změny k uložení.")
            status_box.update(label="✅ Vše aktuální", state="complete", expanded=True)
            st.success("Databáze je aktuální."); st.stop()
        
        status_box.write(f"✅ **KROK 2 HOTOVO:** Detekováno **{len(to_process)}** nových nebo změněných ticketů.")

        # --- KROK 3 ---
        status_box.write(f"⏳ **KROK 3:** Stahuji detaily a aktivity ({len(to_process)} ticketů)...")
        
        progress = st.progress(0); eta = st.empty()
        conn = init_db(); cur = conn.cursor(); start = time.time()

        for i, t in enumerate(to_process):
            if stop_placeholder.button("🛑 ZASTAVIT PROCES", key=f"stop_row_{i}", type="secondary", use_container_width=True):
                conn.commit()
                conn.close()
                status_box.update(label="🛑 Zastaveno uživatelem (data částečně uložena)", state="error")
                st.toast("Proces byl zastaven. Stránka se obnoví.")
                st.stop()

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

            elapsed = time.time() - start
            if i > 0:
                rem_seconds = int((len(to_process) - i) * (elapsed / i))
                eta_text = format_duration(rem_seconds)
                eta.caption(f"⏱️ Zbývá cca: **{eta_text}**")
            
            progress.progress((i + 1) / len(to_process)); time.sleep(0.05)

        conn.close()
        stop_placeholder.empty()
        
        # --- KROK 4 ---
        status_box.write("✅ **KROK 3 HOTOVO:** Data úspěšně stažena.")
        status_box.update(label="🎉 Proces dokončen!", state="complete", expanded=True)
        st.success(f"Hotovo! Databáze byla aktualizována o {len(to_process)} ticketů.")
        
        # ZMĚNA: Náhled dat odstraněn