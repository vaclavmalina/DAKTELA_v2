import pandas as pd

def format_human_time(seconds):
    """
    Převede sekundy na čitelný formát (h m s).
    """
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

# ZMĚNA: Přidán parametr date_col_name a dayfirst=True do pd.to_datetime
def filter_data(df, date_range=None, date_col_name=None, status_list=None, vip_list=None, status_match_mode='any', **kwargs):
    """
    Univerzální filtrační funkce.
    date_col_name: Přesný název sloupce, podle kterého se má filtrovat datum.
    """
    filtered_df = df.copy()

    # 1. Datum (Dynamický sloupec)
    # Pokud máme rozsah data A TAKÉ víme, jak se ten sloupec jmenuje
    if date_range and len(date_range) == 2 and date_col_name and date_col_name in filtered_df.columns:
        # Převedeme sloupec na datetime (pokud už není) s podporou dayfirst=True (pro 13.01.2025)
        filtered_df["_temp_date_filter_col"] = pd.to_datetime(filtered_df[date_col_name], dayfirst=True, errors='coerce')
        
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        filtered_df = filtered_df[
            (filtered_df["_temp_date_filter_col"] >= start_date) & 
            (filtered_df["_temp_date_filter_col"] <= end_date)
        ]
        filtered_df = filtered_df.drop(columns=["_temp_date_filter_col"])

    # 2. Statusy
    if status_list and "Statusy" in filtered_df.columns:
        selected_set = set(status_list)
        def check_status_match(row_val):
            if pd.isna(row_val): return False
            row_parts = [x.strip() for x in str(row_val).split(',') if x.strip()]
            row_set = set(row_parts)
            return row_set == selected_set if status_match_mode == 'exact' else not row_set.isdisjoint(selected_set)
        
        mask = filtered_df["Statusy"].apply(check_status_match)
        filtered_df = filtered_df[mask]

    # 3. VIP
    if vip_list and "VIP" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["VIP"].isin(vip_list)]

    # 4. Dynamické filtry (kwargs)
    for col_name, selected_values in kwargs.items():
        if selected_values and col_name in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[col_name].astype(str).isin(selected_values)]

    return filtered_df

def calculate_kpis(df):
    """
    Vypočítá klíčové statistiky z DataFrame.
    """
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