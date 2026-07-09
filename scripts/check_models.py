import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

response = requests.get(url)

if response.status_code == 200:
    models = response.json().get("models", [])

    print("Available Gemini Models:\n")

    for model in models:
        if "generateContent" in model.get("supportedGenerationMethods", []):
            print(f"- {model['name'].replace('models/', '')}")
else:
    print("Error:", response.text)