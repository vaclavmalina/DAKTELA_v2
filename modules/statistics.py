import streamlit as st
import pandas as pd

def render_statistics():
    # --- Inicializace Session State pro data ---
    # Toto zajistí, že data zůstanou v paměti i po odchodu do menu
    if 'uploaded_data' not in st.session_state:
        st.session_state.uploaded_data = {}  # Slovník: {'nazev_souboru': dataframe}

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
    
    # Uploader pro více souborů
    uploaded_files = st.file_uploader(
        "Nahrajte jeden nebo více souborů (CSV, Excel)", 
        type=['csv', 'xlsx', 'xls'], 
        accept_multiple_files=True,  # Povolit více souborů
        label_visibility="collapsed"
    )

    # Zpracování nově nahraných souborů
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            
            # Pokud soubor ještě nemáme v paměti, nebo byl nahrán znovu, zpracujeme ho
            # (Streamlit uploader při každém rerunu vrací soubory znovu, pokud je uživatel neodstraní z widgetu,
            # proto kontrolujeme, zda už data nemáme, abychom neprocesovali zbytečně, 
            # ale pokud uživatel chce soubor přepsat, musí ho v uploaderu smazat a nahrát znovu)
            
            try:
                if file_name not in st.session_state.uploaded_data:
                    if file_name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    
                    # Uložení do trvalé paměti session_state
                    st.session_state.uploaded_data[file_name] = df
                    st.toast(f"✅ Soubor '{file_name}' byl načten.", icon="saved")
            except Exception as e:
                st.error(f"Chyba u souboru {file_name}: {e}")

    # --- Výběr a zobrazení dat ---
    # Zobrazíme obsah pouze pokud máme v paměti nějaká data
    if len(st.session_state.uploaded_data) > 0:
        
        st.divider()
        
        # Ovládací panel nad tabulkou
        col_select, col_actions = st.columns([3, 1])
        
        with col_select:
            # Roletka pro výběr aktivního souboru
            file_options = list(st.session_state.uploaded_data.keys())
            selected_file = st.selectbox("📂 Vyberte soubor k zobrazení:", file_options)
        
        with col_actions:
            # Tlačítko pro vymazání paměti
            if st.button("🗑️ Smazat vše", use_container_width=True):
                st.session_state.uploaded_data = {}
                st.rerun()

        # Získání DataFrame pro vybraný soubor
        current_df = st.session_state.uploaded_data[selected_file]
        
        st.markdown(f"**Tabulka:** `{selected_file}` ({len(current_df)} řádků)")

        # --- Přepínač zobrazení (Excel mód) ---
        col_label, col_toggle = st.columns([3, 1])
        with col_toggle:
            full_view = st.toggle("Zobrazit celou délku", value=False)

        # Výpočet výšky
        if full_view:
            calculated_height = (len(current_df) + 1) * 35 + 3
            table_height = min(calculated_height, 15000)
        else:
            table_height = 600

        # Zobrazení editoru
        st.data_editor(
            current_df,
            use_container_width=True,
            height=table_height,
            num_rows="dynamic",
            key=f"editor_{selected_file}" # Unikátní klíč pro každý soubor, aby se nemíchaly stavy
        )
    
    else:
        st.info("👋 Zatím nejsou nahrána žádná data. Použijte tlačítko výše.")