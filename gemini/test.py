import streamlit as st
from google import genai

# Načtení z secrets.toml
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def test_gemini():
    print("Odesílám dotaz do Gemini API (model gemini-2.0-flash)...")
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents="Napiš přesně tuto větu: 'AI spojení navázáno.'"
        )
        print(f"\nOdpověď: {response.text}")
    except Exception as e:
        print(f"Nastala chyba: {e}")

if __name__ == "__main__":
    test_gemini()