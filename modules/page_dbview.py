import streamlit as st
import sqlite3
import pandas as pd
import os
import io
from datetime import datetime, time

# Cesta k databázi
DB_PATH = os.path.join('data', 'daktela_data.db')

def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    return sqlite3.connect(DB_PATH)

def list_tables():
    conn = get_db_connection()
    if conn is None:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

def get_lookup_dict(conn, table_name, id_col='id', val_col='title'):
    """
    Pomocná funkce: Stáhne číselník a vrátí slovník {1: 'Nový', 2: 'V řešení'}
    """
    try:
        query = f"SELECT {id_col}, {val_col} FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        return dict(zip(df[id_col], df[val_col]))
    except:
        return {}

def replace_col_at_position(df, old_col, new_col_name, mapping_dict):
    """
    Nahradí sloupec ID za Text PŘESNĚ NA STEJNÉ POZICI.
    """
    if old_col not in df.columns:
        return df
    
    col_index = df.columns.get_loc(old_col)
    new_series = df[old_col].map(mapping_dict).fillna(df[old_col])
    
    df.insert(col_index, new_col_name, new_series)
    df = df.drop(columns=[old_col])
    
    return df

def enrich_data_with_names(conn, df, table_name):
    """
    Nahradí ID za čitelné názvy a zachová pořadí sloupců.
    """
    df_enriched = df.copy()

    if table_name == 'tickets':
        statuses = get_lookup_dict(conn, 'statuses', 'status_id', 'title')
        df_enriched = replace_col_at_position(df_enriched, 'status_id', 'status', statuses)

        categories = get_lookup_dict(conn, 'categories', 'category_id', 'title')
        df_enriched = replace_col_at_position(df_enriched, 'category_id', 'category', categories)

        users = get_lookup_dict(conn, 'users', 'user_id', 'title')
        df_enriched = replace_col_at_position(df_enriched, 'user_id', 'user', users)

        clients = get_lookup_dict(conn, 'clients', 'client_id', 'title')
        df_enriched = replace_col_at_position(df_enriched, 'client_id', 'client', clients)

        contacts = get_lookup_dict(conn, 'contacts', 'contact_id', 'title')
        df_enriched = replace_col_at_position(df_enriched, 'contact_id', 'contact', contacts)

    elif table_name == 'activities':
        queues = get_lookup_dict(conn, 'queues', 'queue_id', 'title')
        df_enriched = replace_col_at_position(df_enriched, 'queue_id', 'queue', queues)
            
        categories = get_lookup_dict(conn, 'categories', 'category_id', 'title')
        df_enriched = replace_col_at_position(df_enriched, 'category_id', 'category', categories)

    elif table_name == 'contacts':
        clients = get_lookup_dict(conn, 'clients', 'client_id', 'title')
        df_enriched = replace_col_at_position(df_enriched, 'client_id', 'client_name', clients)

    return df_enriched

def process_data_to_strings(df):
    """
    Převede DataFrame na čisté stringy pro Excel.
    """
    df_export = df.copy()
    text_columns = []

    for col in df_export.columns:
        col_lower = col.lower()
        
        looks_like_time = any(x in col_lower for x in ['time', 'cas', 'duration', 'start', 'end'])
        looks_like_date = any(x in col_lower for x in ['date', 'day', 'datum'])
        looks_like_system = any(x in col_lower for x in ['created', 'updated', 'edited', 'deleted', 'timestamp'])
        
        if not (looks_like_time or looks_like_date or looks_like_system or 'phone' in col_lower or 'cislo' in col_lower):
             continue

        if looks_like_time or looks_like_date or looks_like_system:
            try:
                temp_series = pd.to_datetime(df_export[col], errors='coerce')
                if temp_series.notna().sum() == 0:
                    pass 
                else:
                    if looks_like_time:
                        df_export[col] = temp_series.dt.strftime('%H:%M:%S').fillna('')
                        text_columns.append(col)
                    elif looks_like_date:
                        df_export[col] = temp_series.dt.strftime('%d.%m.%Y').fillna('')
                        text_columns.append(col)
                    else:
                        df_export[col] = temp_series.dt.strftime('%d.%m.%Y %H:%M:%S').fillna('')
                        text_columns.append(col)
            except:
                pass

        if 'phone' in col_lower or 'cislo' in col_lower or 'id' in col_lower:
            try:
                df_export[col] = df_export[col].astype(str)
                text_columns.append(col)
            except:
                pass

    return df_export, text_columns

def render_db_view():
    # --- CSS PRO ROZŠÍŘENÍ STRÁNKY (WIDE MODE) ---
    # Pouze roztáhne kontejner, nemění styl tlačítek
    st.markdown("""
        <style>
            .block-container {
                max_width: 95% !important;
                padding-top: 2rem;
                padding-bottom: 2rem;
            }
            div[data-testid="stExpander"] details summary p {
                font-weight: bold;
                font-size: 1.1em;
            }
        </style>
    """, unsafe_allow_html=True)

    # Navigace: Vráceno na poměr [1, 4, 1], který fungoval spolehlivě
    col_back, col_title, col_next = st.columns([1, 4, 1])

    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>🔎 Prohlížeč databáze</h2>", unsafe_allow_html=True)
        
    st.divider()

    if not os.path.exists(DB_PATH):
        st.error(f"❌ Databáze nebyla nalezena na cestě: {DB_PATH}")
        return

    tables = list_tables()
    if not tables:
        st.warning("⚠️ Databáze existuje, ale neobsahuje žádné tabulky.")
        return

    # --- VYCENTROVANÝ VÝBĚR TABULKY ---
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        selected_table = st.selectbox("Vyberte tabulku k zobrazení:", tables)

    if selected_table:
        conn = get_db_connection()
        try:
            # 1. Načtení RAW dat
            df_raw = pd.read_sql_query(f"SELECT * FROM {selected_table}", conn)
            # 2. Obohacení
            df_enriched = enrich_data_with_names(conn, df_raw, selected_table)
        except Exception as e:
            st.error(f"Chyba při čtení tabulky: {e}")
            conn.close()
            return
        conn.close()

        # 3. Výběr sloupců
        all_columns = df_enriched.columns.tolist()

        # Expander pro nastavení
        with st.expander(f"🛠️ Filtrovat sloupce pro tabulku '{selected_table}'"):
            
            def select_all_cols(): st.session_state[f"cols_{selected_table}"] = all_columns
            def clear_all_cols(): st.session_state[f"cols_{selected_table}"] = []

            b_col1, b_col2, _ = st.columns([1, 1, 6])
            b_col1.button("✅ Vybrat vše", on_click=select_all_cols, key=f"btn_all_{selected_table}")
            b_col2.button("❌ Zrušit vše", on_click=clear_all_cols, key=f"btn_clear_{selected_table}")

            selected_columns = st.multiselect(
                "Vyberte sloupce:",
                options=all_columns,
                default=all_columns,
                key=f"cols_{selected_table}",
                label_visibility="collapsed"
            )

        if not selected_columns:
            st.warning("⚠️ Vyberte alespoň jeden sloupec.")
            return

        final_cols_ordered = [c for c in all_columns if c in selected_columns]
        df_final = df_enriched[final_cols_ordered]

        # --- ZOBRAZENÍ DAT (FULL WIDTH) ---
        st.markdown(f"### Náhled: {selected_table}")
        st.caption(f"Zobrazeno {len(df_final)} řádků a {len(selected_columns)} sloupců.")
        
        # use_container_width=True zajistí roztažení tabulky do šířky
        st.dataframe(df_final, use_container_width=True, height=500)
        
        st.divider()
        st.subheader("📥 Možnosti exportu")

        # --- EXPORTY ---
        col_xls, col_csv, _ = st.columns([1, 1, 3])
        
        with col_xls:
            df_export, text_cols = process_data_to_strings(df_final)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Data')
                worksheet = writer.sheets['Data']
                for idx, col_name in enumerate(df_export.columns):
                    col_letter = chr(65 + idx) if idx < 26 else 'A' + chr(65 + (idx - 26))
                    try: worksheet.column_dimensions[col_letter].width = min(len(str(col_name)) + 5, 25)
                    except: pass
                    if col_name in text_cols:
                        try: 
                            for cell in worksheet[col_letter]: cell.number_format = '@'
                        except: pass
            buffer.seek(0)
            
            st.download_button(
                label="📊 Stáhnout Excel",
                data=buffer,
                file_name=f"{selected_table}_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )

        with col_csv:
            csv_data = df_final.to_csv(index=False).encode('utf-8-sig')
            
            st.download_button(
                label="📄 Stáhnout CSV",
                data=csv_data,
                file_name=f"{selected_table}_export.csv",
                mime="text/csv",
                use_container_width=True
            )