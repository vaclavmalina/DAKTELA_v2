import streamlit as st

def show_wip_msg(module_name):
    st.toast(f"🚧 Modul **{module_name}** je momentálně ve vývoji.", icon="🛠️")

def render_main_menu():
    st.markdown("<h1 style='text-align: center; margin-bottom: 75px;'>Balíkobot - Datio</h1>", unsafe_allow_html=True)

    menu_items = [
        {"label": "🔎\nAnalýza ticketů", "action": "a_harvester"},
        {"label": "📊\nStatistiky",      "action": "a_statistics"},
        {"label": "🔄\nDatabáze",        "action": "a_db_update"},
        {"label": "📈\nDashboard",       "action": "Dashboard"},
        {"label": "📑\nReporting",       "action": "Reporting"},
        {"label": "👥\nUživatelé",       "action": "Uživatelé"},
        {"label": "🗄️\nStažení dat",     "action": "a_datadownload"},
        {"label": "⚙️\nNastavení",       "action": "Nastavení"},
        {"label": "❓\nNápověda",        "action": "Nápověda"},
    ]

    rows = [menu_items[i:i+3] for i in range(0, len(menu_items), 3)]
    
    for row in rows:
        cols = st.columns(3)
        for idx, item in enumerate(row):
            with cols[idx]:
                # Unikátní klíč pro každé tlačítko
                if st.button(item["label"], use_container_width=True, key=f"menu_btn_{item['action']}"):
                    
                    # 1. HARVESTER
                    if item["action"] == "a_harvester":
                        st.session_state.current_app = "harvester"
                        st.rerun()
                    
                    # 2. STATISTIKY (OPRAVENO)
                    elif item["action"] == "a_statistics":
                        st.session_state.current_app = "statistics"
                        st.rerun()

                    # 3. DATABÁZE (OPRAVENO)
                    elif item["action"] == "a_db_update":
                        st.session_state.current_app = "db_update"
                        st.rerun()

                    # 4. DOWNLOADER
                    elif item["action"] == "a_datadownload":
                        st.session_state.current_app = "datadownload"
                        st.rerun()
                        
                    # OSTATNÍ (Zobrazí WIP hlášku)
                    else:
                        show_wip_msg(item["label"].replace("\n", " "))
        st.write("")