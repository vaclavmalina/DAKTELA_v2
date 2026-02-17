import streamlit as st
from modules import page_harvester, page_mainmenu, page_downloader, page_statistics, page_dbupdate

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Balíkobot Data", layout="centered", initial_sidebar_state="collapsed")

# --- CSS STYLY ---
st.markdown("""
<style>
    /* Skrytí postranního panelu */
    [data-testid="stSidebar"] {display: none;} 
    
    /* Stylování dlaždicových tlačítek v menu */
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

# --- SESSION STATE ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'current_app' not in st.session_state: st.session_state.current_app = "main_menu"

# --- PŘIHLAŠOVACÍ OBRAZOVKA ---
if not st.session_state.authenticated:
    
    # 1. NADPIS (Mimo sloupce = plná šířka = nebude se lámat)
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("""
        <div style='text-align: center;'>
            <h1 style='margin-bottom: 0px; padding-bottom: 0px; white-space: nowrap;'>Balíkobot - 🧬 Datio</h1>
            <p style='color: grey; margin-top: 5px; font-size: 16px;'>Pro přístup do aplikace zadejte heslo.</p>
        </div>
    """, unsafe_allow_html=True)

    # 2. FORMULÁŘ (Ve sloupcích = úzký uprostřed)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            # Pole pro heslo
            password_input = st.text_input("Heslo", type="password", placeholder="Zadejte přístupové heslo...")
            
            # Tlačítko pro odeslání
            submit_button = st.form_submit_button("🔓 Vstoupit", type="primary", use_container_width=True)

            # Logika
            if submit_button:
                if password_input == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Špatné heslo.")
    
    st.stop()

# --- ROUTOVÁNÍ APLIKACE (běží až po přihlášení) ---
app = st.session_state.current_app

if app == "main_menu":
    page_mainmenu.render_main_menu()
elif app == "harvester":
    page_harvester.render_harvester()
elif app == "downloader":
    page_downloader.render_downloader()
elif app == "statistics":
    page_statistics.render_statistics()
elif app == "db_update":
    page_dbupdate.render_db_update()
else:
    st.session_state.current_app = "main_menu"
    st.rerun()