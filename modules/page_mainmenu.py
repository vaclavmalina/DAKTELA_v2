import streamlit as st

def show_wip(name):
    st.toast(f"🚧 Modul {name} je ve vývoji.", icon="🛠️")

def render_main_menu():
    st.markdown("<h1 style='text-align: center; margin-bottom: 50px;'>Balíkobot - Datio</h1>", unsafe_allow_html=True)

    # Definice menu - DŮLEŽITÉ: 'id' musí odpovídat podmínkám v main.py
    menu = [
        {"label": "🔎\nAnalýza ticketů", "id": "harvester"},
        {"label": "📊\nStatistiky",      "id": "statistics"},
        {"label": "🔄\nDatabáze",        "id": "db_update"},
        {"label": "🗄️\nStažení dat",     "id": "downloader"},
        {"label": "📈\nDashboard",       "id": "dashboard_wip"},
        {"label": "📑\nReporting",       "id": "reporting_wip"},
        {"label": "👥\nUživatelé",       "id": "users_wip"},
        {"label": "⚙️\nNastavení",       "id": "settings_wip"},
        {"label": "❓\nNápověda",        "id": "help_wip"},
    ]

    # Vykreslení mřížky 3x3
    rows = [menu[i:i+3] for i in range(0, len(menu), 3)]
    for row in rows:
        cols = st.columns(3)
        for idx, item in enumerate(row):
            with cols[idx]:
                if st.button(item["label"], use_container_width=True, key=f"btn_{item['id']}"):
                    
                    # Logika přepnutí
                    if item["id"] in ["harvester", "statistics", "db_update", "downloader"]:
                        st.session_state.current_app = item["id"]
                        st.rerun()
                    else:
                        show_wip(item["label"].replace("\n", " "))
        st.write("")