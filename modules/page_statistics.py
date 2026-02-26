import streamlit as st
import pandas as pd
import sqlite3
import os
import altair as alt
import datetime
import io
import xlsxwriter
import vl_convert as vlc 

#test

# --- KONFIGURACE CESTY K DB ---
DB_PATH = os.path.join('data', 'daktela_data.db')

# --- POMOCNÉ FUNKCE ---

def format_human_time(seconds):
    if pd.isna(seconds) or seconds is None: return "N/A"
    try: seconds = float(seconds)
    except: return "N/A"
    if seconds < 60: return f"{int(round(seconds))} s"
    elif seconds < 3600: return f"{int(round(seconds / 60))} min"
    else: return f"{round(seconds / 3600, 1)} h"

def calc_biz_sec(start, end):
    if pd.isna(start) or pd.isna(end) or start >= end: return None
    current = start
    biz_secs = 0
    while current < end:
        next_day = (current + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        step_end = min(end, next_day)
        # Pouze pondělí (0) až pátek (4)
        if current.weekday() < 5: 
            day_start = current.replace(hour=8, minute=0, second=0, microsecond=0)
            day_end = current.replace(hour=18, minute=0, second=0, microsecond=0)
            calc_start = max(current, day_start)
            calc_end = min(step_end, day_end)
            if calc_start < calc_end:
                biz_secs += (calc_end - calc_start).total_seconds()
        current = next_day
    return biz_secs

def calculate_kpis(df):
    stats = {"row_count": len(df), "avg_activities": None, "avg_response_time": None, "avg_client_response": None}
    if df.empty: return stats
    
    col_act = "activity_count" if "activity_count" in df.columns else None
    if col_act:
        avg_act = pd.to_numeric(df[col_act], errors='coerce').mean()
        stats["avg_activities"] = round(avg_act, 1) if not pd.isna(avg_act) else 0
        
    if all(c in df.columns for c in ["created_date", "created_time", "first_answer_date", "first_answer_time"]):
        start_strs = df["created_date"].astype(str) + " " + df["created_time"].astype(str)
        end_strs = df["first_answer_date"].astype(str) + " " + df["first_answer_time"].astype(str)
        
        start_strs = start_strs.replace({'nan nan': pd.NA, 'None None': pd.NA})
        end_strs = end_strs.replace({'nan nan': pd.NA, 'None None': pd.NA})
        
        starts = pd.to_datetime(start_strs, errors='coerce')
        ends = pd.to_datetime(end_strs, errors='coerce')
        
        biz_seconds = [calc_biz_sec(s, e) for s, e in zip(starts, ends)]
        med_resp = pd.Series(biz_seconds).median()
        
        if not pd.isna(med_resp): stats["avg_response_time"] = format_human_time(med_resp)
        
    if all(c in df.columns for c in ["last_activity_op_date", "last_activity_op_time", "last_activity_cl_date", "last_activity_cl_time"]):
        op_strs = df["last_activity_op_date"].astype(str) + " " + df["last_activity_op_time"].astype(str)
        cl_strs = df["last_activity_cl_date"].astype(str) + " " + df["last_activity_cl_time"].astype(str)
        
        op_strs = op_strs.replace({'nan nan': pd.NA, 'None None': pd.NA})
        cl_strs = cl_strs.replace({'nan nan': pd.NA, 'None None': pd.NA})
        
        starts = pd.to_datetime(op_strs, errors='coerce')
        ends = pd.to_datetime(cl_strs, errors='coerce')
        
        diffs = (ends - starts).dt.total_seconds()
        diffs = diffs[diffs > 0]
        if not diffs.empty:
            med_client = diffs.median()
            if not pd.isna(med_client): stats["avg_client_response"] = format_human_time(med_client)
            
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
            SELECT t.*, 
                   c.title as _cat_title, 
                   u.title as _user_title, 
                   (SELECT GROUP_CONCAT(st.title, ', ') 
                    FROM ticket_statuses ts 
                    JOIN statuses st ON ts.status_id = st.status_id 
                    WHERE ts.ticket_id = t.ticket_id) as _stat_title, 
                   cl.title as _client_title, 
                   co.title as _contact_title
            FROM tickets t
            LEFT JOIN categories c ON t.category_id = c.category_id
            LEFT JOIN users u ON t.user_id = u.user_id
            LEFT JOIN clients cl ON t.client_id = cl.client_id
            LEFT JOIN contacts co ON t.contact_id = co.contact_id
            """
            df = pd.read_sql_query(query, conn)
            
            mapping = {
                "category_id": "_cat_title",
                "user_id": "_user_title",
                "status_id": "_stat_title",
                "client_id": "_client_title",
                "contact_id": "_contact_title"
            }
            for col, temp_col in mapping.items():
                if col in df.columns and temp_col in df.columns:
                    df[col] = df[temp_col].where(df[temp_col].notna(), df[col])
            df.drop(columns=list(mapping.values()), inplace=True, errors='ignore')

        elif agenda == "Aktivity":
            query = """
            SELECT a.*, 
                   q.title as _queue_title, 
                   c.title as _cat_title
            FROM activities a
            LEFT JOIN queues q ON a.queue_id = q.queue_id
            LEFT JOIN categories c ON a.category_id = c.category_id
            """
            df = pd.read_sql_query(query, conn)
            mapping = {"queue_id": "_queue_title", "category_id": "_cat_title"}
            for col, temp_col in mapping.items():
                if col in df.columns and temp_col in df.columns:
                    df[col] = df[temp_col].where(df[temp_col].notna(), df[col])
            df.drop(columns=list(mapping.values()), inplace=True, errors='ignore')

        elif agenda == "Zásilky":
            try: df = pd.read_sql_query("SELECT * FROM shipments", conn)
            except: df = pd.DataFrame()
        elif agenda == "Klienti":
            df = pd.read_sql_query("SELECT * FROM clients", conn)
        else:
            db_mapping = {
                "Tickety": "tickets", "Aktivity": "activities", "Zásilky": "shipments", 
                "Klienti": "clients", "Uživatelé": "users", "Součty tabulek": "sqlite_sequence",
                "Kategorie": "categories", "Statusy": "statuses", "Fronty": "queues", "Kontakty klientů": "contacts"
            }
            db_table_name = db_mapping.get(agenda, agenda)
            try: df = pd.read_sql_query(f"SELECT * FROM {db_table_name}", conn)
            except: df = pd.DataFrame()
    except Exception as e: 
        st.error(f"SQL Error: {e}"); df = pd.DataFrame()
    finally: conn.close()
    return df

def generate_excel_report(df, kpis, charts=None, agenda_name="Report", date_range_str="N/A"):
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
        ws_dash.write('B4', f"Data z období: {date_range_str}")
        ws_dash.write('B6', "Souhrnné metriky:", bold_fmt) 
        row = 7
        for k, v in kpis.items():
            if v is not None:
                label = k.replace("row_count", "Počet záznamů").replace("avg_activities", "Průměr aktivit").replace("avg_response_time", "Medián odezvy").replace("avg_client_response", "Medián odezvy klienta")
                ws_dash.write(row, 1, label, kpi_fmt); ws_dash.write(row, 2, str(v), kpi_fmt); row += 1
        
        if charts:
            ws_dash.write(row + 2, 1, "Grafický přehled:", bold_fmt)
            img_row = row + 4
            for idx, chart in enumerate(charts):
                try:
                    chart_spec = chart.to_dict()
                    png_data = vlc.vegalite_to_png(chart_spec, scale=2)
                    ws_dash.insert_image(img_row, 1, f'chart_{idx}.png', {'image_data': io.BytesIO(png_data), 'x_scale': 0.7, 'y_scale': 0.7})
                    img_row += 35 # ZMĚNA: Zvětšeno z 20 na 35 řádků pro dostatečnou mezeru mezi grafy v Excelu
                except Exception as e:
                    ws_dash.write(img_row, 1, f"Chyba vykreslení grafu: {str(e)[:100]}")
                    img_row += 2
                    
        ws_dash.set_column('B:C', 25)
        df.to_excel(writer, sheet_name='Data', index=False)
        writer.sheets['Data'].set_column(0, len(df.columns) - 1, 20)
    output.seek(0)
    return output

def reset_filters():
    for k in list(st.session_state.keys()):
        if k.startswith(("filter_", "stat_", "tg_", "slider_", "date_col_select", "check_", "search_")): del st.session_state[k]

# --- MAIN ---
def render_statistics():
    st.markdown("""<style>[data-testid="stSidebar"] { display: block !important; border-right: 1px solid #f0f0f0; } .block-container { padding-top: 1rem !important; } hr { margin: 0.5rem 0; }</style>""", unsafe_allow_html=True)
    c_back, c_tit, _ = st.columns([1, 4, 1])
    if not os.path.exists(DB_PATH): st.error(f"❌ Databáze nenalezena."); return
    
    with st.sidebar:
        st.markdown("### ⚙️ Zdroj dat")
        all_tables = get_all_tables()
        db_mapping = {
            "Tickety": "tickets", "Aktivity": "activities", "Zásilky": "shipments", "Klienti": "clients",
            "Uživatelé": "users", "Součty tabulek": "sqlite_sequence", "Kategorie": "categories",
            "Statusy": "statuses", "Fronty": "queues", "Kontakty klientů": "contacts"
        }
        reverse_mapping = {v: k for k, v in db_mapping.items()}
        options = [reverse_mapping.get(db_name, db_name) for db_name in all_tables]
        
        if not options:
            st.warning("V databázi nejsou žádné dostupné tabulky.")
            return

        sel_agenda = st.selectbox("Agenda:", options, key="agenda_select", label_visibility="collapsed")
        
        st.markdown("### 👁️ Zobrazení")
        show_metrics = st.checkbox("Metriky a Export", value=True)
        show_graph = st.checkbox("Grafy", value=True)
        show_table = st.checkbox("Tabulka", value=True)
        st.divider()
        if st.button("🔄 Vyčistit filtry", use_container_width=True): reset_filters(); st.rerun()
        st.markdown("### 🔍 Filtry")
        df = load_data_from_db(sel_agenda)
        if df.empty: st.warning("Žádná data."); return
        
        if sel_agenda == "Tickety" and "created_date" in df.columns:
            temp_date = pd.to_datetime(df["created_date"], errors='coerce')
            days_cz = {0: '1_Pondělí', 1: '2_Úterý', 2: '3_Středa', 3: '4_Čtvrtek', 4: '5_Pátek', 5: '6_Sobota', 6: '7_Neděle'}
            idx_date = df.columns.get_loc("created_date")
            df.insert(idx_date + 1, "created_day", temp_date.dt.dayofweek.map(days_cz))
            df.insert(idx_date + 2, "created_week", temp_date.dt.isocalendar().week.astype('Int64'))
            
            if "created_time" in df.columns:
                temp_time = pd.to_datetime(df["created_time"], format='%H:%M:%S', errors='coerce')
                hour_labels = temp_time.dt.hour.apply(lambda h: f"{int(h):02d}:00 - {int(h)+1:02d}:00" if pd.notna(h) else None)
                df.insert(idx_date + 3, "created_hour", hour_labels)

        filtered_df = df.copy()

        if sel_agenda == "Tickety" and "ticket_id" in filtered_df.columns:
            search_ticket_id = st.text_input("🔍 Vyhledat ID ticketu:", key="search_ticket_id", help="Vyhledá konkrétní ticket podle jeho ID v databázi.")
            if search_ticket_id:
                filtered_df = filtered_df[filtered_df["ticket_id"].astype(str).str.contains(search_ticket_id.strip(), na=False)]

        date_cols = [c for c in df.columns if any(x in str(c).lower() for x in ["datum", "date", "vytvořeno", "created", "time"])]
        active_date_col = None
        if date_cols:
            active_date_col = st.selectbox("Dle data:", date_cols, index=0, key="date_col_select")
            filtered_df[active_date_col] = pd.to_datetime(filtered_df[active_date_col], errors='coerce').dt.date
            
            valid_dates = filtered_df[active_date_col].dropna()
            if not valid_dates.empty:
                mn, mx = valid_dates.min(), valid_dates.max()
                if mn < mx:
                    default_start = max(mn, mx - datetime.timedelta(days=30))
                    d_range = st.slider("", min_value=mn, max_value=mx, value=(default_start, mx), format="DD.MM", key="slider_date")
                    s_date = d_range[0]
                    e_date = d_range[1] + datetime.timedelta(days=1)
                    filtered_df = filtered_df[(filtered_df[active_date_col] >= s_date) & (filtered_df[active_date_col] < e_date)]
                else:
                    st.caption(f"Pouze jeden den: {mn}")
            else:
                st.caption("Sloupec neobsahuje platná data.")

        filter_cols = []
        if sel_agenda == "Tickety": filter_cols = ["created_day", "created_week", "category_id", "priority", "user_id", "status_id"]
        elif sel_agenda == "Aktivity": filter_cols = ["type", "direction", "sender"]
        elif sel_agenda == "Zásilky": filter_cols = ["carrier", "status"]
        else:
            for c in filtered_df.columns:
                if filtered_df[c].dtype == 'object' and filtered_df[c].nunique() < 50: filter_cols.append(c)

        for col in filter_cols:
            if col in filtered_df.columns:
                if col == "status_id":
                    opts = sorted(filtered_df[col].dropna().astype(str).str.split(', ').explode().unique())
                    if opts:
                        sel = st.multiselect(col, opts, key=f"filter_{col}")
                        if sel:
                            filtered_df = filtered_df[filtered_df[col].astype(str).apply(lambda x: any(item in sel for item in x.split(', ')))]
                else:
                    opts = sorted(filtered_df[col].dropna().astype(str).unique())
                    if opts:
                        display_opts = [o.split('_')[1] if col == 'created_day' and '_' in o else o for o in opts]
                        sel = st.multiselect(col, opts, format_func=lambda x: x.split('_')[1] if col == 'created_day' and '_' in x else x, key=f"filter_{col}")
                        if sel: filtered_df = filtered_df[filtered_df[col].astype(str).isin(sel)]

        if sel_agenda == "Tickety":
            if "vip" in filtered_df.columns:
                if st.checkbox("⭐ Pouze VIP klienti", key="check_vip", help="Zobrazí pouze tickety označené VIP."):
                    filtered_df = filtered_df[filtered_df["vip"].astype(str) == '1']
            has_dev = any(x in filtered_df.columns for x in ["dev_task1", "dev_task2"])
            if has_dev:
                if st.checkbox("🛠️ Pouze s vazbou na vývoj", key="check_dev", help="Tickety s vazbou na BO, HL, TZ, NL ad."):
                    cond = pd.Series(False, index=filtered_df.index)
                    for c in ["dev_task1", "dev_task2"]:
                        if c in filtered_df.columns: cond |= filtered_df[c].notna() & (filtered_df[c] != "")
                    filtered_df = filtered_df[cond]

    with c_tit: 
        st.markdown(f"<h1 style='text-align: center; margin: 0; padding-bottom: 2rem;'>{sel_agenda}</h1>", unsafe_allow_html=True)
        placeholder_export = st.empty()
    
    # --- METRIKY & EXPORT ---
    kpis = calculate_kpis(filtered_df)
    
    date_range_str = "N/A"
    if active_date_col and not filtered_df.empty:
        df_min, df_max = filtered_df[active_date_col].min(), filtered_df[active_date_col].max()
        if pd.notna(df_min) and pd.notna(df_max):
            date_range_str = f"{df_min.strftime('%d.%m.%Y')} - {df_max.strftime('%d.%m.%Y')}"
            
    collected_charts = []

    if show_metrics and sel_agenda == "Tickety":
        st.markdown("### 📊 Metriky")
        k1, k2, k3, k4 = st.columns(4)
        
        k1.metric("Počet ticketů", kpis["row_count"])
        if kpis["avg_activities"]: k2.metric("Aktivity / ticket", kpis["avg_activities"])
        if kpis["avg_response_time"]: k3.metric("Medián odezvy", kpis["avg_response_time"])
        if kpis["avg_client_response"]: k4.metric("Odezva klienta", kpis["avg_client_response"])
        
        st.divider()

    # --- GRAFY S VYUŽITÍM ZÁLOŽEK ---
    if show_graph and not filtered_df.empty and sel_agenda == "Tickety" and active_date_col:
        st.markdown("### 📈 Grafický přehled")
        total_rows = len(filtered_df)
        
        tab_time, tab_cat, tab_detail, tab_clients = st.tabs(["📅 Vývoj v čase", "📊 Kategorie a Statusy", "⏰ Časové rozložení", "👥 Klienti"])
        
        with tab_time:
            chart_df = filtered_df.copy()
            daily = chart_df.groupby(active_date_col).size().reset_index(name='Počet')
            export_chart = alt.Chart(daily).mark_line(point=True).encode(
                x=alt.X(f'{active_date_col}:T', title='Datum'),
                y=alt.Y('Počet:Q', title='Počet'),
                tooltip=[alt.Tooltip(f'{active_date_col}:T', title='Datum'), 'Počet']
            ).properties(height=350, title="Denní vývoj ticketů").interactive()
            st.altair_chart(export_chart, use_container_width=True)
            collected_charts.append(export_chart) 
            
        with tab_cat:
            g1, g2 = st.columns(2)
            with g1:
                if "category_id" in filtered_df.columns:
                    cat_counts = filtered_df["category_id"].value_counts().reset_index()
                    cat_counts.columns = ["Kategorie", "Počet"]
                    cat_counts["Podíl"] = (cat_counts["Počet"] / total_rows * 100).round(1).astype(str) + " %"
                    c_cat = alt.Chart(cat_counts).mark_arc(innerRadius=60).encode(
                        theta="Počet:Q", 
                        color="Kategorie:N", 
                        tooltip=["Kategorie", "Počet", "Podíl"]
                    ).properties(height=350, title="Kategorie")
                    st.altair_chart(c_cat, use_container_width=True)
                    collected_charts.append(c_cat) 
                    
                if "status_id" in filtered_df.columns:
                    stat_series = filtered_df["status_id"].dropna().astype(str).str.split(', ').explode()
                    stat_counts = stat_series.value_counts().reset_index()
                    stat_counts.columns = ["Statusy", "Počet"]
                    stat_counts["Podíl"] = (stat_counts["Počet"] / total_rows * 100).round(1).astype(str) + " %"
                    c_stat = alt.Chart(stat_counts).mark_bar().encode(
                        x=alt.X("Počet:Q", title="Počet"), 
                        y=alt.Y("Statusy:N", sort='-x', title="Status", axis=alt.Axis(labelOverlap=False, labelLimit=300)), 
                        tooltip=["Statusy", "Počet", "Podíl"], 
                        color=alt.Color('Statusy:N', legend=None)
                    ).properties(height=450, title="Nejčastější statusy")
                    st.altair_chart(c_stat, use_container_width=True)
                    collected_charts.append(c_stat) 
                    
            with g2:
                if "priority" in filtered_df.columns:
                    prio_counts = filtered_df["priority"].value_counts().reset_index()
                    prio_counts.columns = ["Priorita", "Počet"]
                    prio_counts["Podíl"] = (prio_counts["Počet"] / total_rows * 100).round(1).astype(str) + " %"
                    c_prio = alt.Chart(prio_counts).mark_arc().encode(
                        theta="Počet:Q", 
                        color="Priorita:N", 
                        tooltip=["Priorita", "Počet", "Podíl"]
                    ).properties(height=350, title="Rozložení dle priority")
                    st.altair_chart(c_prio, use_container_width=True)
                    collected_charts.append(c_prio) 
                    
                if "user_id" in filtered_df.columns:
                    user_counts_full = filtered_df["user_id"].value_counts().reset_index()
                    user_counts_full.columns = ["Uživatel", "Počet"]
                    user_counts_full["Podíl celkem"] = (user_counts_full["Počet"] / total_rows * 100).round(1).astype(str) + " %"
                    user_counts_top10 = user_counts_full.head(10)
                    
                    c_user = alt.Chart(user_counts_top10).mark_bar().encode(
                        x=alt.X("Počet:Q", title="Počet"), 
                        y=alt.Y("Uživatel:N", sort='-x', title="Uživatel", axis=alt.Axis(labelOverlap=False, labelLimit=300)), 
                        tooltip=["Uživatel", "Počet", "Podíl celkem"], 
                        color=alt.Color('Uživatel:N', legend=None)
                    ).properties(height=450, title="Top 10 uživatelů")
                    st.altair_chart(c_user, use_container_width=True)
                    collected_charts.append(c_user) 
                    
        with tab_detail:
            d1, d2 = st.columns(2)
            with d1:
                if "created_day" in filtered_df.columns:
                    day_counts = filtered_df["created_day"].dropna().value_counts().reset_index()
                    day_counts.columns = ["Den", "Počet"]
                    day_counts = day_counts.sort_values(by="Den")
                    day_counts["Den zobrazení"] = day_counts["Den"].apply(lambda x: x.split('_')[1] if '_' in x else x)
                    day_counts["Podíl"] = (day_counts["Počet"] / total_rows * 100).round(1).astype(str) + " %"
                    
                    c_day = alt.Chart(day_counts).mark_bar().encode(
                        x=alt.X("Den zobrazení:N", title="Den v týdnu", sort=day_counts["Den zobrazení"].tolist()), 
                        y=alt.Y("Počet:Q", title="Počet ticketů"), 
                        tooltip=["Den zobrazení", "Počet", "Podíl"],
                        color=alt.Color("Den zobrazení:N", legend=None)
                    ).properties(height=350, title="Počet ticketů dle dnů")
                    st.altair_chart(c_day, use_container_width=True)
                    collected_charts.append(c_day) 
            
            with d2:
                if "created_hour" in filtered_df.columns:
                    hour_counts = filtered_df["created_hour"].dropna().value_counts().reset_index()
                    hour_counts.columns = ["Hodina", "Počet"]
                    hour_counts = hour_counts.sort_values(by="Hodina")
                    hour_counts["Podíl"] = (hour_counts["Počet"] / total_rows * 100).round(1).astype(str) + " %"
                    
                    c_hour = alt.Chart(hour_counts).mark_bar().encode(
                        x=alt.X("Hodina:N", title="Hodinové rozmezí", sort=hour_counts["Hodina"].tolist()), 
                        y=alt.Y("Počet:Q", title="Počet ticketů"), 
                        tooltip=["Hodina", "Počet", "Podíl"],
                        color=alt.Color("Hodina:N", legend=None)
                    ).properties(height=350, title="Počet ticketů dle hodin")
                    st.altair_chart(c_hour, use_container_width=True)
                    collected_charts.append(c_hour)

        with tab_clients:
            # ZMĚNA: Přidána filtrace pro odstranění interních balastních názvů a změněn titulek grafu
            client_col = "account_title" if "account_title" in filtered_df.columns else "_client_title"
            if client_col in filtered_df.columns:
                # Očištění dat o prázdné a nechtěné hodnoty
                df_clients = filtered_df[~filtered_df[client_col].astype(str).str.strip().isin(["Klient", "Balíkobot s.r.o.", "Balikobot s.r.o.", "None", "nan"])]
                
                client_counts = df_clients[client_col].value_counts().reset_index()
                client_counts.columns = ["Klient", "Počet"]
                client_counts_top10 = client_counts.head(10)
                
                c_client = alt.Chart(client_counts_top10).mark_bar().encode(
                    x=alt.X("Počet:Q", title="Počet"), 
                    y=alt.Y("Klient:N", sort='-x', title="Klient", axis=alt.Axis(labelOverlap=False, labelLimit=300)), 
                    tooltip=["Klient", "Počet"], 
                    color=alt.Color('Klient:N', legend=None)
                ).properties(height=450, title="Nejčastější klienti (Top 10)")
                st.altair_chart(c_client, use_container_width=True)
                collected_charts.append(c_client)

        st.divider()

    if sel_agenda == "Tickety" and not filtered_df.empty and placeholder_export is not None:
        xlsx = generate_excel_report(filtered_df, kpis, collected_charts, sel_agenda, date_range_str)
        placeholder_export.download_button("📥 Export XLSX", xlsx, f"Report_{sel_agenda}.xlsx", "application/vnd.ms-excel", use_container_width=True)

    # --- TABULKA DAT ---
    if show_table and not filtered_df.empty:
        st.markdown("### 📋 Detailní data")
        
        display_df = filtered_df.copy()
        if "created_day" in display_df.columns:
            display_df["created_day"] = display_df["created_day"].apply(lambda x: str(x).split('_')[1] if pd.notna(x) and '_' in str(x) else x)
            
        st.dataframe(display_df, use_container_width=True, height=500)