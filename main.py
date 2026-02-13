import streamlit as st
from modules import page_harvester
from modules import page_mainmenu
from modules import page_downloader
from modules import page_statistics

# --- HLAVNÍ KONFIGURACE UI ---
st.set_page_config(
    page_title="Balíkobot - Datio",
    layout="centered",
    initial_sidebar_state="collapsed",
    page_icon="🧊"
)

# --- CSS STYLY ---
st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stSidebarNav"] {display: none;}
        div[data-testid="column"] button {
            height: 120px !important; width: 100% !important;
            font-size: 18px !important; font-weight: 600 !important;
            border-radius: 12px !important; border: 1px solid #e0e0e0;
            background-color: #ffffff; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            color: #31333F; transition: all 0.2s ease-in-out;
        }
        div[data-testid="column"] button:hover {
            transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            border-color: #FF4B4B; color: #FF4B4B; background-color: #fff5f5;
        }
        h1 { margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'current_app' not in st.session_state: st.session_state.current_app = "main_menu"

# --- LOGIN ---
if not st.session_state.authenticated:
    col_main_1, col_main_2, col_main_3 = st.columns([1,2,1])
    with col_main_2:
        st.markdown("<h1 style='text-align: center;'>🔒 Přihlášení</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
            password_input = st.text_input("Heslo", type="password")
            submitted = st.form_submit_button("Přihlásit se", use_container_width=True)

    if submitted:
        if password_input == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Nesprávné heslo.")
    st.stop()

# --- APLIKACE (ROZCESTNÍK) ---
# Voláme funkce z naimportovaných modulů s prefixem page_
if st.session_state.current_app == "main_menu":
    page_mainmenu.render_main_menu()

elif st.session_state.current_app == "harvester":
    page_harvester.render_harvester()

elif st.session_state.current_app == "datadownload":
    # Tady voláme funkci z page_downloader.py
    page_downloader.render_downloader()

# Pro ostatní zatím WIP nebo přesměrování
else:
    st.info(f"Modul {st.session_state.current_app} je ve vývoji.")
    if st.button("Zpět"):
        st.session_state.current_app = "main_menu"
        st.rerun()