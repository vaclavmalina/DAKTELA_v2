import streamlit as st
from openai import OpenAI
import time

def test_ollama():
    print("--- DIAGNOSTIKA CLOUD AI (OpenAI) ---")
    start_time = time.time()
    
    #Nastavení API klíče
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    try:
        # 1. Krok: Kontrola, zda API odpovídá
        print("Krok 1: Kontrola spojení se serverem OpenAI...")
        
        # 2. Krok: Odeslání dotazu
        print("Krok 2: Posílám dotaz...")
        response = client.chat.completions.create(
            model='gpt-4o-mini', # ZMĚNA: Úprava na existující model (gpt-5 zatím není veřejný)
            messages=[
                {
                    'role': 'system',
                    'content': 'Jsi stručný asistent. Odpovídej pouze česky.'
                },
                {
                    'role': 'user',
                    'content': 'Napiš přesně tuto větu: "AI spojení navázáno."'
                },
            ]
        )
        
        # 3. Krok: Výpis výsledku
        end_time = time.time()
        print(f"Krok 3: Hotovo! (Čas zpracování: {end_time - start_time:.2f} s)")
        print(f"\nOdpověď od AI: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"\nCHYBA: Nepodařilo se spojit s AI.")
        print(f"Detail chyby: {e}")
        print("\nMOŽNÉ PŘÍČINY:")
        print("1. Neplatný nebo expirovaný OpenAI API klíč.")
        print("2. Chybějící připojení k internetu.")
        print("3. Nedostatečný kredit na OpenAI účtu.")

if __name__ == "__main__":
    test_ollama()