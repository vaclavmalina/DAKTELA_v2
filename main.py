import streamlit as st
# Import všech modulů
from modules import page_harvester, page_mainmenu, page_downloader, page_statistics, page_dbupdate, page_dbview

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Datio", layout="wide", initial_sidebar_state="expanded")

# --- CSS STYLY ---
st.markdown("""
<style>
    div[data-testid="column"] button {
        height: 120px !important; 
        width: 100% !important; 
        border-radius: 12px !important; 
        border: 1px solid #e0e0e0; 
        background-color: #ffffff; 
        color: #31333F; 
        transition: all 0.2s ease-in-out;
    } 
    div[data-testid="column"] button:hover {
        border-color: #FF4B4B; 
        color: #FF4B4B; 
        background-color: #fff5f5; 
        transform: translateY(-2px); 
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# --- PŘIHLAŠOVACÍ OBRAZOVKA ---
if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("""
        <div style='text-align: center;'>
            <h1 style='margin-bottom: 0px; padding-bottom: 0px; white-space: nowrap;'>Balíkobot - 🧬 Datio</h1>
            <p style='color: grey; margin-top: 5px; font-size: 16px;'>Pro přístup do aplikace zadejte heslo.</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            password_input = st.text_input("Heslo", type="password", placeholder="Zadejte přístupové heslo...")
            submit_button = st.form_submit_button("🔓 Vstoupit", type="primary", use_container_width=True)

            if submit_button:
                # Zkuste získat heslo ze secrets, jinak 'admin'
                try:
                    app_password = st.secrets.get("APP_PASSWORD", "admin")
                except:
                    app_password = "admin"

                if password_input == app_password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Špatné heslo.")
    st.stop()

# ==============================================================================
# --- DEFINICE STRÁNEK A NAVIGACE ---
# ==============================================================================

# 1. Vytvoříme objekty stránek
p_home = st.Page(page_mainmenu.render_main_menu, title="Domů", icon="🏠", default=True)

p_analysis = st.Page(page_harvester.render_harvester, title="Analýza ticketů", icon="🔎", url_path="analyza")
p_stats    = st.Page(page_statistics.render_statistics, title="Statistiky", icon="📊", url_path="statistiky")
p_download = st.Page(page_downloader.render_downloader, title="Stažení reportů", icon="🗄️", url_path="download")

p_db_update = st.Page(page_dbupdate.render_db_update, title="Aktualizace DB", icon="🔄", url_path="db-update")
p_db_view   = st.Page(page_dbview.render_db_view,     title="Prohlížeč DB",   icon="💾", url_path="db-view")

# 2. Uložíme mapu stránek do session_state pro použití v page_mainmenu.py
#    Klíče musí odpovídat tomu, co voláme v page_mainmenu.py
st.session_state.page_map = {
    "analyza": p_analysis,
    "statistiky": p_stats,
    "download": p_download,
    "db-update": p_db_update,
    "db-view": p_db_view
}

# 3. Definice struktury menu pro hamburger
pages = {
    "Hlavní panel": [p_home],
    "Nástroje": [p_analysis, p_stats, p_download],
    "Databáze": [p_db_update, p_db_view]
}

# Spuštění navigace
pg = st.navigation(pages)
pg.run()