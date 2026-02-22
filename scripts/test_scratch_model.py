import requests
import cv2
import base64
import json

# Configuration
ROBOFLOW_API_URL = "http://localhost:9001"
# Use the new scratch model ID and API Key
MODEL_ID = "my-first-project-8caij/4"
API_KEY = "CScNG4RG0ERfvFWW0q5M"

def test_scratch_model():
    print(f"Testing model {MODEL_ID}...")
    
    # Try to get an image from the webcam or use a dummy
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("Failed to grab dummy frame, using black image")
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Encode as JPG then Base64
    _, buffer = cv2.imencode('.jpg', frame)
    img_str = base64.b64encode(buffer).decode('utf-8')
    
    # Roboflow inference server URL format
    url = f"{ROBOFLOW_API_URL}/{MODEL_ID}?api_key={API_KEY}"
    
    try:
        response = requests.post(url, data=img_str, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if response.status_code == 200:
            results = response.json()
            print("Success! Response received:")
            print(json.dumps(results, indent=2))
        else:
            print(f"Failed with status code: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error connecting to inference server: {e}")

if __name__ == "__main__":
    test_scratch_model()
