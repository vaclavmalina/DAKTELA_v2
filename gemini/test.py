import streamlit as st  # PŘIDÁNO: Nutné pro st.secrets
from google import genai
import json

# 1. Načtení klíče ze secrets.toml
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# 2. Inicializace AI klienta (PŘIDÁNO: client musí existovat)
client = genai.Client(api_key=GEMINI_API_KEY)

def test_gemini():
    print("Odesílám dotaz do Gemini API...")
    try:
        # Volání modelu
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents="Analyzuj tento ticket a urči kategorii (Technický dotaz, Fakturace, Pochvala). Odpověz pouze v JSON." + \
                     "\n\nObsah ticketu: Dobrý den, nemůžu se přihlásit do systému, hází mi to chybu 500."
        )
        
        print("\n--- ODPOVĚĎ OD AI ---")
        print(response.text)
        print("---------------------")
        
    except Exception as e:
        print(f"Nastala chyba: {e}")

if __name__ == "__main__":
    test_gemini()