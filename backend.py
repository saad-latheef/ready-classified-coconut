"""
Multi-Agent Backend for Coconut Quality Checker
Integrates 5 Specialized Agents: Ingestion, ML, Analysis, Trend, Explanation (Gemini).
"""

import cv2
import time
import sqlite3
import json
import threading
import os
import math
import serial
import numpy as np
from google import genai
from google.genai import types
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from inference_sdk import InferenceHTTPClient
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for Next.js frontend

# --- CONFIGURATION ---
ROBOFLOW_API_URL = "http://localhost:9001"
ROBOFLOW_API_KEY = "vX3xJcrhB0TPB71Q5RSc"
ROBOFLOW_MODEL_ID = "my-first-project-nlg8h/5"
GEMINI_API_KEY = "AIzaSyB5dGPsk6Ec1HITdiOJF50NVuVPAQoaVKY"  # Hardcoded API key

# Dimension Measurement Configuration
CM_PER_PIXEL = 0.06014
MIN_AREA = 1000  # Relaxed from 5000 to allow smaller objects
MAX_AREA = 500000  # Increased from 300000 to allow larger objects
BORDER_MARGIN = 10
HEIGHT_OFFSET = 0.0  # Set to 0 since user said 0 should be 0
HEIGHT_CALIBRATION_FACTOR = 1.67 # Factor to fix 9cm showing as 15cm (15/9)
WEIGHT_CALIBRATION_FACTOR = 3.165 # Factor to fix 300g displaying as 94.8g

# Hardware Serial Configuration
SERIAL_PORT = 'COM10'
BAUD_RATE = 115200

# Initialize Clients
ml_client = InferenceHTTPClient(api_url=ROBOFLOW_API_URL, api_key=ROBOFLOW_API_KEY)

# Configure Gemini
gemini_client = None
DEFAULT_MODEL = 'gemini-2.5-flash-lite' # Latest Lite model as requested

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print(f"[System] Gemini v2 SDK initialized. Using {DEFAULT_MODEL} as default.")
    except Exception as e:
        print(f"[System] Gemini Client Error: {e}")
else:
    print("[System] No Gemini API key found. Detailed analysis disabled.")

# Global State
latest_frame = None
latest_analysis = None
lock = threading.Lock()
camera_index = 0
# File paths
DB_PATH = 'coconuts.db'
CAPTURES_DIR = 'captures'
if not os.path.exists(CAPTURES_DIR):
    os.makedirs(CAPTURES_DIR)

class SensorAgent:
    """Agent for reading real-time sensor data from USB Serial (NodeMCU)"""
    def __init__(self, port=SERIAL_PORT, baud=BAUD_RATE):
        self.port = port
        self.baud = baud
        self.data = {
            "height": 0.0,
            "weight": 0.0,
            "water": 0.0
        }
        self.lock = threading.Lock()
        self.connected = False
        self.thread = threading.Thread(target=self._read_serial, daemon=True)
        self.thread.start()

    def _read_serial(self):
        print(f"[SensorAgent] Starting serial thread for port {self.port} at {self.baud} baud...")
        try:
            print(f"[SensorAgent] Attempting to connect to {self.port}...")
            ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(2)
            print(f"[SensorAgent] SUCCESS: Connected to {self.port}")
            self.connected = True
            
            while True:
                if ser.in_waiting > 0:
                    try:
                        raw_line = ser.readline()
                        line = raw_line.decode('utf-8', errors='ignore').strip()
                        if line:
                            parts = line.split(',')
                            if len(parts) == 3:
                                try:
                                    h_val = float(parts[0])
                                    w_val = float(parts[1])
                                    wat_val = float(parts[2])
                                    
                                    with self.lock:
                                        self.data["height"] = h_val
                                        self.data["weight"] = w_val
                                        self.data["water"] = wat_val
                                except ValueError as ve:
                                    print(f"[SensorAgent] Data conversion error: {ve} in line '{line}'")
                            else:
                                if line:
                                    print(f"[SensorAgent] Unexpected data format (expected 3 parts): '{line}'")
                    except Exception as read_err:
                        print(f"[SensorAgent] Read Error: {read_err}")
                        break # Connection lost or error, exit thread
            ser.close()
        except Exception as e:
            self.connected = False
            print(f"[SensorAgent] Serial Connection Failed: {e}. One-time check complete, thread terminating.")

    def get_data(self):
        with self.lock:
            processed_data = self.data.copy()
            
        # Apply Calibration globally
        # Height: Apply scaling factor and offset (0 is 0, 7 is 15)
        processed_data["height"] = round(processed_data["height"] * HEIGHT_CALIBRATION_FACTOR + HEIGHT_OFFSET, 2)
        
        # Weight: Apply calibration factor
        processed_data["weight"] = round(processed_data["weight"] * WEIGHT_CALIBRATION_FACTOR, 1)
        
        return processed_data

# Global Sensor Agent instance
sensor_agent = None

def get_sensor_agent():
    global sensor_agent
    if sensor_agent is None:
        # Avoid double initialization in Flask debug mode
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
            sensor_agent = SensorAgent()
        else:
            # Placeholder for the parent process in debug mode
            class MockSensorAgent:
                def get_data(self): return {"height": 0.0, "weight": 0.0, "water": 0.0}
            sensor_agent = MockSensorAgent()
    return sensor_agent

# Initialize agent (will be actual agent in child process, mock in parent)
sensor_agent = get_sensor_agent()

# Database initialization will be called in the main block

# --- AGENTS IMPLEMENTATION ---

class IngestionAgent:
    def __init__(self, src=1):  # Changed to 1 for USB webcam
        print(f"[IngestionAgent] Initializing camera with source index {src}...")
        # Use CAP_DSHOW for faster startup on Windows
        self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
             print(f"[IngestionAgent] Camera {src} failed to open. Falling back to camera 0...")
             self.cap.release()
             self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
             
        if self.cap.isOpened():
            print(f"[IngestionAgent] SUCCESS: Camera initialized.")
        else:
            print("[IngestionAgent] ERROR: Could not open any camera source")

    def get_frame(self):
        if not self.cap or not self.cap.isOpened():
            return None
        ret, frame = self.cap.read()
        if not ret:
            print("[IngestionAgent] Warning: Failed to read frame from camera")
            return None
        return frame

    def release(self):
        if self.cap:
            self.cap.release()
            print("[IngestionAgent] Camera released")

class MLAgent:
    def detect(self, frame):
        try:
            # inference_sdk handles the API call to local docker
            results = ml_client.infer(frame, model_id=ROBOFLOW_MODEL_ID)
            return results
        except Exception as e:
            print(f"ML Error: {e}")
            return {'predictions': []}

class DimensionAgent:
    """Computer Vision agent for measuring coconut dimensions using ellipse fitting"""
    
    def measure(self, frame, bbox=None):
        """
        Measure coconut dimensions using CV ellipse fitting
        Args:
            frame: Input image
            bbox: Optional bounding box (x, y, width, height) from ML to focus on region
        Returns:
            dict with 'major_axis_cm', 'minor_axis_cm', 'visualization' or None
        """
        try:
            # If bbox provided, crop to region of interest
            if bbox:
                x, y, w, h = bbox
                roi = frame[max(0, y):min(frame.shape[0], y+h), 
                           max(0, x):min(frame.shape[1], x+w)]
                offset_x, offset_y = max(0, x), max(0, y)
                print(f"[DimensionAgent] Using bbox: ({x}, {y}, {w}, {h})")
            else:
                roi = frame
                offset_x, offset_y = 0, 0
                print(f"[DimensionAgent] No bbox provided, using full frame")
            
            # Convert to grayscale and blur
            imgGray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            imgBlur = cv2.GaussianBlur(imgGray, (11, 11), 0)
            
            # Threshold using OTSU
            _, imgThresh = cv2.threshold(imgBlur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Clean up noise
            kernel = np.ones((5, 5), np.uint8)
            imgClean = cv2.morphologyEx(imgThresh, cv2.MORPH_OPEN, kernel, iterations=2)
            
            # Find contours
            contours, _ = cv2.findContours(imgClean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            print(f"[DimensionAgent] Found {len(contours)} contours")
            
            best_measurement = None
            
            for idx, cnt in enumerate(contours):
                area = cv2.contourArea(cnt)
                print(f"[DimensionAgent] Contour {idx}: area={area:.0f}")
                
                # Filter by size
                if MIN_AREA < area < MAX_AREA:
                    # Only check border if we're NOT using a bbox (full frame mode)
                    # When using bbox, the coconut fills the ROI so border check fails
                    if not bbox:
                        x, y, w, h = cv2.boundingRect(cnt)
                        if (x < BORDER_MARGIN or y < BORDER_MARGIN or
                            (x + w) > (roi.shape[1] - BORDER_MARGIN) or
                            (y + h) > (roi.shape[0] - BORDER_MARGIN)):
                            print(f"[DimensionAgent] Contour {idx} rejected: too close to border")
                            continue
                    
                    # Fit ellipse
                    if len(cnt) >= 5:
                        ellipse = cv2.fitEllipse(cnt)
                        (cx, cy), (d1, d2), angle = ellipse
                        
                        # Calculate real dimensions
                        major_axis_cm, minor_axis_cm = self._calculate_axes(d1, d2)
                        
                        best_measurement = {
                            'major_axis_cm': major_axis_cm,
                            'minor_axis_cm': minor_axis_cm,
                            'ellipse': ((cx + offset_x, cy + offset_y), (d1, d2), angle),
                            'center': (cx + offset_x, cy + offset_y)
                        }
                        print(f"[DimensionAgent] ✓ Measurement successful: A={major_axis_cm:.2f}cm, B={minor_axis_cm:.2f}cm")
                        break  # Use first valid measurement
                    else:
                        print(f"[DimensionAgent] Contour {idx} rejected: not enough points for ellipse")
                else:
                    print(f"[DimensionAgent] Contour {idx} rejected: area {area:.0f} outside range [{MIN_AREA}, {MAX_AREA}]")
            
            if not best_measurement:
                print(f"[DimensionAgent] ✗ No valid measurement found")
            
            return best_measurement
            
        except Exception as e:
            print(f"Dimension measurement error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calculate_axes(self, d1, d2):
        """Calculate major and minor axes in cm"""
        if d1 > d2:
            major_cm = d1 * CM_PER_PIXEL
            minor_cm = d2 * CM_PER_PIXEL
        else:
            major_cm = d2 * CM_PER_PIXEL
            minor_cm = d1 * CM_PER_PIXEL
        return round(major_cm, 2), round(minor_cm, 2)
    
    def draw_measurement(self, frame, measurement):
        """Draw measurement visualization on frame"""
        if not measurement:
            return frame
        
        (cx, cy), (d1, d2), angle = measurement['ellipse']
        cx, cy = int(cx), int(cy)
        angle_rad = math.radians(angle)
        
        # Draw ellipse
        cv2.ellipse(frame, measurement['ellipse'], (0, 255, 255), 2)
        
        # Identify major and minor axes
        if d1 > d2:
            major_r = d1 / 2
            minor_r = d2 / 2
            major_angle = angle_rad
            minor_angle = angle_rad + math.pi / 2
        else:
            major_r = d2 / 2
            minor_r = d1 / 2
            major_angle = angle_rad + math.pi / 2
            minor_angle = angle_rad
        
        # Draw major axis (red)
        p1_x = int(cx + major_r * math.cos(major_angle))
        p1_y = int(cy + major_r * math.sin(major_angle))
        p2_x = int(cx - major_r * math.cos(major_angle))
        p2_y = int(cy - major_r * math.sin(major_angle))
        cv2.line(frame, (p1_x, p1_y), (p2_x, p2_y), (0, 0, 255), 2)
        
        # Draw minor axis (blue)
        p3_x = int(cx + minor_r * math.cos(minor_angle))
        p3_y = int(cy + minor_r * math.sin(minor_angle))
        p4_x = int(cx - minor_r * math.cos(minor_angle))
        p4_y = int(cy - minor_r * math.sin(minor_angle))
        cv2.line(frame, (p3_x, p3_y), (p4_x, p4_y), (255, 0, 0), 2)
        
        # Draw labels
        cv2.putText(frame, f"A={measurement['major_axis_cm']:.2f} cm", 
                   (cx - 40, cy - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.putText(frame, f"B={measurement['minor_axis_cm']:.2f} cm", 
                   (cx - 40, cy - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        return frame

class AnalysisAgent:
    def analyze(self, predictions, frame_shape, dimension_data=None, manual_weight=None):
        # Default assessment
        assessment = {
            "weight": 0, "diameter": 0, "waterContent": 0,
            "shellColor": "unknown", "shakeSound": "unknown",
            "moldSpots": False, "cracksDamage": False,
            "score": 0, "grade": "Ungraded",
            "issues": [], "recommendations": [],
            "predictions": predictions
        }

        if not predictions.get('predictions', []):
             return assessment

        # Logic for the "Best" coconut found (highest confidence)
        preds = predictions.get('predictions', [])
        best_pred = max(preds, key=lambda x: x['confidence'])
        
        # 1. Physical Measurements - Combined ML, CV and Hardware Sensors
        real_sensors = sensor_agent.get_data()
        
        # Height and Weight are now pre-calibrated in sensor_agent.get_data()
        assessment['height'] = real_sensors['height']
        
        # Use manual weight if provided, otherwise use sensor
        if manual_weight is not None:
            try:
                assessment['weight'] = float(manual_weight)
                print(f"[AnalysisAgent] Using MANUAL weight: {assessment['weight']}g")
            except:
                assessment['weight'] = real_sensors['weight']
        else:
            assessment['weight'] = real_sensors['weight']
        
        # Water content from Analog Sensor
        assessment['waterContent'] = real_sensors['water']

        # Dimensions from Computer Vision
        if dimension_data:
            assessment['diameter'] = dimension_data['major_axis_cm']
            assessment['majorAxis'] = dimension_data['major_axis_cm']
            assessment['minorAxis'] = dimension_data['minor_axis_cm']
        else:
            width_px = best_pred['width']
            diameter_cm = round(width_px * 0.1, 1)
            assessment['diameter'] = diameter_cm
            assessment['majorAxis'] = diameter_cm
            assessment['minorAxis'] = round(diameter_cm * 0.9, 1)

        # 1.5 Physics Calculations
        # V = (π / 6) * A * B * H
        major = assessment['majorAxis']
        minor = assessment['minorAxis']
        height = assessment['height']
        
        volume = (math.pi / 6.0) * major * minor * height
        assessment['volume'] = round(volume, 2)
        
        if volume > 0:
            assessment['density'] = round(assessment['weight'] / volume, 3)
        else:
            assessment['density'] = 0.0
        
        # 2. Issues Detection
        cls = best_pred['class']
        if 'crack' in cls.lower():
            assessment['cracksDamage'] = True
            assessment['issues'].append("Visible crack detected")
        if 'mold' in cls.lower():
            assessment['moldSpots'] = True
            assessment['issues'].append("Mold spots detected")

        # 3. Grading Logic
        score = 100
        if assessment['cracksDamage']: 
            score -= 40
            if "Crack/Damage detected" not in assessment['issues']:
                assessment['issues'].append("Crack/Damage detected")
            
        if assessment['moldSpots']: score -= 30
        
        # New Sizing Rule: 13cm (L) x 10cm (W) is the minimum for Grade A
        is_undersized = assessment['majorAxis'] < 13 or assessment['minorAxis'] < 10
        if is_undersized:
            score -= 20
            if "Undersized (<13x10cm)" not in assessment['issues']:
                assessment['issues'].append("Undersized (<13x10cm)")
        
        assessment['score'] = max(0, score)
        
        # Base Grading
        if score >= 90: grade = "A"
        elif score >= 70: grade = "B"
        elif score >= 50: grade = "C"
        else: grade = "D"

        # CAP AT GRADE B IF UNDERSIZED
        if is_undersized and grade == "A":
            grade = "B"
            print(f"[AnalysisAgent] Capping Grade at B due to size {assessment['majorAxis']}x{assessment['minorAxis']}")

        # FORCE GRADE C/D IF CRACKS EXIST
        if assessment['cracksDamage']:
            if grade in ["A", "B"]:
                grade = "C"
                print(f"[AnalysisAgent] Downgrading to C due to cracks (Original score {score})")
        
        assessment['grade'] = grade

        # 4. Recommendations
        if assessment['grade'] == "A":
            assessment['recommendations'].append("Premium Quality - Package for retail")
        elif assessment['grade'] == "D":
            assessment['recommendations'].append("Discard or use for processing")
        
        # 5. Metadata
        cls_lower = cls.lower()
        if 'green' in cls_lower:
            assessment['shellColor'] = "Green"
        elif 'brown' in cls_lower:
            assessment['shellColor'] = "Brown"
        else:
            assessment['shellColor'] = "Unknown"
        
        return assessment

class GeminiAnalysisAgent:
    """Uses Gemini AI to provide detailed coconut variety and quality analysis with Visual support"""
    def analyze(self, assessment, frame=None):
        if not gemini_client:
            return "Gemini AI not available. Set GEMINI_API_KEY to enable detailed analysis."
        
        try:
            # Prepare image part if frame is available
            contents = []
            if frame is not None:
                success, buffer = cv2.imencode('.jpg', frame)
                if success:
                    print(f"[GeminiVision] Image encoded successfully. Size: {len(buffer)} bytes")
                    from google.genai import types
                    image_bytes = buffer.tobytes()
                    contents.append(types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'))
                else:
                    print("[GeminiVision] ERROR: Failed to encode frame to JPEG")
            else:
                print("[GeminiVision] WARNING: No frame provided for visual analysis")
            
            # Get the ML class name for more context
            ml_class = "Unknown"
            if assessment.get('predictions') and assessment['predictions'].get('predictions'):
                preds = assessment['predictions'].get('predictions', [])
                if preds:
                    ml_class = max(preds, key=lambda x: x['confidence'])['class']
            
            prompt = f"""You are an expert coconut quality analyst. Provide a COMPLETE ANALYSIS REPORT based on this data:

Detection: {ml_class}
Grade: {assessment['grade']}
Score: {assessment['score']}/100
Dimensions: {assessment['majorAxis']} cm (L) x {assessment['minorAxis']} cm (W) x {assessment['height']} cm (H)
Weight: {assessment['weight']} g
Shell Color: {assessment['shellColor']}
Mold Spots: {'Yes' if assessment['moldSpots'] else 'No'}
Cracks/Damage: {'Yes' if assessment['cracksDamage'] else 'No'}
Issues: {', '.join(assessment['issues']) if assessment['issues'] else 'None'}

Provide:
1. **Quality Synopsis**: Overall health and quality summary
2. **Physical Analysis**: Analyze maturity using Weight ({assessment['weight']}g), Volume ({assessment['volume']}cm³), and Density ({assessment['density']}g/cm³)
3. **Internal Content**: Estimate water content/meat thickness based on density and shell color ({assessment['shellColor']})
4. **Usage Recommendation**: Best culinary or industrial uses
5. **Maintenance Advice**: Storage tips for this specific grade

Keep it professional and detailed. Maximum 5-6 sentences.

VISUAL CHECK (Urgently Critical):
Examine the high-resolution image of the coconut shell with extreme care. 
Look for ANY sign of:
- Deep structural cracks or splits.
- Hairline cracks or thin fissures.
- Punctures, dents, or impact damage on the shell.
- Any leakage or wet spots indicating a breach.

INSTRUCTIONS:
1. If ANY such defect is visible, you MUST include the exact string "CRACK_FOUND" (all caps) at the very start of your response.
2. Detailed description: In the 'Quality Synopsis', provide a specific description of what you see (e.g., "haireline crack on the side", "deep split near the top").
3. If no cracks/damage are visible, omit the "CRACK_FOUND" string.
"""
            contents.append(prompt)
            print(f"[GeminiVision] --- ANALYSIS START --- Using Model: {DEFAULT_MODEL}")
            
            response = gemini_client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=contents
            )
            raw_response = response.text
            print(f"[GeminiVision] RAW RESPONSE: {raw_response[:200]}...") # Log first 200 chars
            print(f"[GeminiVision] Final Decision - Crack identified: {'CRACK_FOUND' in raw_response.upper()}")
            return raw_response
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                return "AI Analysis Quota Reached. Please wait a moment and try again."
            return f"Gemini Analysis Error: {error_str}"

class TrendAgent:
    def save(self, assessment, frame=None):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create a unique ID
        import uuid
        record_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        # Save image if provided
        image_path = None
        if frame is not None:
            image_filename = f"capture_{record_id}.jpg"
            full_path = os.path.join(CAPTURES_DIR, image_filename)
            cv2.imwrite(full_path, frame)
            image_path = full_path
            print(f"[TrendAgent] Image saved to {image_path}")
        
        assessment['id'] = record_id
        assessment['createdAt'] = created_at
        assessment['imagePath'] = image_path

        cursor.execute('''
            INSERT INTO assessments (
                id, weight, diameter, height, majorAxis, minorAxis, volume, density, waterContent, shellColor, shakeSound,
                moldSpots, cracksDamage, score, grade, issues, recommendations, predictions, geminiAnalysis, createdAt, imagePath
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record_id, assessment['weight'], assessment['diameter'], assessment['height'],
            assessment.get('majorAxis', 0), assessment.get('minorAxis', 0),
            assessment['volume'], assessment['density'], assessment['waterContent'],
            assessment['shellColor'], assessment['shakeSound'],
            1 if assessment['moldSpots'] else 0, 1 if assessment['cracksDamage'] else 0,
            assessment['score'], assessment['grade'],
            json.dumps(assessment['issues']), json.dumps(assessment['recommendations']),
            json.dumps(assessment['predictions']), assessment['geminiAnalysis'], created_at, image_path
        ))
        
        conn.commit()
        conn.close()
        return {**assessment, "id": record_id, "createdAt": created_at}

    def get_history(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assessments ORDER BY createdAt DESC LIMIT 100")
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            d = dict(row)
            d['issues'] = json.loads(d['issues'])
            d['recommendations'] = json.loads(d['recommendations'])
            d['predictions'] = json.loads(d['predictions'])
            d['geminiAnalysis'] = d.get('geminiAnalysis', '')
            d['moldSpots'] = bool(d['moldSpots'])
            d['cracksDamage'] = bool(d['cracksDamage'])
            history.append(d)
        
        conn.close()
        return history
    
    def delete(self, record_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM assessments WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

# --- INSTANTIATE AGENTS ---
# Agents will be initialized in the main block or on-demand
ingestion = None
ml_agent = MLAgent()
dimension_agent = DimensionAgent()
analysis_agent = AnalysisAgent()
gemini_analysis_agent = GeminiAnalysisAgent()
trend_agent = TrendAgent()

def init_db():
    print("[System] Initializing database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            weight REAL,
            diameter REAL,
            height REAL,
            majorAxis REAL,
            minorAxis REAL,
            volume REAL,
            density REAL,
            waterContent REAL,
            shellColor TEXT,
            shakeSound TEXT,
            moldSpots INTEGER,
            cracksDamage INTEGER,
            score INTEGER,
            grade TEXT,
            issues TEXT,
            recommendations TEXT,
            predictions TEXT,
            geminiAnalysis TEXT,
            createdAt TEXT
        )
    ''')
    conn.commit()
    
    # Column Migration for existing databases
    cursor.execute("PRAGMA table_info(assessments)")
    columns = [column[1] for column in cursor.fetchall()]
    
    new_columns = {
        'height': 'REAL',
        'majorAxis': 'REAL',
        'minorAxis': 'REAL',
        'weight': 'REAL',
        'volume': 'REAL',
        'density': 'REAL',
        'imagePath': 'TEXT'
    }
    
    for col_name, col_type in new_columns.items():
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE assessments ADD COLUMN {col_name} {col_type}")
                print(f"Migrated: Added column {col_name}")
            except Exception as e:
                print(f"Migration error for {col_name}: {e}")
    
    conn.commit()
    conn.close()

# --- ROUTES ---

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            # Lazy initialize ingestion agent if needed
            global ingestion
            if ingestion is None:
                ingestion = IngestionAgent()

            frame = ingestion.get_frame()
            if frame is None:
                break
                
            # Make a copy for visualization
            display_frame = frame.copy()
            
            # Run ML Inference
            results = ml_agent.detect(frame)
            
            # Get dimension measurements (use first detection's bbox if available)
            dimension_data = None
            if results.get('predictions'):
                preds = results['predictions']
                if preds:
                    best_pred = max(preds, key=lambda x: x['confidence'])
                    x, y, w, h = int(best_pred['x']), int(best_pred['y']), int(best_pred['width']), int(best_pred['height'])
                    x1, y1 = int(x - w/2), int(y - h/2)
                    bbox = (x1, y1, w, h)
                    dimension_data = dimension_agent.measure(frame, bbox)
            
            # Draw ML Bounding Boxes
            for pred in results.get('predictions', []):
                x, y, w, h = int(pred['x']), int(pred['y']), int(pred['width']), int(pred['height'])
                x1, y1 = int(x - w/2), int(y - h/2)
                x2, y2 = int(x + w/2), int(y + h/2)
                
                color = (0, 255, 0)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                label = f"{pred['class']} {pred['confidence']:.2f}"
                cv2.putText(display_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Draw dimension measurements (ellipse and axes)
            if dimension_data:
                display_frame = dimension_agent.draw_measurement(display_frame, dimension_data)

            ret, buffer = cv2.imencode('.jpg', display_frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                   
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/save_detection', methods=['POST'])
def save_detection():
    # 1. Grab current frame
    global ingestion
    if ingestion is None:
        ingestion = IngestionAgent()

    frame = ingestion.get_frame()
    if frame is None: return jsonify({"error": "No camera"}), 500
    
    # 2. ML Agent
    results = ml_agent.detect(frame)
    
    # 3. Dimension Agent - Get accurate measurements
    dimension_data = None
    if results.get('predictions'):
        preds = results['predictions']
        if preds:
            best_pred = max(preds, key=lambda x: x['confidence'])
            x, y, w, h = int(best_pred['x']), int(best_pred['y']), int(best_pred['width']), int(best_pred['height'])
            x1, y1 = int(x - w/2), int(y - h/2)
            bbox = (x1, y1, w, h)
            dimension_data = dimension_agent.measure(frame, bbox)
    
    # 4. Analysis Agent (with dimension data and optional manual weight)
    data = request.json or {}
    manual_weight = data.get('manual_weight')
    assessment = analysis_agent.analyze(results, frame.shape, dimension_data, manual_weight)
    
    # 5. Gemini Analysis Agent (With Image Support)
    gemini_analysis = gemini_analysis_agent.analyze(assessment, frame)
    assessment['geminiAnalysis'] = gemini_analysis
    
    # Check for visual crack detection from Gemini (Improved Detection)
    # Check both tag and general mentions in a case-insensitive way
    analysis_upper = gemini_analysis.upper()
    if "[CRACK_DETECTED]" in analysis_upper or "CRACK_FOUND" in analysis_upper:
        print("[System] Gemini Vision identified a crack!")
        assessment['cracksDamage'] = True
        if "Visual crack detected by Gemini" not in assessment['issues']:
            assessment['issues'].append("Visual crack detected by Gemini")
        
        # Ensure Grade is C or D
        if assessment['grade'] in ["A", "B"]:
            assessment['grade'] = "C"
            print("[System] Forcing Grade C due to Gemini crack detection")
        
        # Ensure score reflects this
        assessment['score'] = min(69, assessment['score'])
    
    # 6. Trend Agent (save to DB with Image)
    saved_record = trend_agent.save(assessment, frame)
    
    return jsonify(saved_record)

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(trend_agent.get_history())
    
@app.route('/api/coconut-assessments/<id>', methods=['DELETE'])
def delete_record(id):
    trend_agent.delete(id)
    return jsonify({"status": "deleted"})

@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    return jsonify(sensor_agent.get_data())

@app.route('/api/copilot', methods=['POST'])
def copilot():
    # Explanation Agent - Enhanced for better database querying
    data = request.json
    query = data.get('query')
    
    # Enhanced context gathering
    history = trend_agent.get_history()
    
    # Calculate statistics
    total_assessments = len(history)
    if total_assessments > 0:
        grades = [h['grade'] for h in history]
        avg_score = sum([h['score'] for h in history]) / total_assessments
        grade_distribution = {g: grades.count(g) for g in set(grades)}
        recent_assessments = history[:5]
        
        # Build comprehensive context
        context = f"""
You are an AI assistant for a coconut quality assessment system. Here's the database information:

STATISTICS:
- Total Assessments: {total_assessments}
- Average Quality Score: {avg_score:.1f}/100
- Grade Distribution: {grade_distribution}

RECENT ASSESSMENTS (Last 5):
{json.dumps(recent_assessments, indent=2)}

Your role is to:
1. Answer questions about coconut quality trends and statistics
2. Provide insights on the assessment data
3. Help identify patterns in coconut quality
4. Explain grading criteria and recommendations

Be concise, helpful, and professional in your responses.
"""
    else:
        context = "No coconut assessments have been recorded yet. The database is empty."
    
    # Call Gemini if available
    if gemini_client:
        try:
            prompt = f"{context}\n\nUser Question: {query}\n\nProvide a clear and helpful response:"
            response = gemini_client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=prompt
            )
            reply = response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                reply = "My AI quota is currently full. Please wait about a minute before asking another question!"
            else:
                reply = f"I'm having trouble processing your request right now. Error: {error_str}"
    else:
        reply = "AI assistant is not available. Please configure the Gemini API key."
    
    return jsonify({"reply": reply})


if __name__ == '__main__':
    # Initialize DB (Agents will be lazy-loaded)
    init_db()
    # Ensure sensor agent is active
    get_sensor_agent()
    print("[System] Ready.")
    
    # Run Flask
    # FIX: Set use_reloader=False to prevent double-start that blocks the COM port
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
