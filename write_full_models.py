import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    models = client.models.list()
    with open("full_models_list.txt", "w", encoding="utf-8") as f:
        for model in models:
            f.write(f"{model.name}\n")
    print("Models written to full_models_list.txt")
except Exception as e:
    print(f"Error: {e}")
