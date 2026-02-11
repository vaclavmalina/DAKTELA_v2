import streamlit as st
import pandas as pd
import datetime
# ZMĚNA: Import z nově přejmenovaného souboru 'logic_statistics.py'
from modules.logic_statistics import calculate_kpis, filter_data 

# --- HELPER FUNKCE PRO TLAČÍTKA VŠE/NIC ---
def select_all(key, options):
    st.session_state[key] = options

def clear_all(key):
    st.session_state[key] = []

def render_statistics():
    # --- 1. CSS ÚPRAVA ---
    st.markdown("""
        <style>
            .block-container {
                max-width: 95% !important;
                padding-top: 2rem !important; 
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-bottom: 1rem !important;
            }
            /* Zmenšení mezer mezi tlačítky v sidebaru */
            .stButton button {
                padding: 0.25rem 0.5rem;
                font-size: 0.8rem;
            }
        </style>
    """, unsafe_allow_html=True)

    # --- Inicializace Session State ---
    if 'uploaded_data' not in st.session_state:
        st.session_state.uploaded_data = {}
    
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0

    # --- Header ---
    col_back, col_title, col_void = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu", key="stat_back_btn"):
            st.session_state.current_app = "main_menu"
            st.rerun()
            
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📊 Statistiky a data</h2>", unsafe_allow_html=True)
    st.divider()

    # --- Sekce pro nahrání souborů ---
    st.markdown("### 📤 Správa dat")
    
    uploaded_files = st.file_uploader(
        "📂 Klikněte pro výběr souborů nebo je přetáhněte sem (CSV, Excel)", 
        type=['csv', 'xlsx', 'xls'], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            try:
                if file_name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.session_state.uploaded_data[file_name] = df
                st.toast(f"Soubor '{file_name}' byl úspěšně načten.", icon="✅")
                
            except Exception as e:
                st.error(f"Chyba u souboru {file_name}: {e}")

    # --- Výběr a zobrazení dat ---
    if len(st.session_state.uploaded_data) > 0:
        
        st.divider()
        
        col_select, col_actions = st.columns([3, 1], vertical_alignment="bottom")
        
        with col_select:
            file_options = list(st.session_state.uploaded_data.keys())
            selected_file = st.selectbox("📂 Vyberte soubor k zobrazení:", file_options)
        
        with col_actions:
            if st.button("🗑️ Smazat vše", use_container_width=True):
                st.session_state.uploaded_data = {}
                st.session_state.uploader_key += 1
                st.rerun()

        if selected_file in st.session_state.uploaded_data:
            current_df = st.session_state.uploaded_data[selected_file]
            
            # --- SIDEBAR FILTRY ---
            with st.sidebar:
                st.header("🔍 Filtrování dat")
                st.caption(f"Soubor: {selected_file}")
                st.divider()

                # --- 1. Filtr Datum (SLIDER) ---
                selected_date_range = None
                if "Vytvořeno" in current_df.columns:
                    try:
                        temp_dates = pd.to_datetime(current_df["Vytvořeno"], errors='coerce').dropna()
                        if not temp_dates.empty:
                            min_date = temp_dates.min().date()
                            max_date = temp_dates.max().date()
                            
                            st.subheader("📅 Datum (Posuvník)")
                            # Pokud je jen jedno datum, slider nefunguje jako range, ošetříme to
                            if min_date == max_date:
                                st.info(f"Data jsou pouze ze dne: {min_date}")
                                selected_date_range = (min_date, max_date)
                            else:
                                selected_date_range = st.slider(
                                    "Vyberte období:",
                                    min_value=min_date,
                                    max_value=max_date,
                                    value=(min_date, max_date),
                                    format="DD.MM.YYYY"
                                )
                    except:
                        st.warning("Chyba při čtení data.")
                else:
                    st.info("Sloupec 'Vytvořeno' chybí.")
                
                st.divider()

                # --- 2. Filtr Statusy ---
                selected_statuses = None
                status_match_mode = 'any' # Default

                if "Statusy" in current_df.columns:
                    try:
                        # Extrakt unikátních statusů + ŘAZENÍ A-Z
                        raw_statuses = current_df["Statusy"].dropna().astype(str)
                        unique_statuses_set = set()
                        for row_val in raw_statuses:
                            parts = row_val.split(',')
                            for part in parts:
                                clean_status = part.strip()
                                if clean_status: unique_statuses_set.add(clean_status)
                        
                        unique_statuses = sorted(list(unique_statuses_set))
                        
                        st.subheader("📌 Statusy")
                        
                        # Tlačítka Vše / Nic
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Vše", key="stat_all"): select_all("filter_statuses", unique_statuses)
                        if c2.button("❌ Nic", key="stat_none"): clear_all("filter_statuses")

                        # Multiselect s klíčem v session state
                        selected_statuses = st.multiselect(
                            "Vyberte:", 
                            unique_statuses, 
                            default=unique_statuses, # Defaultně vše, nebo prázdné list, dle preference
                            key="filter_statuses"
                        )

                        # Volba logiky hledání
                        st.caption("Režim hledání:")
                        mode_selection = st.radio(
                            "Režim statusů",
                            options=["Obsahuje alespoň jeden", "Přesná shoda kombinace"],
                            index=0,
                            label_visibility="collapsed"
                        )
                        status_match_mode = 'exact' if mode_selection == "Přesná shoda kombinace" else 'any'

                    except Exception as e:
                        st.warning(f"Chyba: {e}")
                else:
                    st.info("Sloupec 'Statusy' chybí.")

                st.divider()

                # --- 3. Filtr VIP ---
                selected_vip = None
                if "VIP" in current_df.columns:
                    unique_vip = sorted(current_df["VIP"].dropna().unique().astype(str))
                    st.subheader("⭐ VIP")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("✅ Vše", key="vip_all"): select_all("filter_vip", unique_vip)
                    if c2.button("❌ Nic", key="vip_none"): clear_all("filter_vip")

                    selected_vip = st.multiselect(
                        "Vyberte:", 
                        unique_vip, 
                        default=unique_vip,
                        key="filter_vip"
                    )

                st.divider()

                # --- 4. Filtr Kategorie ---
                selected_categories = None
                if "Kategorie" in current_df.columns:
                    unique_cats = sorted(current_df["Kategorie"].dropna().unique().astype(str))
                    st.subheader("📂 Kategorie")

                    c1, c2 = st.columns(2)
                    if c1.button("✅ Vše", key="cat_all"): select_all("filter_cat", unique_cats)
                    if c2.button("❌ Nic", key="cat_none"): clear_all("filter_cat")

                    selected_categories = st.multiselect(
                        "Vyberte:", 
                        unique_cats, 
                        default=unique_cats,
                        key="filter_cat"
                    )

            # --- APLIKACE FILTRU NA DATA ---
            filtered_df = filter_data(
                current_df, 
                date_range=selected_date_range,
                status_list=selected_statuses,
                vip_list=selected_vip,
                category_list=selected_categories,
                status_match_mode=status_match_mode # Posíláme novou logiku
            )

            # --- VÝPOČET KPI ---
            kpis = calculate_kpis(filtered_df)
            
            # --- Vykreslení KPI ---
            st.markdown(f"### 📈 Klíčové metriky (Zobrazeno {len(filtered_df)} z {len(current_df)} řádků)")
            
            kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
            
            with kpi_col1:
                st.metric(label="Počet řádků", value=kpis["row_count"])
            
            with kpi_col2:
                val = kpis["avg_activities"]
                if val is not None:
                    st.metric(label="Prům. počet aktivit", value=val, help="Průměrný počet aktivit na jeden ticket.")
                else:
                    st.metric(label="Prům. počet aktivit", value="N/A")

            with kpi_col3:
                val = kpis["avg_response_time"]
                if val is not None:
                    st.metric(label="Prům. doba 1. odp.", value=val)
                else:
                    st.metric(label="Prům. doba 1. odp.", value="N/A")

            with kpi_col4:
                val = kpis["avg_client_reaction"]
                if val is not None:
                    st.metric(label="Prům. reakce klienta", value=val)
                else:
                    st.metric(label="Prům. reakce klienta", value="N/A")
            
            st.divider()

            # --- Vykreslení Tabulky ---
            st.markdown(f"**Detailní data:** `{selected_file}`")
            
            if not filtered_df.empty:
                calculated_height = (len(filtered_df) + 1) * 35 + 3
                table_height = min(calculated_height, 800)

                st.data_editor(
                    filtered_df,
                    use_container_width=True,
                    height=table_height,
                    num_rows="dynamic",
                    key=f"editor_{selected_file}"
                )
            else:
                st.warning("⚠️ Pro zvolené filtry nebyla nalezena žádná data.")
    
    else:
        st.info("👋 Zatím nejsou nahrána žádná data. Použijte tlačítko výše.")