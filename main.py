import streamlit as st
from modules import page_harvester, page_mainmenu, page_downloader, page_statistics, page_dbupdate

st.set_page_config(page_title="Balíkobot Data", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""<style>[data-testid="stSidebar"] {display: none;} div[data-testid="column"] button {height: 120px !important; width: 100% !important; border-radius: 12px !important; border: 1px solid #e0e0e0; background-color: #ffffff; color: #31333F; transition: all 0.2s ease-in-out;} div[data-testid="column"] button:hover {border-color: #FF4B4B; color: #FF4B4B; background-color: #fff5f5; transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.1);}</style>""", unsafe_allow_html=True)

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'current_app' not in st.session_state: st.session_state.current_app = "main_menu"

if not st.session_state.authenticated:
    _, col, _ = st.columns([1,2,1])
    with col:
        st.markdown("<h1 style='text-align: center;'>🔒 Přihlášení</h1>", unsafe_allow_html=True)
        with st.form("login"):
            if st.form_submit_button("Vstoupit", use_container_width=True) and st.text_input("Heslo", type="password") == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True; st.rerun()
    st.stop()

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
    st.session_state.current_app = "main_menu"; st.rerun()