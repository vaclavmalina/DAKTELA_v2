import streamlit as st
import pandas as pd
import datetime
import os
import altair as alt

# --- POMOCNÉ FUNKCE (Přímo zde) ---

def format_human_time(seconds):
    if pd.isna(seconds) or seconds is None: return "N/A"
    seconds = int(round(seconds))
    if seconds < 60: return f"{seconds} s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m} m {s} s"
    else:
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{h} h {m} m"

def calculate_kpis(df):
    stats = {"row_count": len(df), "avg_activities": None, "avg_response_time": None, "avg_client_reaction": None}
    if df.empty: return stats

    if "Počet aktivit" in df.columns:
        avg_act = pd.to_numeric(df["Počet aktivit"], errors='coerce').mean()
        stats["avg_activities"] = round(avg_act, 1) if not pd.isna(avg_act) else 0
    
    if "Doba první odpovědi" in df.columns:
        avg_resp = pd.to_numeric(df["Doba první odpovědi"], errors='coerce').mean()
        if not pd.isna(avg_resp): stats["avg_response_time"] = format_human_time(avg_resp)

    if "Poslední aktivita operátora" in df.columns and "Poslední aktivita klienta" in df.columns:
        try:
            op_times = pd.to_datetime(df["Poslední aktivita operátora"], errors='coerce')
            cl_times = pd.to_datetime(df["Poslední aktivita klienta"], errors='coerce')
            mask = cl_times > op_times
            diff = cl_times[mask] - op_times[mask]
            if not diff.empty: stats["avg_client_reaction"] = format_human_time(diff.dt.total_seconds().mean())
        except: pass
    return stats

def filter_data(df, date_range=None, date_col_name=None, status_list=None, vip_list=None, status_match_mode='any', **kwargs):
    filtered_df = df.copy()

    # 1. Datum
    if date_range and len(date_range) == 2 and date_col_name and date_col_name in filtered_df.columns:
        filtered_df["_temp_date"] = pd.to_datetime(filtered_df[date_col_name], dayfirst=True, errors='coerce')
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        filtered_df = filtered_df[(filtered_df["_temp_date"] >= start_date) & (filtered_df["_temp_date"] <= end_date)]
        filtered_df = filtered_df.drop(columns=["_temp_date"])

    # 2. Statusy
    if status_list and "Statusy" in filtered_df.columns:
        selected_set = set(status_list)
        def check_status(row_val):
            if pd.isna(row_val): return False
            row_set = set([x.strip() for x in str(row_val).split(',') if x.strip()])
            return row_set == selected_set if status_match_mode == 'exact' else not row_set.isdisjoint(selected_set)
        filtered_df = filtered_df[filtered_df["Statusy"].apply(check_status)]

    # 3. VIP
    if vip_list and "VIP" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["VIP"].isin(vip_list)]

    # 4. Dynamické filtry
    for col_name, selected_values in kwargs.items():
        if selected_values and col_name in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[col_name].astype(str).isin(selected_values)]

    return filtered_df

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

def reset_filters_callback():
    keys_to_delete = []
    for key in st.session_state.keys():
        if key == "slider_main_date": keys_to_delete.append(key)
        if key.startswith(("filter_", "stat_", "tg_")): keys_to_delete.append(key)
    for k in keys_to_delete: del st.session_state[k]

def select_all(key, options): st.session_state[key] = options
def clear_all(key): st.session_state[key] = []
def clean_column_name(col_name): return str(col_name).replace('\ufeff', '').replace("'", "").replace('"', "").strip()

def load_local_files():
    local_path = "data/excel"
    # Zajištění existence složky
    if not os.path.exists(local_path):
        try:
            os.makedirs(local_path)
        except: return # Pokud nejde vytvořit, nevadí, vyřešíme níže

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
    date_col = None
    possible_cols = ["DAY", "Day", "Datum od", "Vytvořeno", "Datum", "Date", "Created", "timestamp"]
    date_col = next((c for c in possible_cols if c in df.columns), None)
    
    if not date_col and not df.empty:
        first = df.columns[0]
        if pd.api.types.is_datetime64_any_dtype(df[first]): date_col = first
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
                filters["date_range"] = st.slider("", min_value=mn, max_value=mx, value=(mn, mx), format="DD.MM.YY", key="slider_main_date")
        except: pass

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

# --- HLAVNÍ FUNKCE ---
def render_statistics():
    # 1. ZOBRAZENÍ SIDEBARU (Přebití globálního CSS z main.py)
    # Bez tohoto by uživatel neviděl filtry!
    st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: block !important; }
            .block-container { padding-top: 2rem !important; }
            .stToggle { margin-top: -5px; }
        </style>
    """, unsafe_allow_html=True)

    # 2. HEADER A NAVIGACE (V hlavním okně, aby byla vidět vždy)
    col_back, col_tit, _ = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu", key="stat_main_back", type="primary"):
            st.session_state.current_app = "main_menu"
            st.rerun()
    with col_tit:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📊 Statistiky</h2>", unsafe_allow_html=True)
    st.divider()

    # 3. NAČTENÍ DAT
    if 'uploaded_data' not in st.session_state: st.session_state.uploaded_data = {}
    if 'datasets' not in st.session_state: st.session_state.datasets = {}
    
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

    # 4. KONTROLA DAT
    available_cats = list(st.session_state.datasets.keys())
    
    if not available_cats:
        st.warning("⚠️ Nebyla nalezena žádná data ve složce `data/excel`.")
        st.info("Nahraj prosím soubory `.xlsx` nebo `.csv` do složky `data/excel`, aby názvy obsahovaly klíčová slova (Daktela, Hotline, Packages...).")
        return # Ukončíme funkci, ale uživatel vidí tlačítko Zpět

    # 5. SIDEBAR (VÝBĚR AGENDY)
    with st.sidebar:
        st.header("📂 Výběr agendy")
        selected_agenda = st.radio("Dataset:", options=available_cats, index=0, key="agenda")
        if selected_agenda in st.session_state.datasets:
            st.caption(f"Soubor: `{st.session_state.datasets[selected_agenda]['filename']}`")

    # 6. LOGIKA ZOBRAZENÍ
    st.markdown(f"### Přehled: {selected_agenda}")
    
    df = st.session_state.datasets[selected_agenda]["data"]
    filtered_df = df.copy()

    # Filtry v sidebaru
    with st.sidebar:
        st.divider()
        st.header("🔍 Filtry")
        st.button("🔄 Resetovat filtry", use_container_width=True, on_click=reset_filters_callback)

        if "Daktela" in selected_agenda:
            cols = {"📂 Kategorie": "Kategorie", "🚨 Priorita": "Priorita", "👤 Uživatel": "Uživatel"}
            filters = render_standard_filters(df, cols)
            
            sel_stats = None; stat_mode = 'any'
            if "Statusy" in df.columns:
                st.subheader("📌 Statusy")
                raw = df["Statusy"].dropna().astype(str); unq = set()
                for x in raw: unq.update([i.strip() for i in x.split(',') if i.strip()])
                sel_stats = st.multiselect("", sorted(list(unq)), default=sorted(list(unq)), key="stat_dk")
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

        elif selected_agenda in ["🚑 Hotline", "❌ Broken Order"]:
            cols = {"🚚 Carrier": "Carrier", "⚠️ Příčina": "Příčina chyby", "🚨 Priority": "Priority", "📌 Stav": "Stav úkolu"}
            filters = render_standard_filters(df, cols)
            kwargs = {k: v for k, v in filters.items() if k not in ["date_range", "active_date_col"]}
            filtered_df = filter_data(df, date_range=filters.get("date_range"), date_col_name=filters.get("active_date_col"), **kwargs)

        elif "Zásilky" in selected_agenda:
            filters = render_standard_filters(df, {}) 
            filtered_df = filter_data(df, date_range=filters.get("date_range"), date_col_name=filters.get("active_date_col"))

    # Výsledky (KPIs)
    if "Daktela" in selected_agenda:
        kpis = calculate_kpis(filtered_df)
        st.markdown(f"#### 📈 Metriky ({len(filtered_df)} / {len(df)})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Počet ticketů", kpis["row_count"])
        c2.metric("Aktivity/ticket", kpis["avg_activities"])
        c3.metric("Doba 1. odp.", kpis["avg_response_time"])
        c4.metric("Reakce klienta", kpis["avg_client_reaction"])
    else:
        st.markdown(f"#### 📈 Přehled ({len(filtered_df)} / {len(df)})")
        st.metric("Počet záznamů", len(filtered_df))

    st.divider()

    # Grafy a Tabulky
    with st.expander("⚙️ Nastavení zobrazení", expanded=True):
        c1, c2, _ = st.columns(3)
        show_graphs = c1.toggle("📊 Zobrazit grafy", value=True)
        show_table = c2.toggle("📋 Zobrazit tabulku", value=True)

    if show_graphs and not filtered_df.empty:
        date_col = filters.get("active_date_col")
        if "Zásilky" in selected_agenda and date_col:
             meta = ["Týden", "Datum od", "Datum do", "Week", "Date from", "Date to", date_col]
             candidates = [c for c in filtered_df.columns if c not in meta]
             for c in candidates: filtered_df[c] = pd.to_numeric(filtered_df[c], errors='coerce').fillna(0)
             cols = [c for c in candidates if pd.api.types.is_numeric_dtype(filtered_df[c])]
             
             if cols:
                 sums = filtered_df[cols].sum().sort_values(ascending=False)
                 top5 = sums.head(5).index.tolist()
                 sel_carriers = st.multiselect("Dopravci", sorted(cols), default=top5, key="graph_carrier_select")
                 
                 if sel_carriers:
                     keep = [date_col] + sel_carriers
                     chart_df = filtered_df[keep].copy()
                     chart_df[date_col] = pd.to_datetime(chart_df[date_col], dayfirst=True, errors='coerce')
                     melted = chart_df.melt(id_vars=[date_col], value_vars=sel_carriers, var_name='Dopravce', value_name='Počet')
                     
                     c = alt.Chart(melted).mark_line(point=True).encode(
                         x=alt.X(date_col, title='Datum', axis=alt.Axis(format='%d.%m')),
                         y=alt.Y('Počet'), color='Dopravce', tooltip=[date_col, 'Dopravce', 'Počet']
                     ).interactive()
                     st.altair_chart(c, use_container_width=True)

        elif date_col:
            cdf = filtered_df.copy()
            cdf[date_col] = pd.to_datetime(cdf[date_col], dayfirst=True, errors='coerce')
            data = cdf.groupby(pd.Grouper(key=date_col, freq='W')).size().reset_index(name='Počet')
            c = alt.Chart(data).mark_bar().encode(
                x=alt.X(date_col, axis=alt.Axis(format='%d.%m')), y='Počet', tooltip=[date_col, 'Počet']
            ).interactive()
            st.altair_chart(c, use_container_width=True)

    if show_table and not filtered_df.empty:
        st.data_editor(filtered_df, use_container_width=True, height=600, key=f"table_{selected_agenda}")