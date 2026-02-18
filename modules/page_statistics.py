import streamlit as st
import pandas as pd
import sqlite3
import os
import altair as alt
import datetime
import io
import xlsxwriter
import vl_convert as vlc 

# --- KONFIGURACE CESTY K DB ---
DB_PATH = os.path.join('data', 'daktela_data.db')

# --- POMOCNÉ FUNKCE ---

def format_human_time(seconds):
    if pd.isna(seconds) or seconds is None: return "N/A"
    try: seconds = int(round(float(seconds)))
    except: return "N/A"
    if seconds < 60: return f"{seconds} s"
    elif seconds < 3600: return f"{divmod(seconds, 60)[0]} m {divmod(seconds, 60)[1]} s"
    else: return f"{divmod(seconds, 3600)[0]} h {divmod(divmod(seconds, 3600)[1], 60)[0]} m"

def calculate_kpis(df):
    stats = {"row_count": len(df), "avg_activities": None, "avg_response_time": None}
    if df.empty: return stats
    col_act = next((c for c in df.columns if c in ["Počet aktivit", "activity_count"]), None)
    col_resp = next((c for c in df.columns if c in ["Doba první odpovědi", "first_answer_duration"]), None)
    if col_act:
        avg_act = pd.to_numeric(df[col_act], errors='coerce').mean()
        stats["avg_activities"] = round(avg_act, 1) if not pd.isna(avg_act) else 0
    if col_resp:
        avg_resp = pd.to_numeric(df[col_resp], errors='coerce').mean()
        if not pd.isna(avg_resp): stats["avg_response_time"] = format_human_time(avg_resp)
    return stats

def get_db_connection():
    if not os.path.exists(DB_PATH): return None
    return sqlite3.connect(DB_PATH)

def get_all_tables():
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

def load_data_from_db(agenda):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        if agenda == "Tickety":
            query = """
            SELECT t.*, c.title as 'Kategorie', u.title as 'Uživatel', s.title as 'Statusy', 
                   cl.title as 'Klient', co.title as 'Kontakt'
            FROM tickets t
            LEFT JOIN categories c ON t.category_id = c.category_id
            LEFT JOIN users u ON t.user_id = u.user_id
            LEFT JOIN statuses s ON t.status_id = s.status_id
            LEFT JOIN clients cl ON t.client_id = cl.client_id
            LEFT JOIN contacts co ON t.contact_id = co.contact_id
            """
            df = pd.read_sql_query(query, conn)
            rename_map = {
                "activity_count": "Počet aktivit", "priority": "Priorita",
                "created_date": "Datum vytvoření", "edited_date": "Poslední změna",
                "first_answer_date": "První odpověď", "stage": "Fáze", 
                "vip": "VIP", "title": "Předmět"
            }
            df.rename(columns=rename_map, inplace=True)
            if "VIP" in df.columns:
                df["VIP"] = df["VIP"].apply(lambda x: "→ VIP KLIENT ←" if x == 1 else "Standard")
        elif agenda == "Aktivity":
            query = """
            SELECT a.*, q.title as 'Fronta', c.title as 'Kategorie'
            FROM activities a
            LEFT JOIN queues q ON a.queue_id = q.queue_id
            LEFT JOIN categories c ON a.category_id = c.category_id
            """
            df = pd.read_sql_query(query, conn)
            df.rename(columns={"type": "Typ", "direction": "Směr", "sender": "Odesílatel", "created_date": "Datum"}, inplace=True)
        elif agenda == "Zásilky":
            try: df = pd.read_sql_query("SELECT * FROM shipments", conn)
            except: df = pd.DataFrame()
        elif agenda == "Klienti":
            df = pd.read_sql_query("SELECT * FROM clients", conn)
            df.rename(columns={"title": "Název klienta", "client_type": "Typ klienta"}, inplace=True)
        else:
            try: df = pd.read_sql_query(f"SELECT * FROM {agenda}", conn)
            except: df = pd.DataFrame()
    except Exception as e: 
        st.error(f"SQL Error: {e}"); df = pd.DataFrame()
    finally: conn.close()
    return df

def generate_excel_report(df, kpis, chart=None, agenda_name="Report"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        wb = writer.book
        ws_dash = wb.add_worksheet('Přehled')
        writer.sheets['Přehled'] = ws_dash
        title_fmt = wb.add_format({'bold': True, 'font_size': 16, 'color': '#2c3e50'})
        bold_fmt = wb.add_format({'bold': True, 'font_size': 12})
        kpi_fmt = wb.add_format({'border': 1, 'bg_color': '#f0f0f0', 'font_size': 11})
        ws_dash.write('B2', f"Report: {agenda_name}", title_fmt)
        ws_dash.write('B3', f"Generováno: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}")
        ws_dash.write('B5', "Souhrnné metriky:", bold_fmt)
        row = 6
        for k, v in kpis.items():
            if v is not None:
                label = k.replace("row_count", "Počet záznamů").replace("avg_activities", "Průměr aktivit").replace("avg_response_time", "Doba odezvy")
                ws_dash.write(row, 1, label, kpi_fmt); ws_dash.write(row, 2, str(v), kpi_fmt); row += 1
        if chart:
            try:
                # DŮLEŽITÉ: Přidání dat přímo do specifikace před konverzí
                chart_spec = chart.to_dict()
                # vl_convert potřebuje mít data přímo v JSONu
                png_data = vlc.vegalite_to_png(chart_spec, scale=2)
                ws_dash.write(row + 2, 1, "Grafický přehled:", bold_fmt)
                ws_dash.insert_image(row + 4, 1, 'chart.png', {'image_data': io.BytesIO(png_data), 'x_scale': 0.7, 'y_scale': 0.7})
            except Exception as e:
                ws_dash.write(row + 4, 1, f"Chyba vykreslení grafu: {str(e)[:100]}")
        ws_dash.set_column('B:C', 25)
        df.to_excel(writer, sheet_name='Data', index=False)
        writer.sheets['Data'].set_column(0, len(df.columns) - 1, 20)
    output.seek(0)
    return output

def reset_filters():
    for k in list(st.session_state.keys()):
        if k.startswith(("filter_", "stat_", "tg_", "slider_", "date_col_select", "check_")): del st.session_state[k]

# --- MAIN ---
def render_statistics():
    st.markdown("""<style>[data-testid="stSidebar"] { display: block !important; border-right: 1px solid #f0f0f0; } .block-container { padding-top: 1rem !important; } hr { margin: 0.5rem 0; }</style>""", unsafe_allow_html=True)
    c_back, c_tit, _ = st.columns([1, 4, 1])
    with c_back:
        if st.button("⬅️ Menu", key="back_menu"): st.session_state.current_app = "main_menu"; st.rerun()
    if not os.path.exists(DB_PATH): st.error(f"❌ Databáze nenalezena."); return

    with st.sidebar:
        st.markdown("### ⚙️ Zdroj dat")
        all_tables = get_all_tables()
        nice_map = {"Tickety": "Tickety", "Aktivity": "Aktivity", "Zásilky": "Zásilky", "Klienti": "Klienti"}
        known_internal = ['tickets', 'activities', 'clients', 'shipments', 'contacts', 'users', 'categories', 'statuses', 'queues', 'sqlite_sequence']
        other_tables = [t for t in all_tables if t not in known_internal]
        options = list(nice_map.keys()) + other_tables
        sel_agenda = st.selectbox("Agenda:", options, key="agenda_select", label_visibility="collapsed")
        
        st.markdown("### 👁️ Zobrazení")
        show_graph = st.checkbox("Grafy", value=True)
        show_table = st.checkbox("Tabulka", value=True)
        st.divider()
        if st.button("🔄 Vyčistit filtry", use_container_width=True): reset_filters(); st.rerun()
        st.markdown("### 🔍 Filtry")
        df = load_data_from_db(sel_agenda)
        if df.empty: st.warning("Žádná data."); return
        filtered_df = df.copy()

        # --- DATUMOVÝ FILTR ---
        date_cols = [c for c in df.columns if any(x in str(c).lower() for x in ["datum", "date", "vytvořeno", "created", "time"])]
        active_date_col = None
        if date_cols:
            active_date_col = st.selectbox("Dle data:", date_cols, index=0, key="date_col_select")
            if not pd.api.types.is_datetime64_any_dtype(filtered_df[active_date_col]):
                filtered_df[active_date_col] = pd.to_datetime(filtered_df[active_date_col], errors='coerce')
            
            valid_dates = filtered_df[active_date_col].dropna()
            # OPRAVA SLIDERU: Kontrola existence a rozdílnosti min/max
            if not valid_dates.empty:
                mn, mx = valid_dates.min().date(), valid_dates.max().date()
                if mn < mx:
                    default_start = max(mn, mx - datetime.timedelta(days=30))
                    d_range = st.slider("", min_value=mn, max_value=mx, value=(default_start, mx), format="DD.MM", key="slider_date")
                    s_date, e_date = pd.to_datetime(d_range[0]), pd.to_datetime(d_range[1]) + pd.Timedelta(days=1)
                    filtered_df = filtered_df[(filtered_df[active_date_col] >= s_date) & (filtered_df[active_date_col] < e_date)]
                else:
                    st.caption(f"Pouze jeden den: {mn}")
            else:
                st.caption("Sloupec neobsahuje platná data.")

        # --- DYNAMICKÉ FILTRY ---
        filter_cols = []
        if sel_agenda == "Tickety": filter_cols = ["Kategorie", "Priorita", "Uživatel", "Statusy"]
        elif sel_agenda == "Aktivity": filter_cols = ["Typ", "Směr", "Odesílatel"]
        elif sel_agenda == "Zásilky": filter_cols = ["carrier", "status"]
        else:
            for c in filtered_df.columns:
                if filtered_df[c].dtype == 'object' and filtered_df[c].nunique() < 50: filter_cols.append(c)

        for col in filter_cols:
            if col in filtered_df.columns:
                opts = sorted(filtered_df[col].dropna().astype(str).unique())
                if opts:
                    sel = st.multiselect(col, opts, key=f"filter_{col}")
                    if sel: filtered_df = filtered_df[filtered_df[col].astype(str).isin(sel)]

        if sel_agenda == "Tickety":
            if "VIP" in filtered_df.columns:
                if st.checkbox("⭐ Pouze VIP klienti", key="check_vip", help="Zobrazí pouze tickety označené VIP."):
                    filtered_df = filtered_df[filtered_df["VIP"].str.contains("VIP", na=False)]
            has_dev = any(x in filtered_df.columns for x in ["dev_task1", "dev_task2"])
            if has_dev:
                if st.checkbox("🛠️ Pouze s vazbou na vývoj", key="check_dev", help="Tickety s vazbou na BO, HL, TZ, NL ad."):
                    cond = pd.Series(False, index=filtered_df.index)
                    for c in ["dev_task1", "dev_task2"]:
                        if c in filtered_df.columns: cond |= filtered_df[c].notna() & (filtered_df[c] != "")
                    filtered_df = filtered_df[cond]

    # --- GRAFY & KPI ---
    export_chart = None
    if show_graph and not filtered_df.empty and active_date_col:
        chart_df = filtered_df.copy()
        daily = chart_df.groupby(chart_df[active_date_col].dt.date).size().reset_index(name='Počet')
        export_chart = alt.Chart(daily).mark_line(point=True).encode(
            x=alt.X(f'{active_date_col}:T', title='Datum'),
            y=alt.Y('Počet:Q', title='Počet'),
            tooltip=[alt.Tooltip(f'{active_date_col}:T', title='Datum'), 'Počet']
        ).properties(height=300, title="Vývoj v čase").interactive()

    with c_tit: st.markdown(f"<h1 style='text-align: center; margin: 0;'>{sel_agenda}</h1>", unsafe_allow_html=True)
    kpis = calculate_kpis(filtered_df)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Počet záznamů", kpis["row_count"])
    if kpis["avg_activities"]: k2.metric("Aktivity / ticket", kpis["avg_activities"])
    if kpis["avg_response_time"]: k3.metric("Doba odezvy", kpis["avg_response_time"])
    with k4:
        st.write("")
        if not filtered_df.empty:
            xlsx = generate_excel_report(filtered_df, kpis, export_chart, sel_agenda)
            st.download_button("📥 Export XLSX", xlsx, f"Report_{sel_agenda}.xlsx", "application/vnd.ms-excel", use_container_width=True)

    st.markdown("---")
    if show_graph and not filtered_df.empty:
        if export_chart: st.altair_chart(export_chart, use_container_width=True)
        if "Kategorie" in filtered_df.columns:
            cat_counts = filtered_df["Kategorie"].value_counts().reset_index()
            cat_counts.columns = ["Kategorie", "Počet"]
            c2 = alt.Chart(cat_counts).mark_arc(innerRadius=60).encode(theta="Počet", color="Kategorie", tooltip=["Kategorie", "Počet"]).properties(height=300)
            st.altair_chart(c2, use_container_width=True)

    if show_table and not filtered_df.empty:
        st.write("#### Detailní data")
        st.dataframe(filtered_df, use_container_width=True, height=500)