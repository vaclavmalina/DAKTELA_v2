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
    parts = []
    if h > 0: parts.append(f"{h}h")
    if m > 0: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

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
        if not val: return ""
        return str(val[0])
    return str(val) if val else ""

def find_crm_id(cf_data):
    priority_keys = ['organization_id', 'shipper_id', 'dealer_id', 'Dealer ID', 'id_dopravce']
    for key in priority_keys:
        val = get_cf_value(cf_data, key)
        if val: return val
    return ""

# --- PARSOVÁNÍ AKTIVIT ---

def extract_email_address(data_list):
    """Vytáhne e-mail z hlavičky (např. [{'address': 'email@example.com', ...}])."""
    if isinstance(data_list, list) and len(data_list) > 0:
        return data_list[0].get('address', '')
    return ""

def get_activity_details(act, operator_title):
    """
    Rozpozná odesílatele, příjemce a směr na základě typu aktivity.
    """
    act_type = act.get('type')
    item = act.get('item', {})
    if not isinstance(item, dict): item = {}
    
    sender = ""
    recipient = ""
    direction = item.get('direction', '') # IN / OUT
    
    # 1. EMAIL
    if act_type == 'EMAIL':
        headers = item.get('options', {}).get('headers', {})
        
        if direction == 'in':
            sender = extract_email_address(headers.get('from'))
            recipient = extract_email_address(headers.get('to'))
        else: # out
            sender = extract_email_address(headers.get('from')) 
            # Pokud není from (někdy bývá prázdné u odchozích), je to operátor nebo queue email
            if not sender: sender = operator_title
            recipient = extract_email_address(headers.get('to'))

    # 2. CALL (Hovor)
    elif act_type == 'CALL':
        if direction == 'in':
            sender = item.get('clid', 'Unknown') # Caller ID
            recipient = item.get('did', 'System') # Destination ID
        else:
            sender = operator_title
            recipient = item.get('clid', '')

    # 3. COMMENT (Interní komentář) - Většinou nemá směr nebo je 'in'
    elif act_type == 'COMMENT':
        sender = act.get('user', {}).get('title', 'System')
        recipient = "Internal"
        direction = "INTERNAL"
        
    # 4. CHAT / SMS / OSTATNÍ
    else:
        sender = act.get('user', {}).get('title', 'Unknown')
        recipient = item.get('queue', {}).get('title', '')
        
    return sender, recipient, direction

# --- DATABÁZE ---

def init_db():
    ensure_data_dir()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. ČÍSELNÍKY
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (category_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS statuses (status_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT, color TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS queues (queue_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT)''')

    # 2. CLIENTS & CONTACTS
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        client_id INTEGER PRIMARY KEY AUTOINCREMENT,
        daktela_id TEXT UNIQUE, 
        title TEXT, 
        crm_id TEXT, 
        client_type TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS contacts (
        contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        daktela_id TEXT UNIQUE, 
        title TEXT, 
        client_id INTEGER,
        FOREIGN KEY (client_id) REFERENCES clients(client_id)
    )''')

    # 3. TICKETS
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        ticket_id INTEGER PRIMARY KEY,
        title TEXT,
        category_id INTEGER, user_id INTEGER, status_id INTEGER, client_id INTEGER, contact_id INTEGER,
        priority TEXT, stage TEXT,
        created_date TEXT, created_time TEXT, edited_date TEXT, edited_time TEXT,
        first_answer_date TEXT, first_answer_time TEXT,
        last_activity_op_date TEXT, last_activity_op_time TEXT,
        last_activity_cl_date TEXT, last_activity_cl_time TEXT,
        reopen_date TEXT, reopen_time TEXT,
        activity_count INTEGER, followers TEXT, account_title TEXT,
        vip INTEGER, dev_task1 TEXT, dev_task2 TEXT,
        last_synced_date TEXT, last_synced_time TEXT,
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (status_id) REFERENCES statuses(status_id),
        FOREIGN KEY (client_id) REFERENCES clients(client_id),
        FOREIGN KEY (contact_id) REFERENCES contacts(contact_id)
    )''')

    # 4. ACTIVITIES (Kompletní specifikace)
    c.execute('''CREATE TABLE IF NOT EXISTS activities (
        activity_id INTEGER PRIMARY KEY AUTOINCREMENT, 
        daktela_id TEXT UNIQUE,
        ticket_id INTEGER,
        
        created_date TEXT,
        created_time TEXT,
        
        type TEXT,
        direction TEXT,
        
        sender TEXT,
        recipient TEXT,
        
        queue_id INTEGER,    -- FK na frontu
        category_id INTEGER, -- FK na kategorii (snapshot z ticketu)
        
        has_attachment INTEGER, -- 0 nebo 1
        activity_order INTEGER, -- Chronologické pořadí (1, 2, 3...)
        
        content TEXT, -- Textové tělo
        
        FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id),
        FOREIGN KEY (queue_id) REFERENCES queues (queue_id),
        FOREIGN KEY (category_id) REFERENCES categories (category_id)
    )''')
    
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

# --- LOOKUP FUNCTIONS ---
def get_or_create_user_id(cursor, daktela_sys_name, daktela_title):
    if not daktela_sys_name: return None
    cursor.execute("SELECT user_id FROM users WHERE daktela_id = ?", (daktela_sys_name,))
    row = cursor.fetchone()
    if row: return row[0]
    cursor.execute("INSERT INTO users (daktela_id, title) VALUES (?, ?)", (daktela_sys_name, daktela_title))
    return cursor.lastrowid

def get_or_create_category_id(cursor, daktela_sys_name, title):
    if not daktela_sys_name: return None
    cursor.execute("SELECT category_id FROM categories WHERE daktela_id = ?", (daktela_sys_name,))
    row = cursor.fetchone()
    if row: return row[0]
    cursor.execute("INSERT INTO categories (daktela_id, title) VALUES (?, ?)", (daktela_sys_name, title))
    return cursor.lastrowid

def get_or_create_status_id(cursor, daktela_sys_name, title, color):
    if not daktela_sys_name: return None
    cursor.execute("SELECT status_id FROM statuses WHERE daktela_id = ?", (daktela_sys_name,))
    row = cursor.fetchone()
    if row: return row[0]
    cursor.execute("INSERT INTO statuses (daktela_id, title, color) VALUES (?, ?, ?)", (daktela_sys_name, title, color))
    return cursor.lastrowid

def get_or_create_queue_id(cursor, daktela_sys_name, title):
    if not daktela_sys_name: return None
    cursor.execute("SELECT queue_id FROM queues WHERE daktela_id = ?", (str(daktela_sys_name),))
    row = cursor.fetchone()
    if row: return row[0]
    cursor.execute("INSERT INTO queues (daktela_id, title) VALUES (?, ?)", (str(daktela_sys_name), title))
    return cursor.lastrowid

def get_or_create_client_id(cursor, dak_acc_id, title, crm_id, client_type):
    if not dak_acc_id: return None
    cursor.execute("SELECT client_id FROM clients WHERE daktela_id = ?", (dak_acc_id,))
    row = cursor.fetchone()
    if row:
        if crm_id or client_type:
            cursor.execute("UPDATE clients SET crm_id = ?, client_type = ? WHERE client_id = ?", (crm_id, client_type, row[0]))
        return row[0]
    cursor.execute("INSERT INTO clients (daktela_id, title, crm_id, client_type) VALUES (?, ?, ?, ?)", (dak_acc_id, title, crm_id, client_type))
    return cursor.lastrowid

def get_or_create_contact_id(cursor, dak_cont_id, title, db_client_id):
    if not dak_cont_id: return None
    cursor.execute("SELECT contact_id FROM contacts WHERE daktela_id = ?", (dak_cont_id,))
    row = cursor.fetchone()
    if row:
        if db_client_id:
            cursor.execute("UPDATE contacts SET client_id = ? WHERE contact_id = ?", (db_client_id, row[0]))
        return row[0]
    cursor.execute("INSERT INTO contacts (daktela_id, title, client_id) VALUES (?, ?, ?)", (dak_cont_id, title, db_client_id))
    return cursor.lastrowid

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

    # ZMĚNA: Sjednocení CSS s page_dbview.py (padding + šířka + styl tlačítek)
    st.markdown("""
        <style>
            .block-container {
                max_width: 95% !important;
                padding-top: 2rem;
                padding-bottom: 2rem;
            }
            div.stButton > button {
                white-space: nowrap;
            }
        </style>
    """, unsafe_allow_html=True)

    # Sloupce pro navigaci - zachováváme [1, 4, 1] jako v dbview
    col_back, col_title, col_next = st.columns([1, 4, 1])
            
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>🔄 Aktualizace databáze</h2>", unsafe_allow_html=True)
            
    st.divider()

    if 'categories' not in st.session_state:
        try:
            res = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
            st.session_state['categories'] = sorted(res.json().get('result', {}).get('data', []), key=lambda x: x.get('title', '').lower())
        except: pass

    cat_map = {c['title']: c['name'] for c in st.session_state.get('categories', [])}

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
    
    st.caption("Rychlý výběr data:")
    r1 = st.columns(4); r2 = st.columns(4)
    r1[0].button("Poslední aktualizace", on_click=cb_incremental, use_container_width=True, help="Nastaví datum 'Od' na poslední záznam v databázi.")
    r1[1].button("Dnes", on_click=cb_today, use_container_width=True)
    r1[2].button("Včera", on_click=cb_yesterday, use_container_width=True)
    r1[3].button("Tento týden", on_click=cb_this_week, use_container_width=True)
    r2[0].button("Tento měsíc", on_click=cb_this_month, use_container_width=True)
    r2[1].button("Minulý měsíc", on_click=cb_last_month, use_container_width=True)
    r2[2].button("Tento rok", on_click=cb_this_year, use_container_width=True)
    r2[3].button("Minulý rok", on_click=cb_last_year, use_container_width=True)

    st.divider()

    if st.button("🚀 Spustit synchronizaci", type="primary", use_container_width=True):
        if not ACCESS_TOKEN: st.error("Chybí token!"); st.stop()
        
        stop_placeholder = st.empty()
        status_box = st.status("Probíhá proces synchronizace...", expanded=True)
        status_box.write("⏳ **KROK 1:** Zjišťuji počet záznamů přes API...")
        
        api_tickets = []
        skip = 0
        take = 1000 
        
        base_params = {
            "filter[logic]": "and",
            "filter[filters][0][field]": "edited", "filter[filters][0][operator]": "gte", "filter[filters][0][value]": f"{d_from} 00:00:00",
            "filter[filters][1][field]": "edited", "filter[filters][1][operator]": "lte", "filter[filters][1][value]": f"{d_to} 23:59:59",
            "fields[0]": "name", "fields[1]": "title", "fields[2]": "created", "fields[3]": "edited", 
            "fields[4]": "category", "fields[5]": "user", "fields[6]": "statuses", "fields[7]": "customFields",
            "fields[8]": "priority", "fields[9]": "stage",
            "fields[10]": "first_answer", 
            "fields[12]": "last_activity_operator", "fields[13]": "last_activity_client",
            "fields[14]": "contact",
            "fields[15]": "followers", 
            "fields[16]": "reopen",
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
                    status_box.update(label="🛑 Zastaveno uživatelem", state="error"); st.stop()

                base_params["skip"] = skip
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

        status_box.write("⏳ **KROK 2:** Porovnávám data s databází Balíkobotu...")
        db_map = get_db_ticket_map()
        
        to_process = [t for t in api_tickets if t['name'] not in db_map or str(t['edited']) > str(db_map[t['name']])]

        if not to_process:
            stop_placeholder.empty()
            status_box.write("✅ **KROK 2 HOTOVO:** Žádné nové změny k uložení.")
            status_box.update(label="✅ Vše aktuální", state="complete", expanded=True)
            st.success("Databáze je aktuální."); st.stop()
        
        status_box.write(f"✅ **KROK 2 HOTOVO:** Detekováno **{len(to_process)}** nových nebo změněných ticketů.")
        status_box.write(f"⏳ **KROK 3:** Stahuji detaily a aktivity ({len(to_process)} ticketů)...")
        
        progress = st.progress(0); eta = st.empty()
        conn = init_db(); cur = conn.cursor(); start = time.time()

        for i, t in enumerate(to_process):
            if stop_placeholder.button("🛑 ZASTAVIT PROCES", key=f"stop_row_{i}", type="secondary", use_container_width=True):
                conn.commit(); conn.close()
                status_box.update(label="🛑 Zastaveno uživatelem (data částečně uložena)", state="error")
                st.toast("Proces byl zastaven. Stránka se obnoví."); st.stop()

            t_id = t['name']
            
            # --- STAŽENÍ AKTIVIT ---
            real_activity_count = 0
            
            # Před přípravou aktivit si připravíme DB ID kategorie ticketu, abychom ho mohli k aktivitám přiřadit
            current_category_db_id = None
            if isinstance(t.get('category'), dict):
                current_category_db_id = get_or_create_category_id(cur, t['category'].get('name'), t['category'].get('title'))

            try:
                act_res = requests.get(f"{INSTANCE_URL}/api/v6/tickets/{t_id}/activities.json", headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
                if act_res.status_code == 200:
                    acts = act_res.json().get("result", {}).get("data", [])
                    # Důležité: Seřadíme aktivity podle času vzestupně (nejstarší první) pro správné číslování
                    acts.sort(key=lambda x: x.get('time', ''))
                    
                    real_activity_count = len(acts)
                    cur.execute("DELETE FROM activities WHERE ticket_id = ?", (t_id,))
                    
                    for idx, act in enumerate(acts, start=1):
                        dak_act_id = act['name']
                        act_time = act.get('time')
                        a_date, a_time = parse_iso_datetime(act_time)
                        
                        # Obsah
                        item = act.get('item', {})
                        if not isinstance(item, dict): item = {} # Ošetření pro logy
                        
                        raw_desc = act.get('description') or act.get('text') # Komentář vs Email
                        if not raw_desc:
                            raw_desc = item.get('mail', {}).get('body') # Někdy je tělo tady
                        
                        # Queue
                        queue_data = item.get('queue')
                        db_queue_id = None
                        if isinstance(queue_data, dict):
                            db_queue_id = get_or_create_queue_id(cur, queue_data.get('name'), queue_data.get('title'))
                            
                        # Sender / Recipient / Direction
                        # Jméno operátora pro fallback
                        op_title = act.get('user', {}).get('title', 'System')
                        sender, recipient, direction = get_activity_details(act, op_title)
                        
                        # Attachments (0/1)
                        has_att = 1 if len(item.get('attachments', [])) > 0 else 0
                        
                        # Insert
                        cur.execute('''INSERT INTO activities 
                                       (daktela_id, ticket_id, created_date, created_time, 
                                        type, direction, sender, recipient, 
                                        queue_id, category_id, has_attachment, activity_order, content) 
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                       (dak_act_id, t_id, a_date, a_time, 
                                        act.get('type'), direction, sender, recipient,
                                        db_queue_id, current_category_db_id, has_att, idx, clean_daktela_html(raw_desc)))
            except: pass

            # --- PARSING TICKETU ---
            c_date, c_time = parse_iso_datetime(t.get('created'))
            e_date, e_time = parse_iso_datetime(t.get('edited'))
            fa_date, fa_time = parse_iso_datetime(t.get('first_answer'))
            lao_date, lao_time = parse_iso_datetime(t.get('last_activity_operator'))
            lac_date, lac_time = parse_iso_datetime(t.get('last_activity_client'))
            reopen_date, reopen_time = parse_iso_datetime(t.get('reopen'))
            
            # --- VAZBY ---
            db_category_id = current_category_db_id # Už máme z aktivit
            
            db_user_id = None
            if isinstance(t.get('user'), dict):
                db_user_id = get_or_create_user_id(cur, t['user'].get('name'), t['user'].get('title'))

            db_status_id = None
            raw_statuses = t.get('statuses')
            if isinstance(raw_statuses, list) and len(raw_statuses) > 0:
                s = raw_statuses[0]
                db_status_id = get_or_create_status_id(cur, s.get('name'), s.get('title'), s.get('color'))

            db_client_id = None
            db_contact_id = None
            contact_data = t.get('contact', {})
            if isinstance(contact_data, dict):
                client_type = contact_data.get('database', {}).get('title', '')
                account_data = contact_data.get('account', {})
                if isinstance(account_data, dict):
                    dak_acc_id = account_data.get('name')
                    acc_title = account_data.get('title')
                    acc_cf = account_data.get('customFields', {})
                    crm_id = find_crm_id(acc_cf)
                    db_client_id = get_or_create_client_id(cur, dak_acc_id, acc_title, crm_id, client_type)

                dak_cont_id = contact_data.get('name')
                cont_title = contact_data.get('title')
                db_contact_id = get_or_create_contact_id(cur, dak_cont_id, cont_title, db_client_id)

            followers_str = ""
            raw_followers = t.get('followers')
            if isinstance(raw_followers, list):
                names = [f.get('name') for f in raw_followers if isinstance(f, dict) and f.get('name')]
                followers_str = ",".join(names)
            
            account_title_flat = ""
            if isinstance(t.get('contact'), dict) and isinstance(t['contact'].get('account'), dict):
                 account_title_flat = t['contact']['account'].get('title', '')

            cf = t.get('customFields', {})
            vip_val = cf.get('vip')
            is_vip = 1 if vip_val and isinstance(vip_val, list) and len(vip_val) > 0 else 0
            dev_task1 = get_cf_value(cf, 'note')
            dev_task2 = get_cf_value(cf, 'dev_task_2')

            now = datetime.now()
            s_date, s_time = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

            cur.execute('''INSERT OR REPLACE INTO tickets 
                           (ticket_id, title, category_id, user_id, status_id, 
                            client_id, contact_id,
                            priority, stage, 
                            created_date, created_time, edited_date, edited_time, 
                            first_answer_date, first_answer_time, 
                            last_activity_op_date, last_activity_op_time,
                            last_activity_cl_date, last_activity_cl_time,
                            reopen_date, reopen_time,
                            activity_count, followers, account_title,
                            vip, dev_task1, dev_task2,
                            last_synced_date, last_synced_time) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, 
                                   ?, ?, 
                                   ?, ?, ?, ?, 
                                   ?, ?, 
                                   ?, ?, 
                                   ?, ?, 
                                   ?, ?,
                                   ?, ?, ?, 
                                   ?, ?, ?,
                                   ?, ?)''', 
                           (t_id, t.get('title'), db_category_id, db_user_id, db_status_id,
                            db_client_id, db_contact_id,
                            t.get('priority'), t.get('stage'),
                            c_date, c_time, e_date, e_time,
                            fa_date, fa_time,
                            lao_date, lao_time,
                            lac_date, lac_time,
                            reopen_date, reopen_time,
                            real_activity_count, 
                            followers_str, account_title_flat,
                            is_vip, dev_task1, dev_task2,
                            s_date, s_time))
            
            conn.commit()

            elapsed = time.time() - start
            if i > 0:
                rem_seconds = int((len(to_process) - i) * (elapsed / i))
                eta_text = format_duration(rem_seconds)
                eta.caption(f"⏱️ Zbývá cca: **{eta_text}**")
            
            progress.progress((i + 1) / len(to_process)); time.sleep(0.05)

        conn.close()
        stop_placeholder.empty()
        
        status_box.write("✅ **KROK 3 HOTOVO:** Data úspěšně stažena.")
        status_box.update(label="🎉 Proces dokončen!", state="complete", expanded=True)
        st.success(f"Hotovo! Databáze byla aktualizována o {len(to_process)} ticketů.")