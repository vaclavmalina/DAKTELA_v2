import streamlit as st
import pandas as pd
from modules.statistics_logic import calculate_kpis

def render_statistics():
    # --- 1. CSS ÚPRAVA (Excel mód vždy zapnutý + oprava useknutého vršku) ---
    st.markdown("""
        <style>
            .block-container {
                max-width: 95% !important;
                padding-top: 5rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-bottom: 1rem !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # --- Inicializace Session State ---
    if 'uploaded_data' not in st.session_state:
        st.session_state.uploaded_data = {}
    
    # ZMĚNA: Inicializace klíče pro resetování uploaderu
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
    
    # ZMĚNA: Přidán dynamický klíč 'key=f"uploader_{...}"', který zajistí vyprázdnění komponenty při smazání
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
                # ZMĚNA: Inkrementace klíče donutí file_uploader k resetu (zahození cache souborů)
                st.session_state.uploader_key += 1
                st.rerun()

        if selected_file in st.session_state.uploaded_data:
            current_df = st.session_state.uploaded_data[selected_file]
            
            # --- VÝPOČET KPI ---
            kpis = calculate_kpis(current_df)
            
            # --- Vykreslení KPI karet (4 sloupce) ---
            st.markdown("### 📈 Klíčové metriky")
            
            kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
            
            # 1. Počet řádků
            with kpi_col1:
                st.metric(label="Počet řádků", value=kpis["row_count"])
            
            # 2. Průměrný počet aktivit
            with kpi_col2:
                val = kpis["avg_activities"]
                if val is not None:
                    st.metric(label="Prům. počet aktivit", value=val, help="Průměrný počet aktivit na jeden ticket.")
                else:
                    st.metric(label="Prům. počet aktivit", value="N/A", help="⚠️ Data nejsou k dispozici. V souboru chybí sloupec 'Počet aktivit'.")

            # 3. Průměrná doba první odpovědi
            with kpi_col3:
                val = kpis["avg_response_time"]
                if val is not None:
                    st.metric(label="Prům. doba 1. odp.", value=val, help="Průměrný čas od vytvoření ticketu do první odpovědi operátora.")
                else:
                    st.metric(label="Prům. doba 1. odp.", value="N/A", help="⚠️ Data nejsou k dispozici. V souboru chybí sloupec 'Doba první odpovědi'.")

            # 4. Průměrná reakce klienta
            with kpi_col4:
                val = kpis["avg_client_reaction"]
                if val is not None:
                    st.metric(label="Prům. reakce klienta", value=val, help="Průměrný čas, za který klient odpoví na zprávu operátora.")
                else:
                    st.metric(label="Prům. reakce klienta", value="N/A", help="⚠️ Data nejsou k dispozici. Chybí potřebné sloupce časů nebo nebyla nalezena žádná reakce klienta po operátorovi.")
            
            st.divider()

            # --- Vykreslení Tabulky (Bez slideru) ---
            st.markdown(f"**Detailní data:** `{selected_file}`")
            
            # ZMĚNA: Omezení maximální výšky na 800px. 
            # Příliš vysoké hodnoty (50000) způsobují chyby vykreslování (tabulka zmizí).
            # Nyní se zobrazí scrollbar uvnitř tabulky, pokud je dat hodně.
            calculated_height = (len(current_df) + 1) * 35 + 3
            table_height = min(calculated_height, 800)

            st.data_editor(
                current_df,
                use_container_width=True,
                height=table_height,
                num_rows="dynamic",
                key=f"editor_{selected_file}"
            )
    
    else:
        st.info("👋 Zatím nejsou nahrána žádná data. Použijte tlačítko výše.")