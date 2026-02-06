import ollama
import time

def test_ollama():
    print("--- DIAGNOSTIKA LOKÁLNÍ AI ---")
    start_time = time.time()
    
    try:
        # 1. Krok: Kontrola, zda Ollama vůbec odpovídá
        print("Krok 1: Kontrola spojení se serverem Ollama...")
        # (Knihovna ollama automaticky komunikuje s http://localhost:11434)
        
        # 2. Krok: Odeslání dotazu
        print("Krok 2: Posílám dotaz modelu Llama 3 (toto může trvat pár sekund)...")
        response = ollama.chat(
        model='llama3.2:1b', 
        messages=[

            {

                'role': 'system',

                'content': 'Jsi stručný asistent. Odpovídej pouze česky.'

            },

            {

                'role': 'user',

                'content': 'Napiš přesně tuto větu: "AI spojení navázáno."'

            },

        ],
        options={'num_ctx': 4096} # ZMĚNA: Omezení kontextu pro vyšší rychlost
)
        
        # 3. Krok: Výpis výsledku
        end_time = time.time()
        print(f"Krok 3: Hotovo! (Čas zpracování: {end_time - start_time:.2f} s)")
        print(f"\nOdpověď od AI: {response['message']['content']}")
        
    except Exception as e:
        print(f"\nCHYBA: Nepodařilo se spojit s AI.")
        print(f"Detail chyby: {e}")
        print("\nMOŽNÉ PŘÍČINY:")
        print("1. Aplikace Ollama neběží (zkontrolujte ikonu lamy u hodin).")
        print("2. Model 'llama3' není stažený (spusťte v terminálu: ollama pull llama3).")
        print("3. Málo operační paměti RAM pro spuštění modelu.")

if __name__ == "__main__":
    test_ollama()