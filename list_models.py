from google import genai
import os

client = genai.Client(api_key="AIzaSyB5dGPsk6Ec1HITdiOJF50NVuVPAQoaVKY")

print("Checking available Gemini models...")
try:
    for model in client.models.list():
        print(f"Model: {model.name} (Display Name: {model.display_name})")
except Exception as e:
    print(f"Error: {e}")
