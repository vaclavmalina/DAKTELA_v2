import streamlit as st
import requests
import pandas as pd
from datetime import timedelta, date
import time
import io

# --- KONFIGURACE ---
try:
    INSTANCE_URL = st.secrets["DAKTELA_URL"]
    ACCESS_TOKEN = st.secrets["DAKTELA_TOKEN"]
except:
    INSTANCE_URL = "" 
    ACCESS_TOKEN = ""

def get_headers():
    return {"X-AUTH-TOKEN": ACCESS_TOKEN, "Content-Type": "application/json"}

# --- POMOCNÉ FUNKCE PRO NAČÍTÁNÍ ČÍSELNÍKŮ ---

def fetch_categories():
    if 'categories_cache' not in st.session_state:
        try:
            resp = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers=get_headers())
            if resp.status_code == 200:
                data = resp.json().get('result', {}).get('data', [])
                st.session_state['categories_cache'] = {c['title']: str(c['name']) for c in data}
        except: pass
    return st.session_state.get('categories_cache', {})

def fetch_queues():
    if 'queues_cache' not in st.session_state:
        try:
            resp = requests.get(f"{INSTANCE_URL}/api/v6/queues.json", headers=get_headers())
            if resp.status_code == 200:
                data = resp.json().get('result', {}).get('data', [])
                st.session_state['queues_cache'] = {q['title']: str(q['name']) for q in data if q.get('title')}
        except: pass
    return st.session_state.get('queues_cache', {})

def fetch_users():
    if 'users_cache' not in st.session_state:
        try:
            resp = requests.get(f"{INSTANCE_URL}/api/v6/users.json", headers=get_headers())
            if resp.status_code == 200:
                data = resp.json().get('result', {}).get('data', [])
                st.session_state['users_cache'] = {u['title']: u['name'] for u in data if u.get('title')}
        except: pass
    return st.session_state.get('users_cache', {})

# --- POMOCNÁ FUNKCE PRO ČIŠTĚNÍ HODNOT (LIST -> STR) ---
def format_value(val):
    if isinstance(val, list):
        return ", ".join([str(x.get('title', x)) if isinstance(x, dict) else str(x) for x in val])
    if isinstance(val, dict):
        return val.get('title', str(val))
    return val

# --- HLAVNÍ RENDER ---

def render_downloader():
    if 'stop_download' not in st.session_state:
        st.session_state.stop_download = False

    col_back, col_title, _ = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu", key="dl_menu_btn"):
            st.session_state.current_app = "main_menu"; st.rerun()
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📊 Export Dat</h2>", unsafe_allow_html=True)
    st.divider()

    if not ACCESS_TOKEN or not INSTANCE_URL:
        st.error("Chybí konfigurace v secrets.toml."); st.stop()

    agenda_type = st.selectbox("Vyberte typ dat k exportu:", ["🎫 Tickety", "📞 Hovory", "🔄 Obojí"], index=0)

    c1, c2 = st.columns(2)
    default_start = date.today() - timedelta(days=1) if "Hovory" in agenda_type else date.today() - timedelta(days=7)
    d_from = c1.date_input("Datum od", value=default_start)
    d_to = c2.date_input("Datum do", value=date.today())

    download_tasks = []
    users_db = fetch_users()

    # KONFIGURACE TICKETY
    if "Tickety" in agenda_type or "Obojí" in agenda_type:
        st.markdown("### 🎫 Nastavení pro Tickety")
        # Definice polí pro API request
        t_api_fields = ["name", "created", "user", "last_activity", "title", "priority", "stage", "customFields"]
        # Definice sloupců pro zobrazení/excel (včetně rozbalených customFields)
        t_display_cols = ["name", "created", "user", "last_activity", "title", "priority", "stage", "VIP", "DEV_TASK_1", "DEV_TASK_2"]
        
        selected_display = st.multiselect("Sloupce (Tickety)", options=t_display_cols, default=t_display_cols)
        
        cats = fetch_categories()
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            t_sel_c = st.multiselect("Filtrovat kategorie", options=list(cats.keys()), key="t_cats_ms")
        with col_t2:
            t_sel_u = st.multiselect("Filtrovat uživatele", options=list(users_db.keys()), key="t_users_ms")
        
        download_tasks.append({
            "name": "Tickety", "endpoint": "tickets", "date_field": "created", 
            "fields": t_api_fields, "final_cols": selected_display,
            "filter_groups": [
                {"field": "category", "ids": [cats[l] for l in t_sel_c]},
                {"field": "user", "ids": [users_db[l] for l in t_sel_u]}
            ]
        })

    # KONFIGURACE HOVORY
    if "Hovory" in agenda_type or "Obojí" in agenda_type:
        st.markdown("### 📞 Nastavení pro Hovory")
        c_api_fields = ["id_call", "call_time", "direction", "id_queue", "id_agent", "duration", "answered"]
        selected_display = st.multiselect("Sloupce (Hovory)", options=c_api_fields, default=c_api_fields)
        
        queues = fetch_queues()
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            c_sel_q = st.multiselect("Filtrovat fronty", options=list(queues.keys()), key="c_queues_ms")
        with col_f2:
            c_sel_u = st.multiselect("Filtrovat agenty", options=list(users_db.keys()), key="c_users_ms")
            
        download_tasks.append({
            "name": "Hovory", "endpoint": "activitiesCall", "date_field": "call_time", 
            "fields": c_api_fields, "final_cols": selected_display,
            "filter_groups": [
                {"field": "id_queue", "ids": [queues[l] for l in c_sel_q]},
                {"field": "id_agent", "ids": [users_db[l] for l in c_sel_u]}
            ]
        })

    st.divider()

    col_btn, col_stop = st.columns([3, 1])
    start_btn = col_btn.button("🚀 Spustit hromadný export", type="primary", use_container_width=True)
    
    if start_btn:
        st.session_state.stop_download = False
        final_dfs = {}
        status_container = st.status("Zahajuji stahování...", expanded=True)
        
        stop_placeholder = st.empty()
        if stop_placeholder.button("🛑 Zastavit stahování", key="stop_btn_active"):
            st.session_state.stop_download = True

        for task in download_tasks:
            if st.session_state.stop_download: break
            all_data, skip, take = [], 0, 1000
            
            while True:
                if st.session_state.stop_download: break

                params = {
                    "filter[logic]": "and",
                    "filter[filters][0][field]": task['date_field'], 
                    "filter[filters][0][operator]": "gte", "filter[filters][0][value]": f"{d_from} 00:00:00",
                    "filter[filters][1][field]": task['date_field'], 
                    "filter[filters][1][operator]": "lte", "filter[filters][1][value]": f"{d_to} 23:59:59",
                    "take": take, "skip": skip
                }
                
                for group_idx, group in enumerate(task['filter_groups'], start=2):
                    if group['ids']:
                        if len(group['ids']) == 1:
                            params[f"filter[filters][{group_idx}][field]"] = group['field']
                            params[f"filter[filters][{group_idx}][operator]"] = "eq"
                            params[f"filter[filters][{group_idx}][value]"] = group['ids'][0]
                        else:
                            params[f"filter[filters][{group_idx}][logic]"] = "or"
                            for val_idx, val in enumerate(group['ids']):
                                params[f"filter[filters][{group_idx}][filters][{val_idx}][field]"] = group['field']
                                params[f"filter[filters][{group_idx}][filters][{val_idx}][operator]"] = "eq"
                                params[f"filter[filters][{group_idx}][filters][{val_idx}][value]"] = val
                
                for i, f in enumerate(task['fields']):
                    params[f"fields[{i}]"] = f

                try:
                    resp = requests.get(f"{INSTANCE_URL}/api/v6/{task['endpoint']}.json", params=params, headers=get_headers())
                    resp.raise_for_status()
                    res_json = resp.json().get('result', {})
                    batch = res_json.get('data', [])
                    total = res_json.get('total', 0)
                    
                    if not batch: break
                    
                    for item in batch:
                        row = item.copy()
                        
                        # --- ROZBALENÍ CUSTOM FIELDS (Pouze pro Tickety) ---
                        if task['name'] == "Tickety" and 'customFields' in item:
                            cf = item['customFields'] if isinstance(item['customFields'], dict) else {}
                            row['VIP'] = format_value(cf.get('vip', ""))
                            row['DEV_TASK_1'] = format_value(cf.get('note', ""))
                            row['DEV_TASK_2'] = format_value(cf.get('dev_task_2', ""))
                            del row['customFields']

                        # --- OBECNÉ ZPLOŠTĚNÍ OSTATNÍCH POLÍ ---
                        for k, v in row.items():
                            if k not in ['VIP', 'DEV_TASK_1', 'DEV_TASK_2']: # Tyto už jsme zpracovali
                                row[k] = format_value(v)
                        
                        all_data.append(row)

                    status_container.update(label=f"📥 Stahuji {task['name']}: {len(all_data)} / {total} záznamů...")
                    if len(all_data) >= total or len(batch) < take: break
                    skip += take
                    time.sleep(0.05)
                except Exception as e:
                    st.error(f"Chyba u {task['name']}: {e}"); break

            if all_data and not st.session_state.stop_download:
                df = pd.DataFrame(all_data)
                # Vybereme jen ty sloupce, které uživatel chtěl a které v DF reálně existují
                cols_to_keep = [c for c in task['final_cols'] if c in df.columns]
                final_dfs[task['name']] = df[cols_to_keep]

        stop_placeholder.empty()

        if st.session_state.stop_download:
            status_container.update(label="🛑 Zastaveno.", state="error", expanded=False)
        elif not final_dfs:
            status_container.update(label="❌ Žádná data.", state="error", expanded=False)
        else:
            status_container.update(label="✅ Hotovo.", state="complete", expanded=False)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                for sheet_name, df in final_dfs.items():
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
                    ws = writer.sheets[sheet_name]
                    for i, col in enumerate(df.columns):
                        ws.set_column(i, i, max(len(str(col)), 18))
            
            st.success("Export připraven!")
            st.download_button(label="💾 STÁHNOUT EXCEL (XLSX)", data=buffer.getvalue(), file_name=f"daktela_export_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)