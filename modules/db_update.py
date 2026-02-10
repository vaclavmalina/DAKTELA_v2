import streamlit as st
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
import time
from bs4 import BeautifulSoup

# --- KONFIGURACE ---
# Načtení ze secrets, nebo fallback
try:
    INSTANCE_URL = st.secrets["DAKTELA_URL"]
    ACCESS_TOKEN = st.secrets["DAKTELA_TOKEN"]
except:
    INSTANCE_URL = "" # Doplňte případně natvrdo pro test
    ACCESS_TOKEN = ""

DB_FILE = "daktela_data.db"

# --- POMOCNÉ FUNKCE ---

def clean_daktela_html(html_content):
    """Odstraní HTML tagy, styly a skripty, ale zachová text a odřádkování."""
    if not html_content or not isinstance(html_content, str):
        return ""
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Odstraníme bordel (CSS, JS, hlavičky)
    for script_or_style in soup(['script', 'style', 'head', 'title', 'meta']):
        script_or_style.decompose()

    # Nahradíme <br> a <p> za konce řádků
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all("p"):
        p.append("\n")

    text = soup.get_text(separator="\n")
    
    # Vyčištění prázdných řádků
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)

def init_db():
    """Inicializuje databázi a tabulky, pokud neexistují."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Tabulka Tickets (Metadata)
    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY,
            title TEXT,
            category TEXT,
            user TEXT,
            created_at TIMESTAMP,
            edited_at TIMESTAMP,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabulka Activities (Obsah)
    c.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            activity_id TEXT PRIMARY KEY,
            ticket_id INTEGER,
            time TIMESTAMP,
            type TEXT,
            sender TEXT,
            text_body TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
        )
    ''')
    conn.commit()
    return conn

def get_db_ticket_map():
    """Vrátí slovník {ticket_id: edited_at} pro rychlé porovnání existujících dat."""
    conn = init_db()
    try:
        df = pd.read_sql("SELECT ticket_id, edited_at FROM tickets", conn)
        if df.empty:
            return {}
        return dict(zip(df.ticket_id, df.edited_at))
    except:
        return {}
    finally:
        conn.close()

# --- HLAVNÍ RENDER FUNKCE ---
def render_db_update():
    # --- HEADER (Tlačítko Zpět + Nadpis) ---
    col_back, col_title, col_void = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu", key="db_menu_btn"):
            st.session_state.current_app = "main_menu"
            st.rerun()
            
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📥 Stažení dat</h2>", unsafe_allow_html=True)
    
    st.divider()

    # --- INPUTY ---
    st.info("Tento nástroj synchronizuje data z Daktely do lokální databáze. Stahuje pouze nové nebo upravené tickety.")
    
    col1, col2, col3 = st.columns(3)
    # Defaultně poslední měsíc
    default_start = date.today() - timedelta(days=30)
    
    d_from = col1.date_input("Datum od (edited)", value=default_start)
    d_to = col2.date_input("Datum do (edited)", value=date.today())
    cat_id = col3.text_input("ID Kategorie", value="categories_62a076bf7abc6412427206", help="ID kategorie z URL Daktely")

    st.write("") # Mezera

    # --- LOGIKA TLAČÍTKA ---
    if st.button("🚀 Spustit synchronizaci", type="primary", use_container_width=True):
        
        if not ACCESS_TOKEN or not INSTANCE_URL:
            st.error("Chybí konfigurace (URL nebo Token). Zkontrolujte secrets.toml.")
            st.stop()

        # 1. Získání seznamu ticketů (Metadata)
        status_box = st.status("Krok 1: Získávám seznam ticketů...", expanded=True)
        
        params = {
            "filter[logic]": "and",
            "filter[filters][0][field]": "edited",
            "filter[filters][0][operator]": "gte",
            "filter[filters][0][value]": f"{d_from} 00:00:00",
            "filter[filters][1][field]": "edited",
            "filter[filters][1][operator]": "lte",
            "filter[filters][1][value]": f"{d_to} 23:59:59",
            "filter[filters][2][field]": "category",
            "filter[filters][2][operator]": "eq",
            "filter[filters][2][value]": cat_id,
            "fields[0]": "name",
            "fields[1]": "title",
            "fields[2]": "created",
            "fields[3]": "edited",
            "fields[4]": "category",
            "fields[5]": "user",
            "take": 1000 # Pro jednoduchost bez while cyklu (max 1000 změněných v období)
        }

        try:
            res = requests.get(f"{INSTANCE_URL}/api/v6/tickets.json", params=params, headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
            res.raise_for_status()
            api_tickets = res.json().get("result", {}).get("data", [])
            status_box.write(f"✅ API vrátilo {len(api_tickets)} záznamů v zadaném období.")
        except Exception as e:
            status_box.update(label="❌ Chyba při komunikaci s API", state="error")
            st.error(f"Detail chyby: {e}")
            st.stop()

        # 2. Filtrace (Smart Sync)
        status_box.write("Krok 2: Porovnávám s databází (hledám změny)...")
        db_map = get_db_ticket_map()
        tickets_to_process = []

        for t in api_tickets:
            t_id = t['name']
            api_edited = t['edited']
            
            # Pokud v DB není NEBO pokud je v API novější datum editace
            if t_id not in db_map or str(api_edited) > str(db_map[t_id]):
                tickets_to_process.append(t)
        
        if not tickets_to_process:
            status_box.update(label="✅ Hotovo! Databáze je aktuální.", state="complete", expanded=False)
            st.success("Žádné nové změny k uložení.")
            st.stop()

        status_box.write(f"🔍 Nalezeno **{len(tickets_to_process)}** ticketů k aktualizaci.")
        status_box.update(label=f"⬇️ Stahuji {len(tickets_to_process)} ticketů...", state="running", expanded=True)

        # 3. Stahování detailů a ukládání
        progress_bar = st.progress(0)
        conn = init_db()
        cursor = conn.cursor()
        
        counter = 0
        total = len(tickets_to_process)

        for t in tickets_to_process:
            t_id = t['name']
            t_title = t.get('title', 'Bez názvu')
            
            # Bezpečné získání vnořených hodnot
            t_cat = t.get('category', {}).get('title') if isinstance(t.get('category'), dict) else str(t.get('category'))
            t_user = t.get('user', {}).get('title') if isinstance(t.get('user'), dict) else str(t.get('user'))
            
            # A) Upsert Ticketu
            cursor.execute('''
                INSERT OR REPLACE INTO tickets (ticket_id, title, category, user, created_at, edited_at, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (t_id, t_title, t_cat, t_user, t.get('created'), t.get('edited')))

            # B) Stažení aktivit
            try:
                act_res = requests.get(f"{INSTANCE_URL}/api/v6/tickets/{t_id}/activities.json", headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
                if act_res.status_code == 200:
                    activities = act_res.json().get("result", {}).get("data", [])
                    
                    # Smazat staré aktivity tohoto ticketu (full refresh pro ticket)
                    cursor.execute("DELETE FROM activities WHERE ticket_id = ?", (t_id,))
                    
                    for act in activities:
                        # Čištění HTML
                        raw_text = act.get('description') or act.get('text') or ""
                        clean_text = clean_daktela_html(raw_text)
                        
                        # Získání odesílatele
                        sender = "System"
                        if act.get('user'):
                            sender = act['user'].get('title', 'Unknown Agent')
                        elif act.get('item') and act['item'].get('address'):
                             sender = act['item'].get('address')
                        
                        cursor.execute('''
                            INSERT INTO activities (activity_id, ticket_id, time, type, sender, text_body)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (act['name'], t_id, act['time'], act.get('type'), sender, clean_text))
                
                conn.commit() # Uložíme po každém ticketu
                
            except Exception as e:
                print(f"Chyba u ticketu {t_id}: {e}")
            
            counter += 1
            progress_bar.progress(counter / total)
            time.sleep(0.05) # Malá pauza pro API

        conn.close()
        status_box.update(label="🎉 Hotovo! Data byla uložena.", state="complete", expanded=False)
        st.success(f"Úspěšně zpracováno {total} ticketů.")

        # Zobrazení náhledu dat
        with st.expander("👀 Náhled uložených dat (posledních 10 aktivit)"):
            conn = init_db()
            df = pd.read_sql("SELECT * FROM activities ORDER BY time DESC LIMIT 10", conn)
            st.dataframe(df)
            conn.close()