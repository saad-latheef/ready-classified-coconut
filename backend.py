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
import concurrent.futures
from google import genai
from google.genai import types
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from inference_sdk import InferenceHTTPClient
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for Next.js frontend
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- CONFIGURATION ---
ROBOFLOW_API_URL = "http://localhost:9001"
ROBOFLOW_API_KEY = "vX3xJcrhB0TPB71Q5RSc"
ROBOFLOW_MODEL_ID = "my-first-project-nlg8h/6"

# Scratch and Hole Detection Model
ROBOFLOW_SCRATCH_API_KEY = "CScNG4RG0ERfvFWW0q5M"
ROBOFLOW_SCRATCH_MODEL_ID = "my-first-project-8caij/4"
GEMINI_API_KEY = "AIzaSyB5dGPsk6Ec1HITdiOJF50NVuVPAQoaVKY"  # Hardcoded API key

# Dimension Measurement Configuration
CM_PER_PIXEL = 0.06014
MIN_AREA = 1000  # Relaxed from 5000 to allow smaller objects
MAX_AREA = 500000  # Increased from 300000 to allow larger objects
BORDER_MARGIN = 10
HEIGHT_OFFSET = 0.0  # Set to 0 since user said 0 should be 0
HEIGHT_CALIBRATION_FACTOR = 1.67 # Factor to fix 9cm showing as 15cm (15/9)
WEIGHT_CALIBRATION_FACTOR = 0.00229345 # Maps raw 436024.11 units to 1000g

# Hardware Serial Configuration
SERIAL_PORT = 'COM14'
BAUD_RATE = 921600

# Initialize Clients
ml_client = InferenceHTTPClient(api_url=ROBOFLOW_API_URL, api_key=ROBOFLOW_API_KEY)
scratch_client = InferenceHTTPClient(api_url=ROBOFLOW_API_URL, api_key=ROBOFLOW_SCRATCH_API_KEY)

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
# Global Thread Pool for Multi-Agent Hub
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# --- DECOUPLED STREAM STATE ---
latest_raw_frame = None
latest_display_frame = None
latest_ml_results = {'predictions': []}
latest_scratch_results = {'predictions': []}
latest_dimension_data = None
stream_lock = threading.Lock()
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
        self.tare_offset = 1300.0
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
                            # Skip ESP32 debug messages (start with [)
                            if line.startswith('['):
                                print(f"[ESP32] {line}")
                                continue
                            
                            parts = line.split(',')
                            if len(parts) == 3:
                                try:
                                    h_val = float(parts[0])
                                    w_val = float(parts[1])
                                    wat_val = float(parts[2])
                                    
                                    with self.lock:
                                        self.data["height"] = h_val
                                        self.data["weight"] = w_val
                                        self.data["water"] = wat_val  # Water computed by ESP32
                                    # Stream weight to all connected WebSocket clients
                                    try:
                                        socketio.emit('weight_data', {'w': w_val, 't': time.time()}, namespace='/')
                                    except Exception:
                                        pass
                                except ValueError as ve:
                                    pass  # Silently skip malformed data
                            else:
                                if line and not line.startswith('['):
                                    print(f"[SensorAgent] Unexpected format: '{line}'")
                    except Exception as read_err:
                        print(f"[SensorAgent] Read Error: {read_err}")
                        break
            ser.close()
        except Exception as e:
            self.connected = False
            print(f"[SensorAgent] Serial Connection Failed: {e}. One-time check complete, thread terminating.")

    def get_data(self):
        try:
            with self.lock:
                processed_data = self.data.copy()
                
            # Weight calibration
            raw_diff = processed_data["weight"] - self.tare_offset
            stable_raw = (raw_diff // 100) * 100
            processed_data["weight"] = int(round(stable_raw * WEIGHT_CALIBRATION_FACTOR, 0))
            
            # Water: pass through from ESP32 (already in ml)
            # processed_data["water"] is already set from serial
            
            return processed_data
        except Exception as e:
            print(f"[SensorAgent] Critical error in get_data: {e}")
            return {"height": 0.0, "weight": 0.0, "water": 0.0}

    def tare(self):
        with self.lock:
            self.tare_offset = self.data["weight"]
            print(f"[SensorAgent] Tare complete. New offset: {self.tare_offset}")
        return True
    
    def reset_water_baseline(self):
        """Reset water level - no-op since ESP32 handles it"""
        print("[SensorAgent] Water detection managed by ESP32")

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
    def __init__(self, src=1):  # Changed to 0 for connected webcam
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

def background_capture_thread():
    """Continuously grabs frames from the camera as fast as possible"""
    global ingestion, latest_raw_frame
    print("[System] Starting Background Capture Thread...")
    while True:
        try:
            if ingestion is None:
                ingestion = IngestionAgent()
            
            frame = ingestion.get_frame()
            if frame is not None:
                with stream_lock:
                    latest_raw_frame = frame
            else:
                time.sleep(0.01)
        except Exception as e:
            print(f"[CaptureThread] Error: {e}")
            time.sleep(1)

def background_inference_thread():
    """Runs AI Hub in the background without blocking the video stream"""
    global latest_raw_frame, latest_ml_results, latest_scratch_results, latest_dimension_data
    print("[System] Starting Background Inference Thread...")
    frame_count = 0
    while True:
        try:
            # Grab a snapshot of the current frame
            frame = None
            with stream_lock:
                if latest_raw_frame is not None:
                    frame = latest_raw_frame.copy()
            
            if frame is None:
                time.sleep(0.1)
                continue
            
            frame_count += 1
            
            # Parallel Multi-Agent Detection
            futures_list = []
            futures_list.append(executor.submit(ml_agent.detect, frame))
            
            # Check scratches every 2nd "inference" pass (not frame)
            check_scratches = (frame_count % 2 == 0)
            if check_scratches:
                futures_list.append(executor.submit(ml_agent.detect_scratches, frame))
            
            # Use bounded wait
            concurrent.futures.wait(futures_list, timeout=1.5)
            
            new_ml = {'predictions': []}
            new_scratch = {'predictions': []}
            
            if futures_list[0].done():
                new_ml = futures_list[0].result()
            
            if check_scratches and len(futures_list) > 1 and futures_list[1].done():
                new_scratch = futures_list[1].result()
            
            # Dimension measurement (on Best Coconut)
            new_dim = None
            if new_ml.get('predictions'):
                best = max(new_ml['predictions'], key=lambda x: x['confidence'])
                x1, y1 = int(best['x'] - best['width']/2), int(best['y'] - best['height']/2)
                bbox = (x1, y1, int(best['width']), int(best['height']))
                new_dim = dimension_agent.measure(frame, bbox)
            
            # Update Global Results for the stream to pick up
            with stream_lock:
                latest_ml_results = new_ml
                if check_scratches:
                    latest_scratch_results = new_scratch
                latest_dimension_data = new_dim
                
        except Exception as e:
            print(f"[InferenceThread] Error: {e}")
            time.sleep(0.1)

class MLAgent:
    def detect(self, frame):
        try:
            # Main coconut detection
            results = ml_client.infer(frame, model_id=ROBOFLOW_MODEL_ID)
            return results
        except Exception as e:
            print(f"ML Error (Coconut): {e}")
            return {'predictions': []}

    def detect_scratches(self, frame):
        try:
            # Scratch and hole detection
            # print("[MLAgent] Calling scratch detection...")
            results = scratch_client.infer(frame, model_id=ROBOFLOW_SCRATCH_MODEL_ID)
            if results.get('predictions'):
                print(f"[MLAgent] Scratch Detected: {len(results['predictions'])} results")
            return results
        except Exception as e:
            print(f"ML Error (Scratch): {e}")
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
            major_cm = d1 * CM_PER_PIXEL - 10.0  # -5 original + -5 extra
            minor_cm = d2 * CM_PER_PIXEL - 5.0   # -5 extra
        else:
            major_cm = d2 * CM_PER_PIXEL - 10.0
            minor_cm = d1 * CM_PER_PIXEL - 5.0
        return round(max(major_cm, 0), 2), round(max(minor_cm, 0), 2)
    
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
    def __init__(self):
        # Cache last known good values for fallback
        self._last = {
            'shellColor': 'Unknown',
            'majorAxis': 0,
            'minorAxis': 0,
        }

    def analyze(self, predictions, frame_shape, dimension_data=None, manual_weight=None, scratch_preds=None, manual_water=None):
        # Default assessment
        assessment = {
            "weight": 0, "diameter": 0, "height": 0, "waterContent": 0,
            "majorAxis": 0, "minorAxis": 0, "volume": 0, "density": 0,
            "shellColor": "unknown", "shakeSound": "unknown",
            "moldSpots": False, "cracksDamage": False,
            "score": 0, "grade": "Ungraded",
            "scratchPercentage": 0.0, "scratchCount": 0,
            "issues": [], "recommendations": [],
            "predictions": predictions,
            "scratch_predictions": []
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
        
        # Use manual weight if provided, otherwise fall back to sensor
        if manual_weight is not None:
            try:
                assessment['weight'] = float(manual_weight)
                print(f"[AnalysisAgent] Using MANUAL weight: {assessment['weight']}g")
            except:
                assessment['weight'] = real_sensors['weight']
        else:
            assessment['weight'] = real_sensors['weight']
        
        # Water content from manual input or sensor fallback
        if manual_water is not None:
            try:
                assessment['waterContent'] = float(manual_water)
                print(f"[AnalysisAgent] Using MANUAL water level: {assessment['waterContent']}ml")
            except:
                assessment['waterContent'] = real_sensors['water']
        else:
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

        # Cache axes if valid, otherwise use last known
        if assessment['majorAxis'] > 0 and assessment['minorAxis'] > 0:
            self._last['majorAxis'] = assessment['majorAxis']
            self._last['minorAxis'] = assessment['minorAxis']
        else:
            assessment['majorAxis'] = self._last['majorAxis']
            assessment['minorAxis'] = self._last['minorAxis']
            assessment['diameter'] = self._last['majorAxis']

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

        # 2.5 Scratch & Hole Detection (log only, does NOT affect grade)
        if scratch_preds:
            for sp in scratch_preds:
                s_cls = sp.get('class', '').lower()
                if 'hole' in s_cls:
                    assessment['cracksDamage'] = True  # Only holes set this
                issue_msg = f"Potential {s_cls} detected"
                if issue_msg not in assessment['issues']:
                    assessment['issues'].append(issue_msg)

        # 2.6 Scratch Percentage Calculation (Area-based)
        scratch_area = 0
        if scratch_preds:
            for sp in scratch_preds:
                scratch_area += sp.get('width', 0) * sp.get('height', 0)
        
        coconut_area = 0
        if dimension_data and 'ellipse' in dimension_data:
            # pi * r1 * r2
            _, (d1, d2), _ = dimension_data['ellipse']
            coconut_area = math.pi * (d1 / 2.0) * (d2 / 2.0)
        elif best_pred:
            # Fallback to bbox area
            coconut_area = best_pred.get('width', 0) * best_pred.get('height', 0)
            
        if coconut_area > 0:
            assessment['scratchPercentage'] = round((scratch_area / coconut_area) * 100, 2)
            if assessment['scratchPercentage'] > 5:
                assessment['issues'].append(f"High scratch density: {assessment['scratchPercentage']}%")
        else:
            assessment['scratchPercentage'] = 0.0

        # 3. NEW GRADING SYSTEM - Rule-based A/B/C Classification
        # ========================================================
        
        # Move shellColor detection FIRST (needed for grading)
        cls_lower = cls.lower()
        if 'green' in cls_lower:
            assessment['shellColor'] = "Green"
        elif 'brown' in cls_lower:
            assessment['shellColor'] = "Brown"
        else:
            assessment['shellColor'] = "Unknown"
        
        # Cache color
        if assessment['shellColor'] != 'Unknown':
            self._last['shellColor'] = assessment['shellColor']
        else:
            assessment['shellColor'] = self._last['shellColor']
        
        # RULE 1: HOLE = INSTANT C GRADE (overrides everything)
        has_hole = False
        if scratch_preds:
            for sp in scratch_preds:
                if 'hole' in sp.get('class', '').lower():
                    has_hole = True
                    if "Hole detected" not in assessment['issues']:
                        assessment['issues'].append("Hole detected")
        
        if has_hole:
            assessment['grade'] = "C"
            assessment['score'] = 30
            assessment['recommendations'].append("Hole detected - C Grade (processing only)")
            print("[AnalysisAgent] INSTANT C GRADE: Hole detected")
            return assessment
        
        # RULE 2: Classify each factor into A/B/C
        height_val = assessment['height']
        weight_val = assessment['weight']
        water_val = assessment['waterContent']
        color = assessment['shellColor']
        
        grades = []  # Collect grade votes from each factor
        
        # --- Height ---
        if height_val > 12:
            grades.append('A')
        elif height_val >= 10:
            grades.append('B')
        else:
            grades.append('C')
            if "Small size (height < 10cm)" not in assessment['issues']:
                assessment['issues'].append("Small size (height < 10cm)")
        
        # --- Weight ---
        if weight_val >= 1100:
            grades.append('A')
        elif weight_val >= 700:
            grades.append('B')
        elif weight_val >= 300:
            grades.append('C')
        else:
            grades.append('C')
            if "Very lightweight (< 300g)" not in assessment['issues']:
                assessment['issues'].append("Very lightweight (< 300g)")
        
        # --- Water Content (ml) ---
        if water_val >= 200:
            grades.append('A')  # High
        elif water_val >= 100:
            grades.append('B')  # Medium
        else:
            grades.append('C')  # Low
        
        # --- Appearance (Color only, scratches don't affect grade) ---
        if color == "Green":
            grades.append('A')  # Clean smooth green
        elif color == "Brown":
            grades.append('B')  # Brown
        else:
            grades.append('B')  # Unknown defaults to B
        
        # FINAL GRADE: Majority vote (worst grade wins ties)
        grade_order = {'A': 0, 'B': 1, 'C': 2}
        a_count = grades.count('A')
        b_count = grades.count('B')
        c_count = grades.count('C')
        
        if c_count >= max(a_count, b_count):
            grade = "C"
        elif a_count >= b_count:
            grade = "A"
        else:
            grade = "B"
        
        # Calculate score from grade
        if grade == "A":
            assessment['score'] = 90 + min(10, a_count * 2)
        elif grade == "B":
            assessment['score'] = 70 + min(19, b_count * 3)
        else:
            assessment['score'] = max(10, 50 - c_count * 5)
        
        assessment['grade'] = grade
        
        # 4. Recommendations
        if grade == "A":
            assessment['recommendations'].append("Premium Quality - Package for retail")
        elif grade == "B":
            assessment['recommendations'].append("Standard Quality - Suitable for market")
        else:
            assessment['recommendations'].append("Low Quality - Processing or discard")
        
        return assessment

class GeminiAnalysisAgent:
    """Uses Gemini AI to provide detailed coconut variety and quality analysis with Visual support"""
    def analyze(self, assessment, frame=None):
        if not gemini_client:
            print("[GeminiVision] Client not available, falling back to local analysis")
            return self._generate_local_analysis(assessment)
        
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

Provide synopsis, physical analysis, internal content estimate, usage recommendation, and maintenance advice."""
            
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
            print(f"[GeminiVision] Error during analysis: {e}. Falling back to local analysis.")
            return self._generate_local_analysis(assessment)

    def _generate_local_analysis(self, assessment):
        """Generates a detailed structured report locally without AI when Gemini is offline"""
        grade = assessment.get('grade', 'Ungraded')
        score = assessment.get('score', 0)
        weight = assessment.get('weight', 0)
        volume = assessment.get('volume', 0)
        density = assessment.get('density', 0)
        issues = assessment.get('issues', [])
        color = assessment.get('shellColor', 'Unknown')
        water = assessment.get('waterContent', 0)
        
        # 1. Quality Synopsis
        synopsis = f"This coconut has been graded as **Grade {grade}** with a quality score of **{score}/100**. "
        if issues:
            synopsis += f"Key observations include: {', '.join(issues)}. "
        else:
            synopsis += "The external shell appears healthy and structurally sound. "

        # 2. Physical Analysis
        maturity = "mature" if color == "Brown" else "young"
        phys_desc = "standard"
        if density > 1.0: phys_desc = "high-density"
        elif density < 0.6: phys_desc = "low-density/lightweight"
        
        physical = f"At {weight}g and a volume of {volume:.0f}cm³, the specimen exhibits {phys_desc} characteristics. "
        physical += f"The calculated density of {density:.2f}g/cm³ is typical for a {maturity} coconut of this size."

        # 3. Internal Content
        content_est = "generous" if water > 200 else "adequate" if water > 100 else "limited"
        internal = f"Hydration analysis estimates a **{content_est}** liquid volume of approximately **{water}ml**. "
        if color == "Green":
            internal += "The internal meat (endosperm) is likely tender and high in sweetness."
        else:
            internal += "The meat is expected to be firm and thick, suitable for oil or desiccated processing."

        # 4. Usage Recommendation
        if grade == 'A':
            usage = "Ideal for premium retail, bottled water, or high-end culinary fresh use."
        elif grade == 'B':
            usage = "Recommended for general market sale or standard household consumption."
        else:
            usage = "Best suited for industrial processing, oil extraction, or animal feed components."

        # 5. Maintenance Advice
        advice = "Store in a cool, ventilated area away from direct sunlight. "
        if color == "Green": advice += "Consume within 3-5 days for peak freshness."
        else: advice += "Shelf life is approximately 10-14 days if kept dry."

        report = f"""**LOCAL DETAILED ANALYSIS (OFFLINE)**

1. **Quality Synopsis**: {synopsis}
2. **Physical Analysis**: {physical}
3. **Internal Content**: {internal}
4. **Usage Recommendation**: {usage}
5. **Maintenance Advice**: {advice}

*Note: This report was generated locally using deterministic sensor data.*"""
        return report

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
                moldSpots, cracksDamage, score, grade, issues, recommendations, predictions, geminiAnalysis, scratchPercentage, createdAt, imagePath
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record_id, assessment['weight'], assessment['diameter'], assessment['height'],
            assessment.get('majorAxis', 0), assessment.get('minorAxis', 0),
            assessment['volume'], assessment['density'], assessment['waterContent'],
            assessment['shellColor'], assessment['shakeSound'],
            1 if assessment['moldSpots'] else 0, 1 if assessment['cracksDamage'] else 0,
            assessment['score'], assessment['grade'],
            json.dumps(assessment['issues']), json.dumps(assessment['recommendations']),
            json.dumps(assessment['predictions']), assessment['geminiAnalysis'], 
            assessment.get('scratchPercentage', 0.0), created_at, image_path
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
        'imagePath': 'TEXT',
        'scratchPercentage': 'REAL'
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
        global latest_raw_frame, latest_ml_results, latest_scratch_results, latest_dimension_data
        
        while True:
            try:
                # 1. Grab Current state (Snapshot)
                frame = None
                ml_res = None
                scratch_res = None
                dim_data = None
                
                with stream_lock:
                    if latest_raw_frame is not None:
                        frame = latest_raw_frame.copy()
                    ml_res = latest_ml_results.copy()
                    scratch_res = latest_scratch_results.copy()
                    dim_data = latest_dimension_data
                
                if frame is None:
                    time.sleep(0.03) # ~30fps wait
                    continue
                
                # 2. Draw detections on the frame replica
                # Coconut (Green) - Show only the BEST match to avoid overlapping issues
                preds = ml_res.get('predictions', [])
                if preds:
                    best_pred = max(preds, key=lambda x: x['confidence'])
                    x, y, w, h = int(best_pred['x']), int(best_pred['y']), int(best_pred['width']), int(best_pred['height'])
                    cv2.rectangle(frame, (int(x-w/2), int(y-h/2)), (int(x+w/2), int(y+h/2)), (0, 255, 0), 2)
                    cv2.putText(frame, f"{best_pred['class']}", (int(x-w/2), int(y-h/2)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Scratch & Hole (Blue)
                for pred in scratch_res.get('predictions', []):
                    x, y, w, h = int(pred['x']), int(pred['y']), int(pred['width']), int(pred['height'])
                    cls_name = pred.get('class', 'Defect').upper()
                    cv2.rectangle(frame, (int(x-w/2), int(y-h/2)), (int(x+w/2), int(y+h/2)), (255, 0, 0), 2)
                    cv2.putText(frame, cls_name, (int(x-w/2), int(y-h/2)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

                if dim_data:
                    frame = dimension_agent.draw_measurement(frame, dim_data)

                # 3. Stream at optimized resolution
                display_frame = cv2.resize(frame, (640, 480))
                ret, buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                
                time.sleep(0.01) # Small throttle to CPU
                
            except Exception as e:
                print(f"[VideoFeed] View error: {e}")
                time.sleep(0.1)
                   
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
    manual_water = data.get('manual_water')
    
    # 4.5 Run scratch detection for the saved report and percentage calculation
    scratch_results = ml_agent.detect_scratches(frame)
    scratch_preds = scratch_results.get('predictions', [])
    
    # 4.6 Single Analysis Pass (Includes Scratches and Percentage)
    assessment = analysis_agent.analyze(results, frame.shape, dimension_data, manual_weight, scratch_preds=scratch_preds, manual_water=manual_water)
    assessment['scratch_predictions'] = scratch_preds
    assessment['scratchCount'] = len(scratch_preds)
    
    # 5. Gemini Analysis Agent (With Image Support)
    gemini_analysis = gemini_analysis_agent.analyze(assessment, frame)
    assessment['geminiAnalysis'] = gemini_analysis
    
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

@app.route('/api/tare', methods=['POST'])
def tare_sensors():
    agent = get_sensor_agent()
    if agent:
        agent.tare()
        return jsonify({"status": "success", "message": "Sensors tared to zero"})
    return jsonify({"status": "error", "message": "Sensor agent not available"}), 500

@app.route('/api/water_reset', methods=['POST'])
def water_reset():
    agent = get_sensor_agent()
    if agent:
        agent.reset_water_baseline()
        return jsonify({"status": "success", "message": "Water baseline reset"})
    return jsonify({"status": "error", "message": "Sensor agent not available"}), 500

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
    
    # Start DECOUPLED AGENTS
    threading.Thread(target=background_capture_thread, daemon=True).start()
    threading.Thread(target=background_inference_thread, daemon=True).start()
    
    print("[System] Zero-Lag Decoupled Stream Architecture Ready.")
    
    # Run Flask with SocketIO for real-time WebSocket streaming
    # FIX: Set use_reloader=False to prevent double-start that blocks the COM port
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
