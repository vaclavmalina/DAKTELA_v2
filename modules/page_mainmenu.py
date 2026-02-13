import streamlit as st

def show_wip_msg(module_name):
    st.toast(f"🚧 Modul **{module_name}** je momentálně ve vývoji.", icon="🛠️")

def render_main_menu():
    st.markdown("<h1 style='text-align: center; margin-bottom: 75px;'>Balíkobot - Datio</h1>", unsafe_allow_html=True)

    menu_items = [
        {"label": "🔎\nAnalýza ticketů", "action": "a_harvester"},
        {"label": "📊\nStatistiky",      "action": "a_statistics"},
        {"label": "🔄\nDatabáze",     "action": "a_db_update"},
        {"label": "📈\nDashboard",       "action": "Dashboard"},
        {"label": "📑\nReporting",       "action": "Reporting"},
        {"label": "👥\nUživatelé",       "action": "Uživatelé"},
        {"label": "🗄️\Stažení dat",          "action": "a_datadownload"},
        {"label": "⚙️\nNastavení",       "action": "Nastavení"},
        {"label": "❓\nNápověda",        "action": "Nápověda"},
    ]

    # Rozdělení do řádků po 3 sloupcích
    rows = [menu_items[i:i+3] for i in range(0, len(menu_items), 3)]
    
    for row in rows:
        cols = st.columns(3)
        for idx, item in enumerate(row):
            with cols[idx]:
                # Přidán parametr 'key', aby Streamlit bezpečně rozeznal každé tlačítko
                if st.button(item["label"], use_container_width=True, key=f"menu_btn_{item['action']}"):
                    
                    # 1. HARVESTER
                    if item["action"] == "a_harvester":
                        st.session_state.current_app = "harvester"
                        st.rerun()
                    
                    # 2. STATISTIKY (směruje na page_statistics)
                    elif item["action"] == "a_statistics":
                        st.session_state.current_app = "statistics"
                        st.rerun()

                    # 3. Databáze (směruje na page_dbupdate)
                    elif item["action"] == "a_db_update":
                        st.session_state.current_app = "db_update"
                        st.rerun()

                     # 4. Data (směruje na page_datadownload)
                    elif item["action"] == "a_datadownload":
                        st.session_state.current_app = "datadownload"
                        st.rerun()
                        
                    # OSTATNÍ (Zatím nefunkční)
                    else:
                        show_wip_msg(item["action"])
        st.write("") # Mezera mezi řádky