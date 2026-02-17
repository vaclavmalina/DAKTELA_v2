import streamlit as st

def render_main_menu():
    # Nadpis s větším odsazením zespodu, aby se "nedusil" na tlačítkách
    st.markdown("<h1 style='text-align: center; margin-bottom: 60px;'>Balíkobot - 🧬 Datio</h1>", unsafe_allow_html=True)

    # Definice pouze aktivních modulů
    menu = [
        {"label": "🔎 Analýza ticketů", "id": "harvester", "help": "Vyhledávání a filtrace ticketů"},
        {"label": "📊 Statistiky",      "id": "statistics", "help": "Přehledy a grafy"},
        {"label": "🔄 Aktualizace DB",  "id": "db_update",  "help": "Synchronizace dat z Daktely"},
        {"label": "🗄️ Stažení dat",     "id": "downloader", "help": "Export do Excelu/CSV"},
    ]

    # Layout: Použijeme sloupce [1, 2, 1] pro vycentrování.
    # Prostřední sloupec (šířka 2) bude obsahovat tlačítka.
    _, col, _ = st.columns([1, 2, 1])

    with col:
        for item in menu:
            # Vykreslení tlačítka
            if st.button(item["label"], use_container_width=True, key=f"btn_{item['id']}", help=item.get("help")):
                st.session_state.current_app = item["id"]
                st.rerun()
            
            # ELEGANTNÍ MEZERA
            # Místo prázdného řádku vložíme neviditelný blok s výškou 15px
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)