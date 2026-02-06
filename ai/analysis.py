import json
import ollama
import os
import sys
import csv
from collections import Counter

# Import promptu
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from prompt import SYSTEM_PROMPT
except ImportError:
    print("CHYBA: Nenalezen soubor 'prompt.py'.")
    sys.exit(1)

# --- KONFIGURACE ---
MODEL_NAME = 'llama3.2:3b'
INPUT_FILE = 'data_technicka_VSE_20260206_094050.json'
JSON_OUTPUT = 'ai_analysis_export.json'
CSV_OUTPUT = 'ai_analysis_export.csv' # Název výsledného CSV souboru

def format_ticket_history(ticket):
    """
    ULTRA-LEHKÝ formát pro CPU (i7).
    Ořezává texty na minimum pro rychlé zpracování.
    """
    summary = f"Téma: {ticket.get('ticket_name')}\n"
    
    activities = sorted(ticket.get('activities', []), key=lambda x: x.get('activity_number', 0))
    if not activities: return summary + "Bez textu."

    # 1. První zpráva (Co se děje)
    first = activities[0]
    raw_text_1 = first.get('activity_text', '')
    clean_text_1 = raw_text_1[:350].replace('\n', ' ').replace(';', ',') # Odstraníme středníky, ať nerozbíjí CSV
    summary += f"Klient: {clean_text_1}...\n"

    # 2. Hledáme INTERNÍ KOMENTÁŘ
    comments = [a for a in activities if a.get('activity_type') == 'COMMENT']
    
    if comments:
        last_comment = comments[-1]
        comm_text = last_comment.get('activity_text', '')[:350].replace('\n', ' ').replace(';', ',')
        summary += f"Interní diagnóza: {comm_text}...\n"
    else:
        last = activities[-1]
        if last != first:
            clean_text_last = last.get('activity_text', '')[:350].replace('\n', ' ').replace(';', ',')
            summary += f"Řešení: {clean_text_last}...\n"

    return summary

def save_statistics_to_csv(results):
    """
    Vypočítá statistiku a uloží ji do CSV souboru pro Excel.
    """
    total = len(results)
    if total == 0: return

    # Získání kategorií
    categories = []
    for r in results:
        # Robustní získání kategorie
        cat = r.get('category') or r.get('navrzeny_status') or r.get('status') or "Nezařazeno"
        categories.append(cat)

    counts = Counter(categories)
    
    # Výpis do terminálu (pro kontrolu)
    print("\n" + "="*60)
    print(f"📊 STATISTIKA ({total} ticketů) -> Ukládám do CSV...")
    print("="*60)

    try:
        # Uložení do CSV
        with open(CSV_OUTPUT, 'w', newline='', encoding='utf-8-sig') as csvfile:
            # Používáme středník jako oddělovač (standard pro český Excel)
            writer = csv.writer(csvfile, delimiter=';')
            
            # Hlavička
            writer.writerow(['Kategorie ticketu', 'Počet ticketů', 'Zastoupení (%)'])
            
            # Data
            for cat, count in counts.most_common():
                percentage = (count / total) * 100
                # Formátujeme procenta s desetinnou čárkou pro český Excel
                percentage_str = f"{percentage:.1f}".replace('.', ',')
                
                writer.writerow([cat, count, percentage_str])
                print(f"{cat:<30} | {count:<5} | {percentage:.1f} %")
                
        print(f"\n✅ CSV soubor úspěšně vytvořen: {CSV_OUTPUT}")
        print("   (Otevřete v Excelu, data jsou oddělena středníkem)")

    except Exception as e:
        print(f"❌ Chyba při ukládání CSV: {e}")

def run_analysis(input_path):
    if not os.path.exists(input_path):
        print(f"❌ Soubor {input_path} nenalezen.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        tickets = json.load(f)

    print(f"🚀 Zahajuji analýzu {len(tickets)} ticketů na CPU (Model: {MODEL_NAME})...")
    
    analyzed_data = []

    for i, ticket in enumerate(tickets, 1):
        ticket_input = format_ticket_history(ticket)
        
        try:
            print(f"[{i}/{len(tickets)}] Zpracovávám ticket {ticket.get('ticket_number')}...", end="\r")
            
            response = ollama.chat(
                model=MODEL_NAME,
                format='json',
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': ticket_input}
                ],
                options={
                    'temperature': 0.1,
                    'num_ctx': 1024, # Optimalizace pro CPU
                    'num_thread': 4 
                }
            )
            
            result = json.loads(response['message']['content'])
            result['ticket_number'] = ticket.get('ticket_number')
            analyzed_data.append(result)
            
        except Exception as e:
            analyzed_data.append({"ticket_number": ticket.get('ticket_number'), "category": "CHYBA", "reason": str(e)})

    # Uložení JSON výsledků (pro jistotu)
    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(analyzed_data, f, ensure_ascii=False, indent=2)
    
    # Uložení CSV (to co chcete)
    save_statistics_to_csv(analyzed_data)

if __name__ == "__main__":
    run_analysis(INPUT_FILE)