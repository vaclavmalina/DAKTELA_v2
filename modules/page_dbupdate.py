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

# --- IN-MEMORY CACHE PRO EXTRÉMNÍ ZRYCHLENÍ ---
class DBLookup:
    def __init__(self, conn):
        self.conn = conn
        self.c = conn.cursor()
        self.cache = {
            'users': {row[0]: row[1] for row in self.c.execute("SELECT daktela_id, user_id FROM users").fetchall()},
            'categories': {row[0]: row[1] for row in self.c.execute("SELECT daktela_id, category_id FROM categories").fetchall()},
            'statuses': {row[0]: row[1] for row in self.c.execute("SELECT daktela_id, status_id FROM statuses").fetchall()},
            'queues': {row[0]: row[1] for row in self.c.execute("SELECT daktela_id, queue_id FROM queues").fetchall()},
            'clients': {row[0]: row[1] for row in self.c.execute("SELECT daktela_id, client_id FROM clients").fetchall()},
            'contacts': {row[0]: row[1] for row in self.c.execute("SELECT daktela_id, contact_id FROM contacts").fetchall()}
        }
        
    def get_or_create(self, table, dak_id, **kwargs):
        if not dak_id: return None
        dak_id = str(dak_id)
        if dak_id in self.cache[table]:
            return self.cache[table][dak_id]
        
        keys = ['daktela_id'] + list(kwargs.keys())
        vals = [dak_id] + list(kwargs.values())
        placeholders = ",".join(["?"] * len(keys))
        cols = ",".join(keys)
        
        self.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", vals)
        new_id = self.c.lastrowid
        self.cache[table][dak_id] = new_id
        return new_id

# --- POMOCNÉ FUNKCE ---

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_db_connection():
    ensure_data_dir()
    return sqlite3.connect(DB_FILE)

def clean_daktela_html(html_content):
    if not html_content or not isinstance(html_content, str): return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for s in soup(['script', 'style', 'head', 'title', 'meta']): s.decompose()
        for br in soup.find_all("br"): br.replace_with("\n")
        return "\n".join(line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip())
    except:
        return str(html_content)

def format_duration(seconds):
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}h {m}m {s}s"
    elif m > 0: return f"{m}m {s}s"
    else: return f"{s}s"

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

def extract_email_address(data):
    if not data: return ""
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict): return first.get('address', '')
        elif isinstance(first, str): return first
    elif isinstance(data, str): return data
    return ""

def get_activity_details(act, operator_title):
    act_type = act.get('type')
    
    if not act_type and act.get('description'):
        act_type = 'COMMENT'

    item = act.get('item') or {}
    sender = ""
    recipient = ""
    direction = str(item.get('direction', '')).upper()
    
    if act_type == 'EMAIL':
        options = item.get('options') or {}
        headers = options.get('headers') or {}
        sender = extract_email_address(headers.get('from'))
        recipient = extract_email_address(headers.get('to'))
        
        if not sender and direction == 'OUT': sender = operator_title
        if not direction:
            direction = "OUT" if sender == operator_title else "IN"

    elif act_type == 'CALL':
        if direction == 'IN':
            sender = item.get('clid', 'Unknown')
            recipient = item.get('did', 'System')
        else:
            sender = operator_title
            recipient = item.get('clid', '')

    elif act_type == 'COMMENT':
        sender = (act.get('user') or {}).get('title', 'System')
        recipient = "Internal"
        direction = "INTERNAL"
        
    else:
        sender = (act.get('user') or {}).get('title', 'Unknown')
        recipient = (item.get('queue') or {}).get('title', '')
        
    return sender, recipient, direction, act_type

def is_auto_reply(act, raw_desc):
    item = act.get('item') or {}
    
    options = item.get('options') or act.get('options') or {}
    headers = options.get('headers') or {}
    
    headers_lower = {str(k).lower(): str(v).lower() for k, v in headers.items()}
    if headers_lower.get('auto-submitted') == 'auto-generated':
        return 1
    if headers_lower.get('x-auto-response-suppress') == 'all':
        return 1
        
    text_to_check = str(raw_desc).lower()
    
    split_markers = [
        "---------- odpovězená zpráva ----------", 
        "---------- replied message ----------",
        "napsal(a):", 
        "wrote:",
        "<blockquote"
    ]
    
    for marker in split_markers:
        if marker in text_to_check:
            text_to_check = text_to_check.split(marker)[0]
            
    auto_phrases = [
        "potvrzujeme, že vaše zpráva byla úspěšně doručena",
        "we are confirming that your message has been successfully delivered",
        "upozornění na napojení dopravců",
        "automaticky generovaná zpráva",
        "toto je automatická odpověď"
    ]
    
    for phrase in auto_phrases:
        if phrase in text_to_check:
            return 1
            
    return 0

# --- DATABÁZE INIT ---
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (category_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS statuses (status_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS queues (queue_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS clients (client_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT, crm_id TEXT, client_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contacts (contact_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, title TEXT, client_id INTEGER, FOREIGN KEY (client_id) REFERENCES clients(client_id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        ticket_id INTEGER PRIMARY KEY, title TEXT, category_id INTEGER, user_id INTEGER, status_id INTEGER, client_id INTEGER, contact_id INTEGER, 
        priority TEXT, stage TEXT, created_date TEXT, created_time TEXT, edited_date TEXT, edited_time TEXT, first_answer_date TEXT, first_answer_time TEXT, 
        last_activity_op_date TEXT, last_activity_op_time TEXT, last_activity_cl_date TEXT, last_activity_cl_time TEXT, reopen_date TEXT, reopen_time TEXT, 
        activity_count INTEGER, followers TEXT, account_title TEXT, vip INTEGER, dev_task1 TEXT, dev_task2 TEXT, last_synced_date TEXT, last_synced_time TEXT,
        FOREIGN KEY (category_id) REFERENCES categories(category_id), FOREIGN KEY (user_id) REFERENCES users(user_id), FOREIGN KEY (status_id) REFERENCES statuses(status_id),
        FOREIGN KEY (client_id) REFERENCES clients(client_id), FOREIGN KEY (contact_id) REFERENCES contacts(contact_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS activities (
        activity_id INTEGER PRIMARY KEY AUTOINCREMENT, daktela_id TEXT UNIQUE, ticket_id INTEGER, created_date TEXT, created_time TEXT, 
        type TEXT, direction TEXT, sender TEXT, recipient TEXT, queue_id INTEGER, category_id INTEGER, has_attachment INTEGER, 
        activity_order INTEGER, automatic_reply INTEGER, content TEXT,
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id), FOREIGN KEY (queue_id) REFERENCES queues(queue_id), FOREIGN KEY (category_id) REFERENCES categories(category_id)
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

def get_table_stats():
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

# --- CALLBACKY ---
def set_date_range(d_from, d_to):
    st.session_state.db_date_from = d_from
    st.session_state.db_date_to = d_to
def cb_incremental():
    last_date = get_last_ticket_date()
    if last_date:
        set_date_range(last_date, date.today())
        st.toast(f"Nastaveno datum od: {last_date}")
    else:
        st.toast("Databáze je prázdná, nelze navázat. Vyberte datum ručně.", icon="⚠️")

# --- RENDER ---
def render_db_update():
    st.markdown("""<style>.block-container { max_width: 95% !important; padding-top: 2rem; padding-bottom: 2rem; } div.stButton > button { white-space: nowrap; }</style>""", unsafe_allow_html=True)

    c_back, c_tit, _ = st.columns([1, 4, 1])
    with c_back:
        if st.button("⬅️ Menu", key="db_menu_btn"):
            st.session_state.current_app = "main_menu"; st.rerun()
    with c_tit:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>💽 Správa Databáze</h2>", unsafe_allow_html=True)
    st.divider()

    tab1, tab2, tab3 = st.tabs(["🔄 Synchronizace Daktela", "📥 Import Dat (Excel/CSV)", "🛠️ Pokročilá Správa Tabulek"])

    # --- TAB 1: DAKTELA SYNC ---
    with tab1:
        if 'db_date_from' not in st.session_state: st.session_state.db_date_from = date.today()
        if 'db_date_to' not in st.session_state: st.session_state.db_date_to = date.today()
        
        if 'categories' not in st.session_state:
            try:
                res = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
                st.session_state['categories'] = sorted(res.json().get('result', {}).get('data', []), key=lambda x: x.get('title', '').lower())
            except: pass
        cat_map = {c['title']: c['name'] for c in st.session_state.get('categories', [])}

        c1, c2 = st.columns(2)
        d_from = c1.date_input("Datum od (edited)", value=st.session_state.db_date_from, key="db_date_from")
        d_to = c2.date_input("Datum do (edited)", value=st.session_state.db_date_to, key="db_date_to")
        selected_cat_titles = st.multiselect("Kategorie (nevybráno = VŠE)", options=list(cat_map.keys()), key="db_cat_select")
        
        st.write("")
        
        btn_placeholder = st.empty()
        stop_placeholder = st.empty()
        ui_status = st.empty()
        prog_text = st.empty()
        prog_bar = st.empty()

        if btn_placeholder.button("🚀 Spustit synchronizaci", type="primary", use_container_width=True):
            if not ACCESS_TOKEN: st.error("Chybí token!"); st.stop()
            
            btn_placeholder.empty()
            ui_status.info("⏳ **Krok 1/3:** Zjišťuji počet záznamů přes API...")
            
            session = requests.Session()
            session.headers.update({"X-AUTH-TOKEN": ACCESS_TOKEN})
            
            api_tickets = []
            skip = 0
            take = 1000 
            
            base_params = {
                "filter[logic]": "and",
                "filter[filters][0][field]": "edited", "filter[filters][0][operator]": "gte", "filter[filters][0][value]": f"{d_from} 00:00:00",
                "filter[filters][1][field]": "edited", "filter[filters][1][operator]": "lte", "filter[filters][1][value]": f"{d_to} 23:59:59",
                "fields[0]": "name", "fields[1]": "title", "fields[2]": "created", "fields[3]": "edited", 
                "fields[4]": "category", "fields[5]": "user", "fields[6]": "statuses", "fields[7]": "customFields",
                "fields[8]": "priority", "fields[9]": "stage", "fields[10]": "first_answer", 
                "fields[11]": "last_activity_operator", "fields[12]": "last_activity_client",
                "fields[13]": "contact", "fields[14]": "followers", "fields[15]": "reopen",
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
                    if stop_placeholder.button("🛑 ZASTAVIT PROCES", key=f"stop_api_{skip}", type="secondary", use_container_width=True):
                        ui_status.error("🛑 Zastaveno uživatelem."); st.stop()

                    res = session.get(f"{INSTANCE_URL}/api/v6/tickets.json", params=base_params)
                    if res.status_code != 200:
                        ui_status.error(f"❌ Chyba API: {res.text}"); st.stop()
                    
                    batch = res.json().get("result", {}).get("data", [])
                    if not batch: break
                    api_tickets.extend(batch)
                    if len(batch) < take: break
                    skip += take
            except Exception as e: 
                ui_status.error(f"❌ Chyba: {e}"); st.stop()

            ui_status.info(f"✅ **Krok 1/3:** Nalezeno {len(api_tickets)} záznamů v API.\n\n⏳ **Krok 2/3:** Porovnávám data s lokální databází...")
            
            db_map = get_db_ticket_map()
            to_process = [t for t in api_tickets if t['name'] not in db_map or str(t['edited']) > str(db_map[t['name']])]

            if not to_process:
                stop_placeholder.empty()
                ui_status.success("✅ **Vše je aktuální.** Žádné nové tickety ke stažení.")
                st.stop()
            
            ui_status.info(f"✅ **Krok 2/3:** Identifikováno **{len(to_process)}** nových/změněných ticketů.\n\n⏳ **Krok 3/3:** Stahuji a ukládám detailní data...")
            pb = prog_bar.progress(0)
            
            conn = init_db()
            db = DBLookup(conn)
            start = time.time()
            total_tickets = len(to_process)

            for i, t in enumerate(to_process, start=1):
                if stop_placeholder.button("🛑 ZASTAVIT PROCES", key=f"stop_row_{i}", type="secondary", use_container_width=True):
                    conn.commit(); conn.close()
                    ui_status.error("🛑 Zastaveno uživatelem. Část dat byla uložena."); st.stop()

                t_id = t['name']
                
                elapsed = time.time() - start
                avg_time = elapsed / i
                rem_time = int((total_tickets - i) * avg_time)
                eta_str = format_duration(rem_time)
                
                prog_text.markdown(f"**Ticket:** `{t_id}` | Zpracováno: **{i} / {total_tickets}** | ⏱️ ETA: **{eta_str}**")
                pb.progress(i / total_tickets)
                
                cat_dict = t.get('category') or {}
                db_category_id = db.get_or_create('categories', cat_dict.get('name'), title=cat_dict.get('title'))
                
                user_dict = t.get('user') or {}
                db_user_id = db.get_or_create('users', user_dict.get('name'), title=user_dict.get('title'))
                
                db_status_id = None
                status_list = t.get('statuses') or []
                if len(status_list) > 0:
                    s = status_list[0]
                    db_status_id = db.get_or_create('statuses', s.get('name'), title=s.get('title'))

                # --- AKTIVITY ---
                real_activity_count = 0
                all_activities = []
                act_skip = 0
                act_take = 100
                
                try:
                    while True:
                        act_res = session.get(f"{INSTANCE_URL}/api/v6/tickets/{t_id}/activities.json?skip={act_skip}&take={act_take}")
                        if act_res.status_code == 200:
                            acts = act_res.json().get("result", {}).get("data", [])
                            if not acts: break
                            all_activities.extend(acts)
                            if len(acts) < act_take: break
                            act_skip += act_take
                        else: break
                except: pass

                if all_activities:
                    all_activities.sort(key=lambda x: x.get('time', ''))
                    real_activity_count = len(all_activities)
                    db.c.execute("DELETE FROM activities WHERE ticket_id = ?", (t_id,))
                    
                    for idx, act in enumerate(all_activities, start=1):
                        dak_act_id = act['name']
                        a_date, a_time = parse_iso_datetime(act.get('time'))
                        
                        item = act.get('item') or {}
                        
                        raw_desc = act.get('text') or act.get('description') or item.get('text') or item.get('description') or (item.get('mail') or {}).get('body') or ""
                        
                        queue_dict = item.get('queue') or {}
                        db_queue_id = db.get_or_create('queues', queue_dict.get('name'), title=queue_dict.get('title'))
                        
                        op_title = (act.get('user') or {}).get('title', 'System')
                        sender, recipient, direction, act_type_final = get_activity_details(act, op_title)
                        
                        has_att = 1 if len(item.get('attachments') or []) > 0 else 0
                        auto_flag = is_auto_reply(act, raw_desc)
                        
                        db.c.execute('''INSERT OR REPLACE INTO activities 
                                       (daktela_id, ticket_id, created_date, created_time, 
                                        type, direction, sender, recipient, 
                                        queue_id, category_id, has_attachment, activity_order, automatic_reply, content) 
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                       (dak_act_id, t_id, a_date, a_time, 
                                        act_type_final, direction, sender, recipient,
                                        db_queue_id, db_category_id, has_att, idx, auto_flag, clean_daktela_html(raw_desc)))

                # --- PARSING TICKETU ---
                c_date, c_time = parse_iso_datetime(t.get('created'))
                e_date, e_time = parse_iso_datetime(t.get('edited'))
                fa_date, fa_time = parse_iso_datetime(t.get('first_answer'))
                lao_date, lao_time = parse_iso_datetime(t.get('last_activity_operator'))
                lac_date, lac_time = parse_iso_datetime(t.get('last_activity_client'))
                reopen_date, reopen_time = parse_iso_datetime(t.get('reopen'))
                
                db_client_id = None
                db_contact_id = None
                contact_data = t.get('contact') or {}
                if contact_data:
                    client_type = (contact_data.get('database') or {}).get('title', '')
                    acc_data = contact_data.get('account') or {}
                    if acc_data:
                        dak_acc_id = acc_data.get('name')
                        acc_title = acc_data.get('title')
                        crm_id = find_crm_id(acc_data.get('customFields') or {})
                        db_client_id = db.get_or_create('clients', dak_acc_id, title=acc_title, crm_id=crm_id, client_type=client_type)

                    dak_cont_id = contact_data.get('name')
                    cont_title = contact_data.get('title')
                    db_contact_id = db.get_or_create('contacts', dak_cont_id, title=cont_title, client_id=db_client_id)

                followers_str = ""
                raw_followers = t.get('followers')
                if isinstance(raw_followers, list):
                    followers_str = ",".join([f.get('name') for f in raw_followers if isinstance(f, dict) and f.get('name')])
                
                account_title_flat = ""
                if contact_data and isinstance(contact_data.get('account'), dict):
                     account_title_flat = contact_data['account'].get('title', '')

                cf_raw = t.get('customFields')
                cf = cf_raw if isinstance(cf_raw, dict) else {}
                
                vip_val = cf.get('vip')
                is_vip = 1 if vip_val and isinstance(vip_val, list) and len(vip_val) > 0 else 0
                dev_task1 = get_cf_value(cf, 'note')
                dev_task2 = get_cf_value(cf, 'dev_task_2')

                now = datetime.now()
                s_date, s_time = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

                db.c.execute('''INSERT OR REPLACE INTO tickets 
                               (ticket_id, title, category_id, user_id, status_id, client_id, contact_id,
                                priority, stage, created_date, created_time, edited_date, edited_time, 
                                first_answer_date, first_answer_time, last_activity_op_date, last_activity_op_time,
                                last_activity_cl_date, last_activity_cl_time, reopen_date, reopen_time,
                                activity_count, followers, account_title, vip, dev_task1, dev_task2, last_synced_date, last_synced_time) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                               (t_id, t.get('title'), db_category_id, db_user_id, db_status_id, db_client_id, db_contact_id,
                                t.get('priority'), t.get('stage'), c_date, c_time, e_date, e_time,
                                fa_date, fa_time, lao_date, lao_time, lac_date, lac_time, reopen_date, reopen_time,
                                real_activity_count, followers_str, account_title_flat, is_vip, dev_task1, dev_task2, s_date, s_time))
                
                if i % 50 == 0:
                    conn.commit()

            conn.commit()
            conn.close()
            session.close()
            
            stop_placeholder.empty()
            prog_text.empty()
            prog_bar.empty()
            ui_status.success(f"🎉 **Proces úspěšně dokončen!**\n\nStahování a synchronizace {total_tickets} ticketů proběhla v pořádku.")

    # --- TAB 2: IMPORT EXCELU ---
    with tab2:
        st.markdown("### 📤 Nahrát novou tabulku")
        st.info("Zde můžete nahrát data z Excelu nebo CSV přímo do databáze.")
        uploaded_file = st.file_uploader("Vyberte soubor (.xlsx, .csv)", type=['xlsx', 'xls', 'csv'])
        if uploaded_file:
            clean_name = os.path.splitext(uploaded_file.name)[0].lower().replace(" ", "_").replace("-", "_")
            table_name = st.text_input("Název nové tabulky v DB:", value=clean_name)
            if st.button("💾 Uložit do DB"):
                try:
                    if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
                    else: df = pd.read_excel(uploaded_file)
                    df.columns = [str(c).strip().replace(" ", "_").lower() for c in df.columns]
                    conn = get_db_connection()
                    df.to_sql(table_name, conn, if_exists='replace', index=False)
                    conn.close()
                    st.success(f"✅ Tabulka '{table_name}' vytvořena ({len(df)} řádků).")
                    time.sleep(1); st.rerun()
                except Exception as e: st.error(f"Chyba při importu: {e}")

    # --- TAB 3: POKROČILÁ SPRÁVA TABULEK ---
    with tab3:
        st.markdown("### 🛠️ Pokročilá správa databáze")
        stats_df = get_table_stats()
        
        if not stats_df.empty:
            st.markdown("#### 📊 Přehled tabulek")
            st.dataframe(stats_df, use_container_width=True, hide_index=True)
            st.divider()

            st.markdown("#### ⚙️ Operace s tabulkou")
            target_table = st.selectbox("Vyberte tabulku k úpravám:", stats_df["Table"].tolist())
            
            if target_table:
                conn = get_db_connection()
                schema_df = pd.read_sql(f"PRAGMA table_info({target_table})", conn)
                cols = schema_df['name'].tolist()
                
                sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(["🔍 Prohlížení a Export", "🗑️ Smazat záznamy", "💻 Vlastní SQL", "⚠️ Nebezpečné akce"])
                
                with sub_tab1:
                    st.markdown(f"**Náhled dat v tabulce `{target_table}` (max 1000 řádků):**")
                    try:
                        df_preview = pd.read_sql(f"SELECT * FROM {target_table} LIMIT 1000", conn)
                        st.dataframe(df_preview, use_container_width=True)
                        csv = df_preview.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Stáhnout náhled jako CSV",
                            data=csv,
                            file_name=f"{target_table}_export.csv",
                            mime="text/csv",
                        )
                    except Exception as e:
                        st.error(f"Nelze načíst data: {e}")

                with sub_tab2:
                    st.markdown("**Smazat konkrétní řádek / řádky**")
                    st.info("Vyberte sloupec (typicky ID) a zadejte hodnotu. Všechny řádky, které se shodují, budou smazány.")
                    del_c1, del_c2 = st.columns(2)
                    del_col = del_c1.selectbox("Sloupec:", cols, key="del_col")
                    del_val = del_c2.text_input("Hodnota ke smazání:", key="del_val")
                    
                    if st.button("🗑️ Smazat odpovídající záznamy", type="primary"):
                        if del_val:
                            try:
                                cur = conn.cursor()
                                cur.execute(f"DELETE FROM {target_table} WHERE {del_col} = ?", (del_val,))
                                rows_deleted = cur.rowcount
                                conn.commit()
                                st.success(f"✅ Úspěšně smazáno {rows_deleted} záznamů.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Chyba při mazání: {e}")
                        else:
                            st.warning("Zadejte hodnotu ke smazání.")

                with sub_tab3:
                    st.markdown("**Spustit vlastní SQL dotaz**")
                    st.warning("Zde můžete spouštět raw SQL dotazy (SELECT, UPDATE, DELETE).")
                    sql_query = st.text_area("SQL Dotaz:", value=f"SELECT * FROM {target_table} LIMIT 10")
                    if st.button("▶️ Spustit SQL"):
                        try:
                            if sql_query.strip().upper().startswith("SELECT") or sql_query.strip().upper().startswith("PRAGMA"):
                                sql_df = pd.read_sql(sql_query, conn)
                                st.dataframe(sql_df, use_container_width=True)
                                st.success(f"Nalezeno {len(sql_df)} řádků.")
                            else:
                                cur = conn.cursor()
                                cur.execute(sql_query)
                                conn.commit()
                                st.success(f"✅ Dotaz úspěšně proveden. Ovlivněno řádků: {cur.rowcount}")
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Chyba v SQL dotazu: {e}")

                with sub_tab4:
                    st.markdown("**Hromadné akce s tabulkou**")
                    danger_action = st.radio("Vyberte akci:", ["Vymazat všechna data (TRUNCATE)", "Smazat celou tabulku (DROP)"])
                    if st.button("⚠️ Provést nebezpečnou akci", type="primary"):
                        cur = conn.cursor()
                        try:
                            if "DROP" in danger_action:
                                cur.execute(f"DROP TABLE IF EXISTS {target_table}")
                                st.toast(f"Tabulka {target_table} byla smazána.")
                            else:
                                cur.execute(f"DELETE FROM {target_table}")
                                st.toast(f"Data z tabulky {target_table} byla vymazána.")
                            conn.commit()
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Chyba: {e}")
                            
                conn.close()
        else:
            st.info("Databáze je prázdná.")