import streamlit as st
import pandas as pd

def render_statistics():
    # --- Header ---
    col_back, col_title, col_void = st.columns([1, 4, 1])
    with col_back:
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
            # Načtení dat
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            st.success(f"✅ Soubor **{uploaded_file.name}** byl úspěšně nahrán ({len(df)} řádků).")
            
            # --- Zobrazení dat v tabulce ---
            st.divider()
            
            col_label, col_toggle = st.columns([3, 1])
            with col_label:
                st.subheader("📋 Data (Excel mód)")
            with col_toggle:
                # Přepínač pro zobrazení celé tabulky
                full_view = st.toggle("Zobrazit celou délku", value=False)

            # --- Logika pro výšku tabulky ---
            if full_view:
                # Výpočet výšky: počet řádků * 35px + 38px na hlavičku (přibližně)
                # Omezíme to na max 15000px, aby prohlížeč nespadl u obřích dat
                calculated_height = (len(df) + 1) * 35 + 3
                table_height = min(calculated_height, 15000) 
            else:
                table_height = 600  # Fixní výška s posuvníkem

            # Používáme data_editor místo dataframe - vypadá a chová se jako Excel
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                height=table_height,
                num_rows="dynamic", # Umožní přidávat/mazat řádky
                key="data_editor"
            )

            # Volitelně: Pokud chceš pracovat s upravenými daty
            # st.write("Počet aktuálních řádků:", len(edited_df))

        except Exception as e:
            st.error(f"❌ Došlo k chybě při zpracování souboru: {e}")