# Coconut Quality Checker - Tech Stack Document

This document outlines the full technical architecture and technology stack used in the Coconut Quality Checker application.

## 1. Frontend Architecture
The frontend is built using a modern React-based stack designed for low-latency hardware monitoring.

*   **Framework**: Next.js 14 (App Router)
*   **Language**: TypeScript
*   **Styling**: Tailwind CSS + Shadcn UI
*   **Visualization**: **Custom Canvas-based Serial Plotter** (real-time 50Hz weight streaming).
*   **Communication**: WebSockets for raw sensor streams + HTTP polling for assessment states.

## 2. Backend Architecture (Multi-Agent System)
The backend is a high-performance Python Flask application implementing a Multi-Agent Orchestration pattern for sensor fusion and vision AI.

*   **Framework**: Flask (Python 3.10+)
*   **Agents**:
    *   **Ingestion Agent**: Managed high-speed USB camera feed with OpenCV `CAP_DSHOW` optimization for MJPEG streaming.
    *   **ML Agent**: Connects to a local **Roboflow Inference Server** (Docker) for real-time defect identification.
    *   **Analysis Agent**: Calculates volume (ellipsoid fitting), density, and performs factor-based voting for grading.
    *   **Sensor Agent**: Threaded serial interface (`pyserial`) for continuous bidirectional communication with ESP32.
    *   **Gemini Vision Agent**: Leverages **Google Gemini 2.5 Flash Lite** for nuanced qualitative crack and mold detection.
    *   **Trend Agent**: Manages SQLite data persistence and historical assessment retrieval.

## 3. AI & Model Stack
*   **Reasoning/Vision**: Google Gemini 2.5 Flash Lite (`google-genai` SDK).
*   **Object Detection**: Roboflow YOLO-based models for defect localization (holes, scratches, mold).
*   **Inference Hub**: Roboflow Inference Docker Container (`localhost:9001`).

## 4. Hardware & IoT Integration
The system uses a high-speed sensor hub for millisecond-accurate physical measurements.

*   **Controller**: **ESP32 XIAO** (High-speed RISC-V/ESP32 core).
*   **Communication**: USB Serial (921600 Baud) for jitter-free data streaming.
*   **Sensors**: 
    *   Load Cell + HX711 (Weight with custom software calibration).
    *   HC-SR04 Ultrasonic (Height measurement with platform baseline).
*   **Firmware Logic**: Implements a dedicated **Water Detection State Machine** (IDLE → COLLECTING → DONE) to compute internal liquid volume via high-speed weight spike analysis.

## 5. Persistence & Storage
*   **Primary Database**: SQLite3 (`coconuts.db`).
*   **Image Storage**: Local filesystem (`captures/`) for High-Def assessment logs.
*   **Schema**: Relational table with JSON-serialized metadata for automated recommendations.

## 6. Performance Optimizations
*   **Native Calibration**: Weight and Height calibration handled at the firmware level for maximum throughput.
*   **Non-Blocking Streams**: Decoupled capture and inference threads to ensure the UI remains responsive even during heavy AI analysis.
*   **Network Efficiency**: Binary WebSocket frames for raw weight data to minimize serialization overhead.

