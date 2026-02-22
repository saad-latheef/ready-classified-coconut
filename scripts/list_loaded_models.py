import requests
import json

ROBOFLOW_API_URL = "http://localhost:9001"

def check_models():
    try:
        # Check models endpoint
        response = requests.get(f"{ROBOFLOW_API_URL}/models")
        if response.status_code == 200:
            models = response.json()
            print("Successfully connected to Inference Server.")
            print("Loaded Models:")
            print(json.dumps(models, indent=2))
            
            # Check for our specific model
            target_model = "my-first-project-8caij/4"
            if any(target_model in m.get('model_id', '') for m in models.get('models', [])):
                print(f"\n✅ Model {target_model} is LOADED and ready.")
            else:
                print(f"\n❌ Model {target_model} is NOT in the loaded list.")
        else:
            print(f"Failed to get models: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to inference server: {e}")

if __name__ == "__main__":
    check_models()
