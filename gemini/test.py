import google.generativeai as genai
import json

# Nastavení klíče
genai.configure(api_key="GEMINI_API_KEY")
model = genai.GenerativeModel('gemini-1.5-flash')

def test_gemini():
    prompt = "Analyzuj tento ticket a urči kategorii (Technický dotaz, Fakturace, Pochvala)."
    ticket_text = "Dobrý den, nemůžu se přihlásit do systému, hází mi to chybu 500."
    
    response = model.generate_content(f"{prompt}\n\nObsah ticketu: {ticket_text}")
    print(response.text)

if __name__ == "__main__":
    test_gemini()