import os
from openai import OpenAI
from dotenv import load_dotenv

# .env einlesen (falls vorhanden)
load_dotenv()

# API-Key laden
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Kein OPENAI_API_KEY gefunden! Trage ihn in .env oder secrets.toml ein.")

print(f"✅ Key gefunden (beginnt mit): {api_key[:10]}...")

# Client erzeugen
client = OpenAI(api_key=api_key)

try:
    # ganz einfacher Test: kleines Chat-Completion
    resp = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": "Sag nur: TEST OK"}],
        max_tokens=20
    )
    print("Antwort von OpenAI:", resp.choices[0].message.content.strip())
    print("🎉 Dein Key funktioniert!")
except Exception as e:
    print("❌ Fehler beim API-Aufruf:", str(e))
    if "insufficient_quota" in str(e):
        print("👉 Hinweis: Dein Key ist gültig, aber dein Projekt hat kein Guthaben oder du nutzt den falschen Key-Typ.")
