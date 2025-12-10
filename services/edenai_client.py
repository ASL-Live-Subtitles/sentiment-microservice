import os
import requests
from dotenv import load_dotenv

load_dotenv()

class EdenAIClient:
    def __init__(self):
        self.api_key = os.getenv("EDENAI_API_KEY")
        self.base_url = "https://api.edenai.run/v2/text/sentiment_analysis"

    def analyze_sentiment(self, text: str, providers: str = "google", language: str = "en"):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "providers": providers,
            "language": language,
            "text": text
        }
        response = requests.post(self.base_url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
