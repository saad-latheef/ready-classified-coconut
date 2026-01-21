import google.generativeai as genai

GEMINI_API_KEY = "AIzaSyB5dGPsk6Ec1HITdiOJF50NVuVPAQoaVKY"
genai.configure(api_key=GEMINI_API_KEY)

test_models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash-exp", "gemini-2.5-flash", "gemini-pro"]

for model_name in test_models:
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("test")
        print(f"SUCCESS: {model_name}")
        break
    except Exception as e:
        print(f"FAILED: {model_name} - {e}")
