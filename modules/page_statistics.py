import streamlit as st
import pandas as pd
import datetime
import os
import altair as alt
from modules.logic_statistics import calculate_kpis, filter_data 

# --- KONFIGURACE ---
CARRIER_MAPPING = {
    'intime': 'WeDo InTime', 'inpost': 'InPost', 'dhlde': 'DHL DE', 'gls': 'GLS',
    'tnt': 'TNT', 'zasilkovna': 'Zásilkovna', 'sps': 'SPS (Slovak Parcel Service)',
    'dhlparcel': 'DHL Parcel', 'dachser': 'Dachser', 'dhlfreightec': 'DHL Freight EuroConnect',
    'airway': 'Airway', 'ppl': 'PPL', 'qdl': 'QDL', 'spring': 'Spring', 'ups': 'UPS',
    'dbschenker': 'DB Schenker', 'raben': 'Raben', 'gwcz': 'Gebrüder Weiss CZ',
    'sameday': 'Sameday', 'sp': 'Slovenská pošta', 'ulozenka': 'WEDO Uloženka',
    'dhl': 'DHL Express', 'liftago': 'Kurýr na přesný čas (Liftago)',
    'gw': 'Gebrüder Weiss SK', 'pbh': 'Pošta bez hranic', 'geis_cargo': 'Geis',
    'ppl_cargo': 'PPL Cargo', 'toptrans': 'TopTrans', 'fedex': 'FedEx', 'japo': 'JAPO',
    'messenger': 'Messenger', 'sds': 'SDS (Slovenský Doručovací Systém)',
    'dsv': 'DSV', 'fofr': 'FOFR', 'magyarposta': 'Maďarská pošta', 'dpd': 'DPD',
    'cp': 'Česká pošta'
}

# --- CALLBACK PRO RESET ---
def reset_filters_callback():
    """
    Callback funkce, která se zavolá PŘED přenačtením stránky.
    Maže stav slideru a filtrů, ale ZACHOVÁVÁ výběr grafu.
    """
    keys_to_delete = []
    for key in st.session_state.keys():
        # 1. Smazat slider (tím se vynutí návrat na min/max hodnoty)
        if key == "slider_main_date":
            keys_to_delete.append(key)
        
        # 2. Smazat filtry v sidebaru a togly
        if key.startswith(("filter_", "stat_", "tg_")):
            keys_to_delete.append(key)
        
        # 3. DŮLEŽITÉ: Klíč "graph_carrier_select" NEMAŽEME.
        # Tím zajistíme, že uživatelův výběr (např. jen PPL) zůstane aktivní i po resetu dat.

    for k in keys_to_delete:
        del st.session_state[k]

def select_all(key, options): st.session_state[key] = options
def clear_all(key): st.session_state[key] = []

def clean_column_name(col_name):
    return str(col_name).replace('\ufeff', '').replace("'", "").replace('"', "").strip()

def load_local_files():
    local_path = "data/excel"
    if os.path.exists(local_path):
        files = [f for f in os.listdir(local_path) if f.endswith(('.csv', '.xlsx', '.xls'))]
        for file_name in files:
            if file_name not in st.session_state.uploaded_data:
                full_path = os.path.join(local_path, file_name)
                try:
                    if file_name.endswith('.csv'): 
                        df = pd.read_csv(full_path, sep=',', engine='python', encoding='utf-8-sig')
                    else: 
                        df = pd.read_excel(full_path)
                    
                    df.columns = [clean_column_name(c) for c in df.columns]

                    if "Packages" in file_name or "packages" in file_name:
                        df.rename(columns=CARRIER_MAPPING, inplace=True)
                    
                    st.session_state.uploaded_data[file_name] = df
                except: pass

def render_standard_filters(df, filter_columns):
    filters = {}
    
    # Hledání data
    date_col = None
    possible_cols = ["DAY", "Day", "Datum od", "Vytvořeno", "Datum", "Date", "Created", "timestamp"]
    date_col = next((c for c in possible_cols if c in df.columns), None)
    
    if not date_col and not df.empty:
        # Fallback na první sloupec, pokud vypadá jako datum
        first = df.columns[0]
        if pd.api.types.is_datetime64_any_dtype(df[first]):
            date_col = first
        else:
            try:
                pd.to_datetime(df[first], dayfirst=True, errors='raise')
                date_col = first
            except: pass

    if date_col:
        try:
            dates = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dropna()
            if not dates.empty:
                mn, mx = dates.min().date(), dates.max().date()
                st.subheader(f"📅 Datum")
                filters['active_date_col'] = date_col 
                
                # Slider
                filters["date_range"] = st.slider(
                    "", min_value=mn, max_value=mx, 
                    value=(mn, mx), format="DD.MM.YY", key="slider_main_date"
                )
        except: pass

    # Ostatní filtry
    for label, col_name in filter_columns.items():
        if col_name in df.columns:
            try:
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
    # CSS
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

    # Init
    if 'uploaded_data' not in st.session_state: st.session_state.uploaded_data = {}
    if 'datasets' not in st.session_state: st.session_state.datasets = {}
    
    # Load
    load_local_files()
    DATA_MAPPING = {
        "📧 Daktela": ["Daktela", "daktela"],
        "🚑 Hotline": ["HL", "hl", "Hotline"],
        "❌ Broken Order": ["BO", "bo", "Broken"],
        "📦 Zásilky": ["Packages", "packages", "Zasilky"]
    }
    
    for category, keywords in DATA_MAPPING.items():
        matched_file = next((f for f in st.session_state.uploaded_data.keys() if any(k in f for k in keywords)), None)
        if matched_file:
            st.session_state.datasets[category] = {"filename": matched_file, "data": st.session_state.uploaded_data[matched_file]}

    # Sidebar
    with st.sidebar:
        if st.button("⬅️ Zpět do Menu", use_container_width=True, type="primary"):
            st.session_state.current_app = "main_menu"; st.rerun()
        st.divider()
        st.header("📂 Výběr agendy")
        
        available_cats = list(st.session_state.datasets.keys())
        if not available_cats: st.warning("Žádná data."); st.stop()
        
        selected_agenda = st.radio("Dataset:", options=list(DATA_MAPPING.keys()), index=0, key="agenda")
        if selected_agenda in st.session_state.datasets:
            st.caption(f"`{st.session_state.datasets[selected_agenda]['filename']}`")

    # Main
    col_tit, _ = st.columns([3, 1])
    with col_tit: st.markdown(f"## 📊 Statistiky: {selected_agenda}")
    
    if selected_agenda not in st.session_state.datasets: return
    df = st.session_state.datasets[selected_agenda]["data"]
    filtered_df = df.copy()

    # Filtry
    with st.sidebar:
        st.divider()
        st.header("🔍 Filtry")
        
        # --- RESET LOGIKA ---
        # Použití callbacku on_click zaručuje, že se stav smaže PŘED vykreslením slideru
        st.button("🔄 Resetovat všechny filtry", use_container_width=True, on_click=reset_filters_callback)

        # Daktela
        if "Daktela" in selected_agenda:
            cols = {"📂 Kategorie": "Kategorie", "🚨 Priorita": "Priorita", "👤 Uživatel": "Uživatel"}
            filters = render_standard_filters(df, cols)
            
            sel_stats = None; stat_mode = 'any'
            if "Statusy" in df.columns:
                raw = df["Statusy"].dropna().astype(str); unq = set()
                for x in raw: unq.update([i.strip() for i in x.split(',') if i.strip()])
                st.subheader("📌 Statusy"); c1, c2 = st.columns(2)
                c1.button("Vše", key="s_a", on_click=select_all, args=("stat_dk", sorted(list(unq))))
                c2.button("Nic", key="s_n", on_click=clear_all, args=("stat_dk",))
                sel_stats = st.multiselect("", sorted(list(unq)), default=sorted(list(unq)), key="stat_dk", label_visibility="collapsed")
                if st.toggle("Přesná shoda", key="tg_stat"): stat_mode = 'exact'

            sel_vip = None
            if "VIP" in df.columns:
                st.subheader("⭐ VIP")
                if st.toggle("Jen VIP", key="tg_vip"): sel_vip = ["→ VIP KLIENT ←"]

            filtered_df = filter_data(
                df, date_range=filters.get("date_range"), date_col_name=filters.get("active_date_col"),
                status_list=sel_stats, vip_list=sel_vip, status_match_mode=stat_mode,
                Kategorie=filters.get("Kategorie"), Priorita=filters.get("Priorita"), Uživatel=filters.get("Uživatel")
            )

        # HL / BO
        elif selected_agenda in ["🚑 Hotline", "❌ Broken Order"]:
            cols = {
                "🚚 Carrier": "Carrier", "⚠️ Příčina chyby": "Příčina chyby",
                "🚨 Priority": "Priority", "📌 Stav úkolu": "Stav úkolu",
                "👤 Reporter": "Reporter", "💻 Resolver IT": "Resolver IT", "📞 Resolver TP": "Resolver TP"
            }
            filters = render_standard_filters(df, cols)
            kwargs = {k: v for k, v in filters.items() if k not in ["date_range", "active_date_col"]}
            filtered_df = filter_data(df, date_range=filters.get("date_range"), date_col_name=filters.get("active_date_col"), **kwargs)

        # Zásilky
        elif "Zásilky" in selected_agenda:
            filters = render_standard_filters(df, {}) 
            filtered_df = filter_data(df, date_range=filters.get("date_range"), date_col_name=filters.get("active_date_col"))

    # Výsledky
    if "Daktela" in selected_agenda:
        kpis = calculate_kpis(filtered_df)
        st.markdown(f"### 📈 Metriky ({len(filtered_df)} / {len(df)})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Počet ticketů", kpis["row_count"])
        c2.metric("Aktivity/ticket", kpis["avg_activities"] or "N/A")
        c3.metric("Doba 1. odp.", kpis["avg_response_time"] or "N/A")
        c4.metric("Reakce klienta", kpis["avg_client_reaction"] or "N/A")
    else:
        st.markdown(f"### 📈 Přehled ({len(filtered_df)} / {len(df)})")
        st.metric("Počet záznamů", len(filtered_df))

    st.divider()

    with st.expander("⚙️ Nastavení zobrazení", expanded=True):
        c1, c2, _ = st.columns(3)
        with c1: show_graphs = st.toggle("📊 Zobrazit grafy", value=True, key="view_tgl_graphs")
        with c2: show_table = st.toggle("📋 Zobrazit tabulku", value=True, key="view_tgl_table")

    # Grafy
    if show_graphs:
        st.markdown("#### 📊 Grafy")
        if filtered_df.empty:
            st.info("⚠️ Žádná data pro zvolený filtr.")
        else:
            date_col = filters.get("active_date_col")
            
            # Graf Zásilky
            if "Zásilky" in selected_agenda and date_col:
                meta = ["Týden", "Datum od", "Datum do", "Week", "Date from", "Date to", date_col]
                candidates = [c for c in filtered_df.columns if c not in meta]
                
                # Numeric konverze jen na filtrovaných datech
                for c in candidates:
                    filtered_df[c] = pd.to_numeric(filtered_df[c], errors='coerce').fillna(0)
                
                cols = [c for c in candidates if pd.api.types.is_numeric_dtype(filtered_df[c])]

                if cols:
                    sums = filtered_df[cols].sum().sort_values(ascending=False)
                    top5 = sums.head(5).index.tolist()
                    
                    st.caption("Výběr dopravců:")
                    
                    # Logika: Streamlit použije default=top5 JEN POKUD klíč neexistuje v session_state.
                    # Jelikož ho při resetu nemažeme, zůstane tam výběr uživatele (např. PPL).
                    sel_carriers = st.multiselect("", sorted(cols), default=top5, key="graph_carrier_select")
                    
                    if sel_carriers:
                        try:
                            keep = [date_col] + sel_carriers
                            chart_df = filtered_df[keep].copy()
                            chart_df[date_col] = pd.to_datetime(chart_df[date_col], dayfirst=True, errors='coerce')
                            chart_df = chart_df.dropna(subset=[date_col])

                            melted = chart_df.melt(id_vars=[date_col], value_vars=sel_carriers, var_name='Dopravce', value_name='Počet')
                            
                            c = alt.Chart(melted).mark_line(point=True).encode(
                                x=alt.X(date_col, title='Datum', axis=alt.Axis(format='%d.%m')),
                                y=alt.Y('Počet', title='Počet'),
                                color='Dopravce',
                                tooltip=[alt.Tooltip(date_col, format='%d.%m.%Y'), 'Dopravce', 'Počet']
                            ).properties(height=400)
                            st.altair_chart(c, use_container_width=True)
                        except: st.error("Chyba grafu.")
                    else: st.info("Vyberte dopravce.")

            # Ostatní grafy
            elif date_col:
                 try:
                     st.caption("Vývoj v čase")
                     cdf = filtered_df.copy()
                     cdf[date_col] = pd.to_datetime(cdf[date_col], dayfirst=True, errors='coerce')
                     data = cdf.groupby(pd.Grouper(key=date_col, freq='W')).size().reset_index(name='Počet')
                     
                     c = alt.Chart(data).mark_bar().encode(
                         x=alt.X(date_col, axis=alt.Axis(format='%d.%m')),
                         y='Počet', tooltip=[alt.Tooltip(date_col, format='%d.%m.%Y'), 'Počet']
                     ).properties(height=350)
                     st.altair_chart(c, use_container_width=True)
                 except: pass

    # Tabulka
    if show_table:
        st.divider()
        st.markdown(f"**Data:** `{st.session_state.datasets[selected_agenda]['filename']}`")
        if not filtered_df.empty:
            st.data_editor(filtered_df, use_container_width=True, height=600, key=f"table_{selected_agenda}")
        else:
            st.warning("⚠️ Žádná data.")