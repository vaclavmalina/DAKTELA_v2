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

def render_downloader():
    # --- HEADER & NAVIGACE ---
    col_back, col_title, _ = st.columns([1, 4, 1])
    with col_back:
        # Tlačítko pro návrat do menu
        if st.button("⬅️ Menu", key="dl_menu_btn"):
            st.session_state.current_app = "main_menu"
            st.rerun()
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📊 Export Dat (XLSX)</h2>", unsafe_allow_html=True)
    st.divider()

    # --- INPUTY ---
    
    # 1. Datum
    c1, c2 = st.columns(2)
    d_from = c1.date_input("Datum od (včetně 00:00)", value=date.today() - timedelta(days=7), key="exp_d_from")
    d_to = c2.date_input("Datum do (včetně 23:59)", value=date.today(), key="exp_d_to")

    # 2. Sloupce
    available_fields = ["name", "title", "created", "edited", "last_activity", "category", "user", "statuses"]
    default_fields = ["name", "title", "created", "last_activity"]
    selected_fields = st.multiselect("Vyberte sloupce k exportu", options=available_fields, default=default_fields, key="exp_fields")

    # 3. Kategorie (Načtení a výběr)
    cat_options = {"VŠE (bez filtru)": None}
    
    # Cache pro kategorie
    if 'categories_cache' not in st.session_state:
        try:
            cat_res = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
            if cat_res.status_code == 200:
                st.session_state['categories_cache'] = {c['title']: c['name'] for c in cat_res.json().get('result', {}).get('data', [])}
        except: pass
    
    if 'categories_cache' in st.session_state:
        cat_options.update(st.session_state['categories_cache'])
    
    selected_cat_label = st.selectbox("Filtr kategorie", options=list(cat_options.keys()), key="exp_cat")
    selected_cat_id = cat_options[selected_cat_label]

    st.divider()

    # --- LOGIKA STAHOVÁNÍ ---
    if st.button("🚀 Načíst data a připravit export", type="primary", use_container_width=True, key="exp_start_btn"):
        if not ACCESS_TOKEN or not INSTANCE_URL:
            st.error("Chybí konfigurace URL nebo Tokenu v secrets.toml.")
            st.stop()
            
        status_box = st.status("Zahajuji komunikaci s API...", expanded=True)
        
        all_data = []
        skip = 0
        take = 1000 # Daktela limit
        
        # Sestavení filtrů
        params = {
            "filter[logic]": "and",
            "filter[filters][0][field]": "created",
            "filter[filters][0][operator]": "gte",
            "filter[filters][0][value]": f"{d_from} 00:00:00",
            "filter[filters][1][field]": "created",
            "filter[filters][1][operator]": "lte",
            "filter[filters][1][value]": f"{d_to} 23:59:59",
            "take": take,
            "skip": skip
        }

        # Filtr 2: Kategorie
        filter_index = 2
        if selected_cat_id:
            params[f"filter[filters][{filter_index}][field]"] = "category"
            params[f"filter[filters][{filter_index}][operator]"] = "eq"
            params[f"filter[filters][{filter_index}][value]"] = selected_cat_id

        # Fields parametry
        fields_to_request = list(set(selected_fields + ["name"])) 
        for i, field in enumerate(fields_to_request):
            params[f"fields[{i}]"] = field

        # SMYČKA PRO STRÁNKOVÁNÍ
        while True:
            params['skip'] = skip
            try:
                resp = requests.get(f"{INSTANCE_URL}/api/v6/tickets.json", params=params, headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
                resp.raise_for_status()
                
                json_data = resp.json()
                result = json_data.get('result', {})
                data_batch = result.get('data', [])
                total_records = result.get('total', 0)
                
                if not data_batch:
                    break
                
                # Flattening objektů (např. category: {name:..., title:...} -> category_title)
                cleaned_batch = []
                for item in data_batch:
                    clean_item = item.copy()
                    # Úprava vnořených objektů pro hezčí Excel
                    if isinstance(item.get('category'), dict):
                        clean_item['category'] = item['category'].get('title', '')
                    if isinstance(item.get('user'), dict):
                        clean_item['user'] = item['user'].get('title', '')
                    if isinstance(item.get('statuses'), list) and item['statuses']:
                         clean_item['statuses'] = ", ".join([s.get('title','') for s in item['statuses']])
                    cleaned_batch.append(clean_item)

                all_data.extend(cleaned_batch)
                
                status_box.write(f"📥 Staženo {len(all_data)} / {total_records} záznamů...")
                
                if len(all_data) >= total_records:
                    break
                
                skip += take
                time.sleep(0.1)
                
            except Exception as e:
                status_box.update(label="❌ Chyba při stahování", state="error")
                st.error(f"Chyba API: {str(e)}")
                st.stop()

        status_box.update(label="✅ Data úspěšně stažena", state="complete", expanded=False)
        
        if not all_data:
            st.warning("V daném období nebyla nalezena žádná data.")
        else:
            df = pd.DataFrame(all_data)
            # Filtrování sloupců
            final_cols = [c for c in selected_fields if c in df.columns]
            df = df[final_cols]

            st.success(f"Nalezeno celkem {len(df)} záznamů.")
            
            with st.expander("👀 Náhled dat", expanded=True):
                st.dataframe(df.head(10))
            
            # Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Report')
            
            st.download_button(
                label=f"📥 Stáhnout XLSX ({len(df)} řádků)",
                data=buffer.getvalue(),
                file_name=f"daktela_export_{d_from}_{d_to}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )