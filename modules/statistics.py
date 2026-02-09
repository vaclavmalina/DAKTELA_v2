import streamlit as st
import pandas as pd
from modules.statistics_logic import calculate_kpis

def render_statistics():
    # --- Inicializace Session State ---
    if 'uploaded_data' not in st.session_state:
        st.session_state.uploaded_data = {}

    # --- Header ---
    col_back, col_title, col_void = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu", key="stat_back_btn"):
            st.session_state.current_app = "main_menu"
            st.rerun()
            
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📊 Statistiky a Data</h2>", unsafe_allow_html=True)
    st.divider()

    # --- Sekce pro nahrání souborů ---
    st.markdown("### 📤 Správa dat")
    
    uploaded_files = st.file_uploader(
        "Nahrajte jeden nebo více souborů", 
        type=['csv', 'xlsx', 'xls'], 
        accept_multiple_files=True, 
        label_visibility="collapsed"
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
                st.rerun()

        if selected_file in st.session_state.uploaded_data:
            current_df = st.session_state.uploaded_data[selected_file]
            
            # --- VÝPOČET KPI ---
            kpis = calculate_kpis(current_df)
            
            # --- Vykreslení KPI karet (4 sloupce) ---
            st.markdown("### 📈 Klíčové metriky")
            
            # Definujeme 4 sloupce
            kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
            
            with kpi_col1:
                st.metric(label="Počet řádků", value=kpis["row_count"])
            
            with kpi_col2:
                val = kpis["avg_activities"]
                st.metric(label="Prům. počet aktivit", value=val if val is not None else "N/A")

            with kpi_col3:
                val = kpis["avg_response_time"]
                st.metric(label="Prům. doba 1. odp.", value=val if val is not None else "N/A", help="Doba první odpovědi")

            with kpi_col4:
                val = kpis["avg_client_reaction"]
                st.metric(label="Prům. reakce klienta", value=val if val is not None else "N/A", help="Čas reakce klienta na zprávu operátora (pokud reagoval později).")
            
            st.divider()

            # --- Vykreslení Tabulky ---
            st.markdown(f"**Detailní data:** `{selected_file}`")
            
            col_void_l, col_toggle = st.columns([2, 2])
            with col_toggle:
                excel_mode = st.toggle("🖥️ Excel mód (Celá šířka i výška)", value=False)

            if excel_mode:
                st.markdown("""
                    <style>
                        .block-container {
                            max-width: 95% !important;
                            padding: 1rem;
                        }
                    </style>
                """, unsafe_allow_html=True)
                calculated_height = (len(current_df) + 1) * 35 + 3
                table_height = min(calculated_height, 15000)
            else:
                table_height = 600

            st.data_editor(
                current_df,
                use_container_width=True,
                height=table_height,
                num_rows="dynamic",
                key=f"editor_{selected_file}"
            )
    
    else:
        st.info("👋 Zatím nejsou nahrána žádná data. Použijte tlačítko výše.")