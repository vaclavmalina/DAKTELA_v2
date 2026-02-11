import pandas as pd

def format_human_time(seconds):
    """
    Převede sekundy na čitelný formát (h m s).
    """
    if pd.isna(seconds) or seconds is None:
        return "N/A"
    
    seconds = int(round(seconds))
    
    if seconds < 60:
        return f"{seconds} s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m} m {s} s"
    else:
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{h} h {m} m"

def filter_data(df, date_range=None, status_list=None, vip_list=None, category_list=None, status_match_mode='any'):
    """
    Filtruje DataFrame podle zadaných parametrů.
    status_match_mode: 
        'any' = řádek obsahuje alespoň jeden z vybraných statusů (OR)
        'exact' = řádek obsahuje přesně tuto kombinaci a nic víc/nic míň
    """
    filtered_df = df.copy()

    # 1. Filtrace podle Data (Vytvořeno)
    if date_range and len(date_range) == 2 and "Vytvořeno" in filtered_df.columns:
        # Převedeme sloupec na datetime
        filtered_df["Vytvořeno_dt"] = pd.to_datetime(filtered_df["Vytvořeno"], errors='coerce')
        
        # Převedeme vstupy (date objekty ze slideru) na datetime
        start_date = pd.to_datetime(date_range[0])
        # Konec dne nastavíme na 23:59:59
        end_date = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        filtered_df = filtered_df[
            (filtered_df["Vytvořeno_dt"] >= start_date) & 
            (filtered_df["Vytvořeno_dt"] <= end_date)
        ]
        filtered_df = filtered_df.drop(columns=["Vytvořeno_dt"])

    # 2. Filtrace podle Statusů (S novou logikou rozdělování čárkou)
    if status_list and "Statusy" in filtered_df.columns:
        # Převedeme seznam vybraných statusů na množinu (set) pro rychlé porovnání
        selected_set = set(status_list)

        def check_status_match(row_val):
            if pd.isna(row_val): return False
            # Rozdělíme řetězec v buňce na seznam a očistíme mezery (např. "Open, VIP" -> {"Open", "VIP"})
            row_parts = [x.strip() for x in str(row_val).split(',') if x.strip()]
            row_set = set(row_parts)

            if status_match_mode == 'exact':
                # Přesná shoda: Množina v řádku se musí rovnat množině vybraných
                # Tzn. ticket musí mít přesně ty statusy, co jsou vybrané, a žádné jiné
                return row_set == selected_set
            else:
                # Alespoň jeden (Default): Průnik množin není prázdný
                # Tzn. alespoň jeden status z řádku je v seznamu vybraných
                return not row_set.isdisjoint(selected_set)

        mask = filtered_df["Statusy"].apply(check_status_match)
        filtered_df = filtered_df[mask]

    # 3. Filtrace podle VIP
    if vip_list and "VIP" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["VIP"].isin(vip_list)]

    # 4. Filtrace podle Kategorie
    if category_list and "Kategorie" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["Kategorie"].isin(category_list)]

    return filtered_df

def calculate_kpis(df):
    """
    Vypočítá klíčové statistiky z DataFrame.
    """
    stats = {
        "row_count": len(df),
        "avg_activities": None,
        "avg_response_time": None,
        "avg_client_reaction": None
    }
    
    if df.empty:
        return stats

    if "Počet aktivit" in df.columns:
        avg_act = pd.to_numeric(df["Počet aktivit"], errors='coerce').mean()
        stats["avg_activities"] = round(avg_act, 1) if not pd.isna(avg_act) else 0
    
    if "Doba první odpovědi" in df.columns:
        avg_resp = pd.to_numeric(df["Doba první odpovědi"], errors='coerce').mean()
        if not pd.isna(avg_resp):
            stats["avg_response_time"] = format_human_time(avg_resp)

    if "Poslední aktivita operátora" in df.columns and "Poslední aktivita klienta" in df.columns:
        try:
            op_times = pd.to_datetime(df["Poslední aktivita operátora"], errors='coerce')
            cl_times = pd.to_datetime(df["Poslední aktivita klienta"], errors='coerce')
            mask = cl_times > op_times
            valid_cl = cl_times[mask]
            valid_op = op_times[mask]

            if not valid_cl.empty:
                diff = valid_cl - valid_op
                avg_seconds = diff.dt.total_seconds().mean()
                stats["avg_client_reaction"] = format_human_time(avg_seconds)
        except Exception:
            pass

    return stats