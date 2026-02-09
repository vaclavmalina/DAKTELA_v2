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
        "row_count": len(df),
        "avg_activities": None,
        "avg_response_time": None,      # Doba 1. odpovědi
        "avg_client_reaction": None     # Průměrná reakce klienta
    }
    
    # 1. Průměrný počet aktivit
    if "Počet aktivit" in df.columns:
        # errors='coerce' změní nečíselné hodnoty na NaN
        avg_act = pd.to_numeric(df["Počet aktivit"], errors='coerce').mean()
        stats["avg_activities"] = round(avg_act, 1) if not pd.isna(avg_act) else 0
    
    # 2. Průměrná doba první odpovědi
    if "Doba první odpovědi" in df.columns:
        avg_resp = pd.to_numeric(df["Doba první odpovědi"], errors='coerce').mean()
        if not pd.isna(avg_resp):
            stats["avg_response_time"] = format_human_time(avg_resp)

    # 3. Průměrná reakce klienta (Klient - Operátor)
    # Podmínka: Počítáme jen pokud Klient reagoval PO operátorovi
    if "Poslední aktivita operátora" in df.columns and "Poslední aktivita klienta" in df.columns:
        try:
            # Převedeme sloupce na datetime objekty
            op_times = pd.to_datetime(df["Poslední aktivita operátora"], errors='coerce')
            cl_times = pd.to_datetime(df["Poslední aktivita klienta"], errors='coerce')

            # Vytvoříme masku (filtr) pro řádky, kde je čas klienta VĚTŠÍ než čas operátora
            # (Zároveň se tím vyhodí řádky, kde čas chybí = NaT)
            mask = cl_times > op_times
            
            # Vybereme jen validní časy
            valid_cl = cl_times[mask]
            valid_op = op_times[mask]

            if not valid_cl.empty:
                # Spočítáme rozdíl
                diff = valid_cl - valid_op
                
                # Převedeme na sekundy a uděláme průměr
                avg_seconds = diff.dt.total_seconds().mean()
                
                # Naformátujeme pomocí funkce definované výše v tomto souboru
                stats["avg_client_reaction"] = format_human_time(avg_seconds)
                
        except Exception:
            # Pokud nastane chyba při výpočtu, necháme hodnotu None
            pass

    return stats