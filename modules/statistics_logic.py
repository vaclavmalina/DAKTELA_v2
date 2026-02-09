import pandas as pd

def format_human_time(seconds):
    """
    Převede sekundy na čitelný formát (h m s).
    Např.: 3665 -> "1 h 1 m 5 s"
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

def calculate_kpis(df):
    """
    Vypočítá klíčové statistiky z DataFrame.
    Vrací slovník s vypočtenými hodnotami.
    """
    stats = {
        "avg_activities": None,
        "avg_response_time": None,
        "avg_response_time_raw": None,
        "row_count": len(df)
    }
    
    # 1. Průměrný počet aktivit
    if "Počet aktivit" in df.columns:
        # errors='coerce' změní nečíselné hodnoty na NaN, které mean() ignoruje
        avg_act = pd.to_numeric(df["Počet aktivit"], errors='coerce').mean()
        stats["avg_activities"] = round(avg_act, 1) if not pd.isna(avg_act) else 0
    
    # 2. Průměrná doba první odpovědi
    if "Doba první odpovědi" in df.columns:
        avg_resp = pd.to_numeric(df["Doba první odpovědi"], errors='coerce').mean()
        if not pd.isna(avg_resp):
            stats["avg_response_time_raw"] = avg_resp
            stats["avg_response_time"] = format_human_time(avg_resp)
            
    return stats