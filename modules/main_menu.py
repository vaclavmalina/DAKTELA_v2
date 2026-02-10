import streamlit as st

def show_wip_msg(module_name):
    st.toast(f"🚧 Modul **{module_name}** je momentálně ve vývoji.", icon="🛠️")

def render_main_menu():
    st.markdown("<h1 style='text-align: center; margin-bottom: 75px;'>Balíkobot - Datio", unsafe_allow_html=True)

    menu_items = [
        {"label": "🔎\nAnalýza ticketů", "action": "harvester"},
        {"label": "📊\nStatistiky",      "action": "Statistiky"},
        {"label": "📈\nDashboard",       "action": "Dashboard"},
        {"label": "📑\nReporting",       "action": "Reporting"},
        {"label": "👥\nUživatelé",       "action": "Uživatelé"},
        {"label": "🔄\nAutomatizace",    "action": "Automatizace"},
        {"label": "🗄️\nArchiv",          "action": "Archiv"},
        {"label": "⚙️\nNastavení",       "action": "Nastavení"},
        {"label": "❓\nNápověda",        "action": "Nápověda"},
    ]

    rows = [menu_items[i:i+3] for i in range(0, len(menu_items), 3)]
    for row in rows:
        cols = st.columns(3)
        for idx, item in enumerate(row):
            with cols[idx]:
                if st.button(item["label"], use_container_width=True):
                    
                    # Logika pro Harvester
                    if item["action"] == "harvester":
                        st.session_state.current_app = "harvester"
                        st.rerun()
                    
                    # ZMĚNA: Přidána logika pro Statistiky
                    elif item["action"] == "Statistiky":
                        st.session_state.current_app = "statistics"
                        st.rerun()
                        
                    # Ostatní tlačítka (WIP)
                    else:
                        show_wip_msg(item["action"])
        st.write("")