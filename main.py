import streamlit as st

# --- 1. HLAVNÍ KONFIGURACE UI (MUSÍ BÝT ÚPLNĚ PRVNÍ) ---
st.set_page_config(
    page_title="Balíkobot - Datio",
    layout="wide",  # 'wide' je pro tabulky a statistiky mnohem lepší než 'centered'
    initial_sidebar_state="expanded", # Výchozí stav sidebaru
    page_icon="🧊"
)

# --- 2. IMPORTY MODULŮ ZE SLOŽKY "modules" ---
try:
    # ZMĚNA: Aktualizace importů podle nových názvů souborů
    from modules.page_mainmenu import render_main_menu
    from modules.page_harvester import render_harvester
    from modules.page_dbupdate import render_db_update
    from modules.page_statistics import render_statistics
except ImportError as e:
    st.error(f"Chyba importu: {e}")
    # ZMĚNA: Aktualizace seznamu souborů v chybové hlášce
    st.info("Ujistěte se, že ve složce 'modules' existují soubory: page_mainmenu.py, page_harvester.py, page_dbupdate.py, page_statistics.py")
    st.stop()

# --- 3. CSS STYLY (Globální) ---
st.markdown("""
    <style>
        /* Skrytí standardní navigace Streamlitu (to chceme, protože máme vlastní menu) */
        [data-testid="stSidebarNav"] {display: none;}
        
        div[data-testid="column"] button {
            height: 120px !important;
            width: 100% !important;
            font-size: 18px !important;
            font-weight: 600 !important;
            border-radius: 12px !important;
            border: 1px solid #e0e0e0;
            background-color: #ffffff;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            transition: all 0.2s ease-in-out;
            color: #31333F;
        }
        div[data-testid="column"] button:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            border-color: #FF4B4B;
            color: #FF4B4B;
            background-color: #fff5f5;
        }
        div[data-testid="column"] button:active {
            transform: translateY(1px);
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        h1 { margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE INICIALIZACE ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'current_app' not in st.session_state:
    st.session_state.current_app = "main_menu"

# --- LOGIN OBRAZOVKA ---
if not st.session_state.authenticated:
    col_main_1, col_main_2, col_main_3 = st.columns([1,2,1])
    with col_main_2:
        st.markdown("<h1 style='text-align: center;'>🔒 Přihlášení</h1>", unsafe_allow_html=True)
        st.write("<p style='text-align: center;'>Pro přístup k Balíkobot data centru zadejte heslo.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            password_input = st.text_input("Heslo", type="password")
            submitted = st.form_submit_button("Přihlásit se", use_container_width=True)

    if submitted:
        # Pozor: Ujisti se, že máš 'APP_PASSWORD' v .streamlit/secrets.toml
        if "APP_PASSWORD" in st.secrets and password_input == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        elif "APP_PASSWORD" not in st.secrets:
             st.warning("Není nastaveno heslo v secrets.toml. (Pro vývoj přeskočeno)")
             st.session_state.authenticated = True
             st.rerun()
        else:
            st.error("Nesprávné heslo.")
    st.stop()

# --- APLIKACE (ROZCESTNÍK) ---
# Tady se rozhoduje, která "obrazovka" se vykreslí
if st.session_state.current_app == "main_menu":
    render_main_menu()

elif st.session_state.current_app == "harvester":
    render_harvester()

elif st.session_state.current_app == "statistics":
    render_statistics()

elif st.session_state.current_app == "db_update":
    render_db_update()