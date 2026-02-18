import streamlit as st

def render_main_menu():
    # Header sekce s uvítáním
    st.markdown("<h1 style='text-align: center; margin-bottom: 10px;'>Balíkobot - 🧬 Datio</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray; margin-bottom: 50px;'>Vítejte v centrálním rozcestníku. Zvolte modul pro pokračování.</p>", unsafe_allow_html=True)

    # Definice modulů (přidal jsem 'icon' pro vizuální efekt)
    menu = [
        {
            "label": "Analýza ticketů", 
            "page": "analyza", 
            "icon": "🔎",
            "desc": "Vyhledávání, filtrace a AI analýza ticketů."
        },
        {
            "label": "Statistiky", 
            "page": "statistiky", 
            "icon": "📊",
            "desc": "Grafy, přehledy a trendy v datech."
        },
        {
            "label": "Stažení reportů", 
            "page": "download", 
            "icon": "🗄️",
            "desc": "Export dat do Excelu a CSV."
        },
        {
            "label": "Aktualizace DB", 
            "page": "db-update", 
            "icon": "🔄",
            "desc": "Synchronizace dat z Daktely do lokální DB."
        },
        {
            "label": "Prohlížeč DB", 
            "page": "db-view", 
            "icon": "💾",
            "desc": "Přímý náhled do tabulek a kontrola dat."
        },
    ]

    # --- GRID LAYOUT (3 sloupce) ---
    # Vypočítáme řádky, abychom mohli iterovat
    cols = st.columns(3)
    
    for i, item in enumerate(menu):
        # Vybereme sloupec (0, 1, 2) podle indexu
        col = cols[i % 3]
        
        with col:
            # Vytvoříme kartu s rámečkem
            with st.container(border=True):
                # Ikona a Nadpis
                st.markdown(f"### {item['icon']} {item['label']}")
                
                # Popis (výška min-height zajistí, že karty budou stejně vysoké i při různě dlouhém textu)
                st.markdown(f"<div style='min-height: 40px; color: grey; font-size: 0.9em;'>{item['desc']}</div>", unsafe_allow_html=True)
                
                st.write("") # Mezera
                
                # Tlačítko přes celou šířku karty
                if st.button("Otevřít ➡️", key=f"btn_{item['page']}", use_container_width=True):
                    target_page = st.session_state.page_map.get(item["page"])
                    if target_page:
                        st.switch_page(target_page)
                    else:
                        st.error("Modul nenalezen.")