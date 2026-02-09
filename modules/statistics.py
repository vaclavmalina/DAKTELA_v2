import streamlit as st
import pandas as pd

def render_statistics():
    # --- Header ---
    col_back, col_title, col_void = st.columns([1, 4, 1])
    with col_back:
        # Tlačítko pro návrat do menu
        if st.button("⬅️ Menu", key="stat_back_btn"):
            st.session_state.current_app = "main_menu"
            st.rerun()
            
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📊 Statistiky a Data</h2>", unsafe_allow_html=True)
    st.divider()

    # --- Sekce pro nahrání souboru ---
    st.markdown("### 📤 Nahrání dat")
    st.write("Nahrajte soubor pro analýzu (podporované formáty: **CSV, Excel**)")
    
    uploaded_file = st.file_uploader("Vyberte soubor", type=['csv', 'xlsx', 'xls'], label_visibility="collapsed")

    if uploaded_file is not None:
        try:
            # Načtení dat dle přípony souboru
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            st.success(f"✅ Soubor **{uploaded_file.name}** byl úspěšně nahrán.")
            
            # --- Zobrazení dat v tabulce ---
            st.divider()
            st.subheader("📋 Náhled dat")
            
            # Interaktivní tabulka (umožňuje řazení a roztahování sloupců)
            st.dataframe(df, use_container_width=True, height=600)

        except Exception as e:
            st.error(f"❌ Došlo k chybě při zpracování souboru: {e}")