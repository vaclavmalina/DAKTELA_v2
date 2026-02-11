import streamlit as st
import pandas as pd
import datetime
import os
# Ujisti se, že logic_statistics.py je aktualizovaný a přijímá user_list/priority_list/kwargs
from modules.logic_statistics import calculate_kpis, filter_data 

# --- HELPER FUNKCE ---
def select_all(key, options): st.session_state[key] = options
def clear_all(key): st.session_state[key] = []

def load_local_files():
    """Automaticky načte soubory ze složky data/excel."""
    local_path = "data/excel"
    if os.path.exists(local_path):
        files = [f for f in os.listdir(local_path) if f.endswith(('.csv', '.xlsx', '.xls'))]
        for file_name in files:
            if file_name not in st.session_state.uploaded_data:
                full_path = os.path.join(local_path, file_name)
                try:
                    if file_name.endswith('.csv'): df = pd.read_csv(full_path)
                    else: df = pd.read_excel(full_path)
                    st.session_state.uploaded_data[file_name] = df
                except: pass

# --- UNIVERZÁLNÍ FUNKCE PRO VYKRESLENÍ FILTRŮ ---
def render_standard_filters(df, filter_columns):
    """
    Vykreslí datum (pokud existuje sloupec data) a sadu multiselect filtrů.
    Vrací slovník { 'NazevSloupce': [vybrane_hodnoty], 'date_range': (od, do) }
    """
    filters = {}
    
    # 1. CHYTRÉ HLEDÁNÍ DATA
    # Rozšířený seznam možných názvů
    possible_date_cols = [
        "Vytvořeno", "Datum", "Date", "Created", "Time", "Čas", 
        "timestamp", "Timestamp", "Datum vytvoření", "Vytvořeno dne", "Day"
    ]
    
    # Zkusíme najít sloupec podle názvu
    date_col = next((c for c in possible_date_cols if c in df.columns), None)

    # Pokud nenajdeme podle názvu, zkusíme najít podle datového typu (datetime)
    if not date_col:
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                date_col = col
                break

    if date_col:
        try:
            # Převedeme na datetime pro jistotu
            dates = pd.to_datetime(df[date_col], errors='coerce').dropna()
            
            if not dates.empty:
                mn, mx = dates.min().date(), dates.max().date()
                st.subheader(f"📅 Datum ({date_col})")
                
                if mn == mx:
                    st.info(f"Data pouze z: {mn}")
                    filters["date_range"] = (mn, mx)
                else:
                    # Tady je ten posuvník
                    filters["date_range"] = st.slider(
                        "", 
                        min_value=mn, 
                        max_value=mx, 
                        value=(mn, mx), 
                        format="DD.MM",
                        key=f"slider_{date_col}" # Unikátní klíč
                    )
            else:
                 # Sloupec existuje, ale po konverzi je prázdný
                 pass
        except Exception as e:
            st.warning(f"Chyba při zpracování data ({date_col}): {e}")

    # 2. OSTATNÍ SPECIFICKÉ FILTRY (Carrier, Priority, atd.)
    for label, col_name in filter_columns.items():
        if col_name in df.columns:
            try:
                # Získání unikátních hodnot (ošetření seznamů oddělených čárkou)
                raw = df[col_name].dropna().astype(str)
                unq = set()
                for x in raw: unq.update([i.strip() for i in x.split(',') if i.strip()])
                opts = sorted(list(unq))
                
                key_prefix = f"filter_{col_name}"
                st.subheader(label)
                c1, c2 = st.columns(2)
                c1.button("Vše", key=f"all_{key_prefix}", on_click=select_all, args=(key_prefix, opts))
                c2.button("Nic", key=f"none_{key_prefix}", on_click=clear_all, args=(key_prefix,))
                
                sel = st.multiselect("", opts, default=opts, key=key_prefix, label_visibility="collapsed")
                filters[col_name] = sel
            except: pass
            
    return filters

def render_statistics():
    # --- CSS ---
    st.markdown("""
        <style>
            .block-container { padding-top: 2rem !important; }
            section[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
            [data-testid="stSidebar"] hr { margin: 0.5rem 0 !important; }
            [data-testid="stSidebar"] h3 { font-size: 13px !important; margin-bottom: -5px !important; padding-top: 5px !important; }
            [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
                background: transparent; border: 1px solid rgba(128,128,128,0.2);
                color: rgba(49, 51, 63, 0.6); font-size: 10px; padding: 0 5px; height: 22px; width: 100%; min-height: 0px;
            }
            [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:hover {
                border-color: #FF4B4B; color: #FF4B4B; background: rgba(255, 75, 75, 0.05);
            }
            .stToggle { margin-top: -5px; }
        </style>
    """, unsafe_allow_html=True)

    # --- INIT ---
    if 'uploaded_data' not in st.session_state: st.session_state.uploaded_data = {}
    if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
    if 'datasets' not in st.session_state: st.session_state.datasets = {}
    
    # --- DATASOURCE CONFIG ---
    DATA_SOURCE_PATH = "data/excel"
    DATA_MAPPING = {
        "Daktela": ["Daktela", "daktela"],
        "Hotline": ["HL", "hl", "Hotline"],
        "Broken Order": ["BO", "bo", "Broken"],
        "Zásilky": ["Packages", "packages", "Zasilky"]
    }

    # --- LOAD DATA ---
    if os.path.exists(DATA_SOURCE_PATH):
        files = [f for f in os.listdir(DATA_SOURCE_PATH) if f.endswith(('.csv', '.xlsx', '.xls'))]
        for category, keywords in DATA_MAPPING.items():
            matched_file = next((f for f in files if any(k in f for k in keywords)), None)
            if matched_file and category not in st.session_state.datasets:
                full_path = os.path.join(DATA_SOURCE_PATH, matched_file)
                try:
                    if matched_file.endswith('.csv'): df = pd.read_csv(full_path)
                    else: df = pd.read_excel(full_path)
                    st.session_state.datasets[category] = {"filename": matched_file, "data": df}
                except: pass

    # --- SIDEBAR ---
    with st.sidebar:
        if st.button("⬅️ Zpět do Menu", use_container_width=True, type="primary"):
            st.session_state.current_app = "main_menu"; st.rerun()
        st.divider()
        
        st.header("📂 Výběr agendy")
        available_cats = list(st.session_state.datasets.keys())
        if not available_cats: st.warning("Žádná data v 'data/excel'."); st.stop()
        
        # Default index na Daktelu (pokud tam je), jinak 0
        idx = 3 if "Daktela" in available_cats else 0
        if idx >= len(available_cats): idx = 0
        
        selected_agenda = st.radio("Dataset:", options=list(DATA_MAPPING.keys()), index=3, key="agenda")
        
        if selected_agenda in st.session_state.datasets:
            st.caption(f"`{st.session_state.datasets[selected_agenda]['filename']}`")
        else:
            st.warning("Soubor nenalezen.")

    # --- MAIN ---
    col_tit, _ = st.columns([3, 1])
    with col_tit: st.markdown(f"## 📊 Statistiky: {selected_agenda}")
    
    if selected_agenda not in st.session_state.datasets:
        st.info(f"Pro kategorii **{selected_agenda}** nebyl ve složce `data/excel` nalezen soubor."); return

    df = st.session_state.datasets[selected_agenda]["data"]
    filtered_df = df.copy()

    # ========================== FILTROVÁNÍ PODLE AGENDY ==========================
    with st.sidebar:
        st.divider()
        st.header("🔍 Filtry")
        
        # --- A) DAKTELA ---
        if selected_agenda == "Daktela":
            # 1. Standardní filtry
            daktela_extra_cols = {
                "📂 Kategorie": "Kategorie",
                "🚨 Priorita": "Priorita",
                "👤 Uživatel": "Uživatel"
            }
            filters = render_standard_filters(df, daktela_extra_cols)
            
            # 2. Statusy (Extra logika)
            sel_stats = None; stat_mode = 'any'
            if "Statusy" in df.columns:
                raw = df["Statusy"].dropna().astype(str); unq = set()
                for x in raw: unq.update([i.strip() for i in x.split(',') if i.strip()])
                opts = sorted(list(unq))
                st.subheader("📌 Statusy"); c1, c2 = st.columns(2)
                c1.button("Vše", key="s_all", on_click=select_all, args=("stat_dk", opts))
                c2.button("Nic", key="s_none", on_click=clear_all, args=("stat_dk",))
                sel_stats = st.multiselect("", opts, default=opts, key="stat_dk", label_visibility="collapsed")
                if st.toggle("Přesná shoda", key="tg_stat"): stat_mode = 'exact'

            # 3. VIP (Extra logika)
            sel_vip = None
            if "VIP" in df.columns:
                st.subheader("⭐ VIP")
                if st.toggle("Jen VIP", key="tg_vip"): sel_vip = ["→ VIP KLIENT ←"]

            # Aplikace filtrů Daktela
            filtered_df = filter_data(
                df, 
                date_range=filters.get("date_range"), # Datum z univerzální funkce
                status_list=sel_stats,
                vip_list=sel_vip,
                status_match_mode=stat_mode,
                # Dynamické argumenty
                Kategorie=filters.get("Kategorie"),
                Priorita=filters.get("Priorita"),
                Uživatel=filters.get("Uživatel")
            )

        # --- B) HOTLINE & BROKEN ORDER ---
        elif selected_agenda in ["Hotline", "Broken Order"]:
            # Definice sloupců pro filtry
            hl_bo_cols = {
                "🚚 Carrier": "Carrier",
                "⚠️ Příčina chyby": "Příčina chyby",
                "🚨 Priority": "Priority", 
                "📌 Stav úkolu": "Stav úkolu",
                "👤 Reporter": "Reporter",
                "💻 Resolver IT": "Resolver IT",
                "📞 Resolver TP": "Resolver TP"
            }
            
            # Vykreslení (Datum + Tyto sloupce)
            filters = render_standard_filters(df, hl_bo_cols)
            
            # Aplikace filtrů (Datum + zbytek jako kwargs)
            kwargs_filters = {k: v for k, v in filters.items() if k != "date_range"}
            
            filtered_df = filter_data(
                df,
                date_range=filters.get("date_range"),
                **kwargs_filters
            )

        # --- C) ZÁSILKY (PACKAGES) ---
        elif selected_agenda == "Zásilky":
            # Jen datum
            # Tady se funkce render_standard_filters postará o nalezení sloupce s datem
            filters = render_standard_filters(df, {}) 
            
            filtered_df = filter_data(
                df,
                date_range=filters.get("date_range")
            )

    # --- VÝSLEDKY ---
    if selected_agenda == "Daktela":
        kpis = calculate_kpis(filtered_df)
        st.markdown(f"### 📈 Metriky ({len(filtered_df)} / {len(df)})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Počet ticketů", kpis["row_count"])
        c2.metric("Aktivity/ticket", kpis["avg_activities"] or "N/A")
        c3.metric("Doba 1. odp.", kpis["avg_response_time"] or "N/A")
        c4.metric("Reakce klienta", kpis["avg_client_reaction"] or "N/A")
    else:
        # Pro ostatní zatím jen počet
        st.markdown(f"### 📈 Přehled ({len(filtered_df)} / {len(df)})")
        st.metric("Počet záznamů", len(filtered_df))

    st.divider()
    st.markdown(f"**Data:** `{st.session_state.datasets[selected_agenda]['filename']}`")
    
    if not filtered_df.empty:
        st.data_editor(filtered_df, use_container_width=True, height=600, key=f"table_{selected_agenda}")
    else:
        st.warning("⚠️ Žádná data neodpovídají filtrům.")