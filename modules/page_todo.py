import streamlit as st
import json
import os
from datetime import datetime

# ZMĚNA: Cesta k souboru s úkoly (ukládá se do kořenového adresáře jako todos.json)
TODO_FILE = "todos.json"

# ZMĚNA: Pomocné funkce pro načítání a ukládání do souboru
def load_todos():
    if os.path.exists(TODO_FILE):
        try:
            with open(TODO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_todos(todos):
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=4)

def render_todo():
    st.markdown("<h1 style='text-align: center; margin-bottom: 2rem;'>📝 Můj úkolníček</h1>", unsafe_allow_html=True)

    # ZMĚNA: Inicializace úkolů v session state přímo ze souboru
    if 'todos' not in st.session_state:
        st.session_state.todos = load_todos()

    # Formulář pro přidání nového úkolu
    with st.form("new_task_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            new_task = st.text_input("Název úkolu", placeholder="Co je potřeba udělat?...")
        with col2:
            priority = st.selectbox(
                "Priorita", 
                ["MANDATORY", "HIGH", "NORMAL", "NICE TO HAVE", "LOW"],
                index=2
            )
        with col3:
            st.write("") # Odřádkování aby bylo tlačítko zarovnané
            st.write("")
            submitted = st.form_submit_button("➕ Přidat", use_container_width=True)

        if submitted and new_task.strip():
            # Generování jednoduchého unikátního ID
            new_id = 0 if not st.session_state.todos else max(t['id'] for t in st.session_state.todos) + 1
            st.session_state.todos.append({
                "id": new_id,
                "text": new_task.strip(),
                "priority": priority,
                "done": False,
                "done_at": None
            })
            # ZMĚNA: Fyzické uložení do JSONu po přidání úkolu
            save_todos(st.session_state.todos)
            st.rerun()

    st.divider()

    # Filtrace na aktivní a hotové úkoly
    active_tasks = [t for t in st.session_state.todos if not t["done"]]
    completed_tasks = [t for t in st.session_state.todos if t["done"]]

    # --- AKTIVNÍ ÚKOLY ---
    st.subheader("📌 K řešení")
    if not active_tasks:
        st.success("Všechno hotovo! Nemáš tu žádné úkoly.")
    else:
        for task in active_tasks:
            # Rozložení do sloupců: Checkbox | Priorita | Text úkolu
            c_chk, c_prio, c_txt = st.columns([0.5, 1.5, 8])
            
            with c_chk:
                # Při kliknutí na checkbox změníme stav a zaznamenáme čas
                if st.checkbox(" ", key=f"chk_{task['id']}"):
                    task["done"] = True
                    task["done_at"] = datetime.now().strftime("%d.%m.%Y v %H:%M")
                    # ZMĚNA: Fyzické uložení do JSONu po odfajfknutí
                    save_todos(st.session_state.todos)
                    st.rerun()
            
            with c_prio:
                # Nastavení barev pro jednotlivé štítky priorit
                color_map = {
                    "MANDATORY": "#ff4b4b", # Červená
                    "HIGH": "#ff9e4b",      # Oranžová
                    "NORMAL": "#4b7bff",    # Modrá
                    "NICE TO HAVE": "#00cc96", # Zelená
                    "LOW": "#a8a8a8"        # Šedá
                }
                color = color_map.get(task["priority"], "#888888")
                st.markdown(
                    f"<div style='background-color: {color}; color: white; border-radius: 4px; text-align: center; padding: 3px 0px; font-size: 11px; font-weight: bold; margin-top: 6px;'>{task['priority']}</div>", 
                    unsafe_allow_html=True
                )
                
            with c_txt:
                st.markdown(f"<div style='margin-top: 6px; font-size: 16px;'>{task['text']}</div>", unsafe_allow_html=True)

    st.divider()

    # --- HOTOVÉ ÚKOLY ---
    st.subheader("✅ Hotovo")
    if not completed_tasks:
        st.caption("Zatím nemáš odfajfknuté žádné úkoly.")
    else:
        # Seřadíme hotové úkoly od nejnověji vyřešených
        for task in sorted(completed_tasks, key=lambda x: x["done_at"], reverse=True):
            st.markdown(
                f"<span style='color: grey;'>~~{task['text']}~~</span> <span style='font-size: 12px; color: #a8a8a8;'>— Vyřešeno: {task['done_at']} (<i>{task['priority']}</i>)</span>", 
                unsafe_allow_html=True
            )
            
        st.write("")
        # Tlačítko na úplné promazání hotových úkolů z paměti
        if st.button("🗑️ Promazat hotové úkoly"):
            st.session_state.todos = [t for t in st.session_state.todos if not t["done"]]
            # ZMĚNA: Fyzické uložení do JSONu po smazání historie
            save_todos(st.session_state.todos)
            st.rerun()