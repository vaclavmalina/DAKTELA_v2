import json
import os
import sys
import csv
import time
import streamlit as st
from openai import OpenAI
from collections import Counter, defaultdict
from datetime import datetime # ZMĚNA: Pro timestamp

# --- KONFIGURACE ---
MODEL_NAME = 'gpt-4o-mini' 
DATA_DIR = 'data'

# ZMĚNA: Generování časového razítka pro unikátní názvy souborů
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

INPUT_FILE = os.path.join(DATA_DIR, 'data_technicka_VSE_20260206_094050.json')

# ZMĚNA: Názvy souborů obsahují timestamp
JSON_OUTPUT = os.path.join(DATA_DIR, f'ai_analysis_log_{timestamp}.json')
CSV_OUTPUT = os.path.join(DATA_DIR, f'ai_analysis_stats_{timestamp}.csv')

# Import promptu
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from ai.prompt import SYSTEM_PROMPT
except ImportError:
    try:
        from prompt import SYSTEM_PROMPT
    except ImportError:
        print("CHYBA: Nenalezen soubor 'prompt.py'.")
        sys.exit(1)

# Inicializace OpenAI
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def format_ticket_history(ticket):
    summary = f"Téma: {ticket.get('ticket_name', 'Bez názvu')}\n"
    summary += f"Původní status: {ticket.get('ticket_status', 'Neznámý')}\n"
    summary += f"Datum vytvoření: {ticket.get('ticket_creationDate', '')}\n"
    summary += "-" * 40 + "\n"
    
    activities = sorted(ticket.get('activities', []), key=lambda x: x.get('activity_number', 0))
    
    if not activities: 
        return summary + "Ticket neobsahuje žádné aktivity."

    for act in activities:
        act_type = act.get('activity_type', 'UNKNOWN')
        sender = act.get('activity_sender', 'Neznámý')
        raw_text = act.get('activity_text') or ""
        
        if not raw_text.strip(): continue

        limit = 2000
        if len(raw_text) > limit:
            clean_text = raw_text[:limit].replace('\n', ' ').replace(';', ',') + " [... TEXT ZKRÁCEN ...]"
        else:
            clean_text = raw_text.replace('\n', ' ').replace(';', ',')
        
        summary += f"[{act_type}] {sender}: {clean_text}\n"

    return summary

def generate_stats_csv(analyzed_data):
    """
    Vytvoří CSV soubor, který je bezpečný pro Excel.
    Odstraňuje znaky nového řádku uvnitř buněk, aby se tabulka nerozsypala.
    """
    total = len(analyzed_data)
    if total == 0: return

    # Agregace dat podle nového statusu
    stats = defaultdict(lambda: {
        "count": 0,
        "problems": [],
        "automation": [],
        "minimization": []
    })

    for item in analyzed_data:
        status = item.get("new_status", "Neznámý")
        stats[status]["count"] += 1
        
        if item.get("problem_summary"): stats[status]["problems"].append(item["problem_summary"])
        if item.get("automation_suggestion"): stats[status]["automation"].append(item["automation_suggestion"])
        if item.get("minimization_suggestion"): stats[status]["minimization"].append(item["minimization_suggestion"])

    print("\n" + "="*60)
    print(f"📊 GENERUJI CSV STATISTIKU ({CSV_OUTPUT})...")
    print("="*60)

    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

        # Používáme utf-8-sig pro správné zobrazení češtiny v Excelu
        with open(CSV_OUTPUT, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
            
            header = [
                'Nový Status', 
                'Počet', 
                'Podíl (%)', 
                'Typické problémy (ukázky)', 
                'Návrhy automatizace', 
                'Návrhy minimalizace'
            ]
            writer.writerow(header)

            sorted_stats = sorted(stats.items(), key=lambda x: x[1]['count'], reverse=True)

            for status, data in sorted_stats:
                count = data["count"]
                percentage = (count / total) * 100
                percentage_str = f"{percentage:.1f}".replace('.', ',')
                
                # ZMĚNA: Funkce pro formátování, která odstraní \n (nové řádky)
                # Místo seznamu pod sebou uděláme seznam vedle sebe oddělený svislítkem |
                def format_safe_cell(items, max_items=10):
                    unique_items = list(set(items))[:max_items]
                    if not unique_items: return ""
                    # Vyčistíme texty od enterů a středníků
                    cleaned_items = [item.replace('\n', ' ').replace(';', ',').strip() for item in unique_items]
                    # Spojíme pomocí " | "
                    return " | ".join(cleaned_items)

                unique_problems = format_safe_cell(data["problems"], 15)
                unique_auto = format_safe_cell(data["automation"], 5)
                unique_min = format_safe_cell(data["minimization"], 5)

                writer.writerow([
                    status, 
                    count, 
                    percentage_str, 
                    unique_problems, 
                    unique_auto, 
                    unique_min
                ])
                
                print(f"{status:<30} | {count:<5} | {percentage:.1f} %")

        print(f"\n✅ CSV uloženo: {CSV_OUTPUT}")

    except Exception as e:
        print(f"❌ Chyba při ukládání CSV: {e}")

def run_analysis(input_path):
    if not os.path.exists(input_path):
        print(f"❌ Soubor {input_path} nenalezen.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        tickets = json.load(f)

    print(f"🚀 Zahajuji analýzu {len(tickets)} ticketů (Model: {MODEL_NAME})...")
    start_analysis_time = time.time()
    
    detailed_log = []

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    for i, ticket in enumerate(tickets, 1):
        ticket_number = ticket.get('ticket_number')
        ticket_input = format_ticket_history(ticket)
        
        t_start = time.time()
        
        try:
            print(f"[{i}/{len(tickets)}] Ticket {ticket_number}...", end="\r")
            
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': ticket_input}
                ],
                response_format={ "type": "json_object" },
                temperature=0.1
            )
            
            ai_content = json.loads(response.choices[0].message.content)
            
            t_end = time.time()
            duration = round(t_end - t_start, 2)

            record = {
                "ticket_number": ticket_number,
                "original_status": ticket.get('ticket_status'),
                "new_status": ai_content.get('new_status', 'Nezařazeno'),
                "reason": ai_content.get('reason', ''),
                "problem_summary": ai_content.get('problem_summary', ''),
                "automation_suggestion": ai_content.get('automation_suggestion', ''),
                "minimization_suggestion": ai_content.get('minimization_suggestion', ''),
                "analysis_time_seconds": duration
            }
            detailed_log.append(record)
            
        except Exception as e:
            print(f"\n❌ Chyba u ticketu {ticket_number}: {e}")
            detailed_log.append({
                "ticket_number": ticket_number, 
                "new_status": "CHYBA", 
                "reason": str(e),
                "analysis_time_seconds": 0
            })

    total_time = time.time() - start_analysis_time

    # ZMĚNA: Struktura finálního JSONu s hlavičkou (summary)
    final_output = {
        "metadata": {
            "analysis_date": datetime.now().isoformat(),
            "model_used": MODEL_NAME,
            "input_file": input_path
        },
        "summary": {
            "total_tickets_processed": len(detailed_log),
            "total_time_seconds": round(total_time, 2),
            "average_time_per_ticket": round(total_time / len(tickets), 2) if tickets else 0
        },
        "tickets": detailed_log
    }

    print(f"\n💾 Ukládám strukturovaný JSON log...")
    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON uložen: {JSON_OUTPUT}")

    generate_stats_csv(detailed_log)

if __name__ == "__main__":
    run_analysis(INPUT_FILE)