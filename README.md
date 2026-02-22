# 🥥 Coconut Quality Checker
### "Precision Grading for the Perfect Coconut — Where AI meets Hardware."

An AI-powered, multi-agent industrial automation system for real-time coconut grading, dimension measurement, and quality assessment.

## 🌟 Overview

The **Coconut Quality Checker** is a professional-grade industrial tool designed to standardize and accelerate the coconut grading process. By integrating high-speed hardware sensors with advanced computer vision and Generative AI, the system removes human subjectivity from quality control. It features a unique "throw-and-detect" workflow: simply place or throw a coconut onto the scale, and the system instantly captures dimensions, weight, and internal water level while performing a 360° visual health check for defects like mold, cracks, or holes.

## 🛠️ Tech Stack (The Quick Version)

This project leverages a sophisticated mix of hardware and software to automate coconut quality assessment. On the hardware side, an **ESP32 XIAO** microcontroller interfaces with **HX711** load cells and **HC-SR04** ultrasonic sensors to capture precise weight and dimensional data at native speeds. The backend is powered by a **Flask**-based multi-agent system that orchestrates real-time sensor processing, **Roboflow**-based object detection for physical defects, and **Google Gemini 2.5 Flash Lite** for deep qualitative vision analysis. All data is persisted in a local **SQLite** database and presented through a premium **Next.js 14** dashboard featuring real-time WebSocket weight plotting and an interactive AI copilot.

## 🚀 Core Features

-   **High-Speed Sensor Fusion**: Real-time weight, height, and water level capture via ESP32.
-   **Dynamic Water Level Detection**: State-based spike analysis on the ESP32 to compute milliliters (ml) from impact settles.
-   **Automated Dimensioning**: Computer vision-based ellipsoid fitting to measure major and minor axes in cm.
-   **Rule-Based Grading Engine**: A robust voting system (A, B, C) that aggregates physical metrics and visual defects.
-   **Multi-Agent Vision Pipeline**: 
    -   **Roboflow Agent**: Rapid identification of holes, cracks, mold, and transparency.
    -   **Gemini Agent**: Nuanced visual analysis for final quality reporting.
-   **Real-time Streaming**: Zero-lag MJPEG video feed and WebSocket-based weight trend plotter.
-   **AI Copilot**: Natural language interface to query historical data and get grading advice.

## 🧱 Detailed Tech Stack

### Frontend
-   **Framework**: Next.js 14 (App Router)
-   **Styling**: Tailwind CSS + Shadcn UI
-   **Communication**: WebSocket (for 50Hz Weight Plotting) + HTTP Pooling
-   **Visualization**: Custom Canvas-based Serial Plotter for raw sensor data.

### Backend (Multi-Agent Orchestration)
-   **Framework**: Flask (Python 3.10+)
-   **Vision**: OpenCV (ellipsoid fitting & contour analysis)
-   **Inference**: Roboflow Inference SDK
-   **AI**: Google Gemini 2.5 Flash Lite
-   **Database**: SQLite3

### Hardware / IoT
-   **Controller**: ESP32 XIAO (C6/Sense)
-   **Sensors**: Load Cell (HX711), Ultrasonic (HC-SR04)
-   **Communication**: USB Serial (921600 Baud)

## 📁 Project Structure

```text
├── app/                  # Next.js Application Logic
├── components/           # UI Components (Webcam, History, Charts)
├── backend.py            # Flask Multi-Agent Server
├── list_models.py        # Roboflow Debug Utility
├── coconuts.db           # SQLite Database
├── captures/             # Assessment Image Storage
└── TECH_STACK.md         # Detailed Tech Architecture
```

## ⚙️ Installation & Setup

### 1. Prerequisites
-   Python 3.10+
-   Node.js 18+
-   Docker (for Roboflow Inference)
-   Google Gemini API Key

### 2. Backend Setup
```bash
# Install dependencies
pip install flask flask-cors opencv-python numpy google-genai inference-sdk pyserial

# Start Roboflow Inference Server (Docker)
docker run -d --name roboflow -p 9001:9001 roboflow/inference-server:latest

# Run the Flask server
python backend.py
```

### 3. Frontend Setup
```bash
# Install dependencies
npm install

# Run the development server
npm run dev
```

### 4. Configuration
Ensure your `backend.py` is configured with:
-   `GEMINI_API_KEY`: Your Google GenAI key.
-   `ROBOFLOW_API_KEY`: Your Roboflow project key.
-   `SERIAL_PORT`: The COM port for your sensor hub (e.g., `COM10`).

## 🧱 Architecture (Multi-Agent System)

The system operates using 5 specialized agents coordinated via the Flask backend:
1.  **Ingestion Agent**: Manages the high-speed camera feed.
2.  **ML Agent**: Performs object detection via Roboflow.
3.  **Analysis Agent**: Physics-based grading and metric calculation.
4.  **Trend Agent**: Handles database I/O and historical trends.
5.  **Gemini Agent**: Provides "Human-like" qualitative analysis.

## 📄 License
Private Repository - proprietary software.
