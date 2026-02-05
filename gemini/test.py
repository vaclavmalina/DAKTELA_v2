import streamlit as st
from google import genai
import json

# Načtení klíče
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=GEMINI_API_KEY)

def diagnose_and_test():
    print("--- DIAGNOSTIKA MODELŮ ---")
    try:
        # Vypíšeme seznam dostupných modelů pro tvůj klíč
        for m in client.models.list():
            print(f"Dostupný model: {m.name}")
            
        print("\n--- TEST VOLÁNÍ (Gemini 1.5 Flash) ---")
        # Zkusíme volat model bez prefixu 'models/'
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents="Napiš 'Ahoj, jsem online' pokud mě slyšíš."
        )
        print(f"Odpověď: {response.text}")
        
    except Exception as e:
        print(f"Nastala chyba: {e}")

if __name__ == "__main__":
    diagnose_and_test()