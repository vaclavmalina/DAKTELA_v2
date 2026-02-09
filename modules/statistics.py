import streamlit as st
import pandas as pd

def render_statistics():
    # --- Inicializace Session State pro data ---
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
        "Nahrajte jeden nebo více souborů (CSV, Excel)", 
        type=['csv', 'xlsx', 'xls'], 
        accept_multiple_files=True, 
        label_visibility="collapsed"
    )

    # Zpracování nově nahraných souborů
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            try:
                # Načteme soubor pouze pokud chceme (jednoduchá logika)
                if file_name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.session_state.uploaded_data[file_name] = df
                
                # Toast notifikace s opravou emoji
                st.toast(f"Soubor '{file_name}' byl úspěšně načten.", icon="✅")
                
            except Exception as e:
                st.error(f"Chyba u souboru {file_name}: {e}")

    # --- Výběr a zobrazení dat ---
    if len(st.session_state.uploaded_data) > 0:
        
        st.divider()
        
        # Ovládací panel nad tabulkou
        col_select, col_actions = st.columns([3, 1])
        
        with col_select:
            file_options = list(st.session_state.uploaded_data.keys())
            selected_file = st.selectbox("📂 Vyberte soubor k zobrazení:", file_options)
        
        with col_actions:
            if st.button("🗑️ Smazat vše", use_container_width=True):
                st.session_state.uploaded_data = {}
                st.rerun()

        if selected_file in st.session_state.uploaded_data:
            current_df = st.session_state.uploaded_data[selected_file]
            
            st.markdown(f"**Tabulka:** `{selected_file}` ({len(current_df)} řádků)")

            # --- OVLÁDÁNÍ ZOBRAZENÍ (ŠÍŘKA + VÝŠKA) ---
            col_label, col_toggle = st.columns([2, 2])
            with col_toggle:
                # Přepínač pro "Excel mód" (Full Width + Full Height)
                excel_mode = st.toggle("🖥️ Excel mód", value=False)

            # Logika pro nastavení rozměrů
            if excel_mode:
                # 1. CSS Injection pro roztažení stránky do šířky
                # Toto přepíše 'layout="centered"' z main.py jen pro tento moment
                st.markdown("""
                    <style>
                        .block-container {
                            max-width: 95% !important;
                            padding-top: 1rem;
                            padding-right: 1rem;
                            padding-left: 1rem;
                            padding-bottom: 1rem;
                        }
                    </style>
                """, unsafe_allow_html=True)

                # 2. Výpočet dynamické výšky
                calculated_height = (len(current_df) + 1) * 35 + 3
                table_height = min(calculated_height, 15000)
            else:
                # Výchozí stav (Centrované, fixní výška s posuvníkem)
                table_height = 600

            # Zobrazení editoru
            st.data_editor(
                current_df,
                use_container_width=True, # Toto zajistí, že se tabulka roztáhne do kontejneru
                height=table_height,
                num_rows="dynamic",
                key=f"editor_{selected_file}"
            )
    
    else:
        st.info("👋 Zatím nejsou nahrána žádná data. Použijte tlačítko výše.")