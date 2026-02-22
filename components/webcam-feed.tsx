"use client"

import { useRef, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Camera, Loader2, AlertCircle, Weight, Ruler, Waves, Droplets } from "lucide-react"
import { SerialPlotter } from "@/components/serial-plotter"

interface CaptureResult {
  grade: string
  score: number
  geminiAnalysis?: string
  scratchPercentage?: number
  scratchCount?: number
}

interface SensorData {
  height: number
  weight: number
  water: number
}

export function WebcamFeed() {
  const [isProcessing, setIsProcessing] = useState(false)
  const [lastResult, setLastResult] = useState<CaptureResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sensors, setSensors] = useState<SensorData>({ height: 0, weight: 0, water: 0 })
  const [liveWeight, setLiveWeight] = useState<number>(0)
  const [manualWeight, setManualWeight] = useState<string>("")
  const [manualWater, setManualWater] = useState<string>("")
  
  // Flask Streaming URL
  const STREAM_URL = "http://localhost:5000/video_feed"
  const SENSOR_URL = "http://localhost:5000/api/sensors"

  // Poll sensors every second
  useEffect(() => {
    const pollSensors = async () => {
      try {
        const response = await fetch(SENSOR_URL)
        if (response.ok) {
          const data = await response.json()
          setSensors(data)
        }
      } catch (err) {
        console.error("Sensor polling failed:", err)
      }
    }

    const interval = setInterval(pollSensors, 200) // Reduced to 5Hz (200ms) for stability
    return () => clearInterval(interval)
  }, [])

  const captureAndAnalyze = async () => {
    setIsProcessing(true)
    setError(null)
    setLastResult(null)
    try {
      // Trigger the 'Save Detection' agent in backend
      const response = await fetch("http://localhost:5000/api/save_detection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          manual_weight: manualWeight ? parseFloat(manualWeight) : null,
          manual_water: manualWater ? parseFloat(manualWater) : null
        })
      })

      if (response.ok) {
        const result = await response.json()
        setLastResult({
          grade: result.grade,
          score: result.score,
          geminiAnalysis: result.geminiAnalysis,
          scratchPercentage: result.scratchPercentage,
          scratchCount: result.scratchCount
        })
      } else {
        setError("Failed to save assessment")
      }
    } catch (error) {
      console.error("Capture failed:", error)
      setError("Failed to connect to Multi-Agent Backend")
    } finally {
      setIsProcessing(false)
    }
  }



  return (
    <div className="flex flex-col h-full gap-4">
        {/* Live Metrics Dashboard */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-2">
          <div className="bg-white p-4 rounded-xl border border-green-100 shadow-sm flex items-center gap-3 group hover:border-green-300 transition-all">
            <div className="p-2 bg-green-50 rounded-lg text-green-600">
              <Weight className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Live Weight</p>
              <h3 className="text-xl font-bold text-gray-800">{liveWeight.toFixed(1)} <span className="text-sm font-normal text-gray-400">g</span></h3>
            </div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm flex items-center justify-between group hover:border-blue-300 transition-all">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                <Ruler className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Live Height</p>
                <h3 className="text-xl font-bold text-gray-800">{sensors.height.toFixed(1)} <span className="text-sm font-normal text-gray-400">cm</span></h3>
              </div>
            </div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-cyan-100 shadow-sm flex items-center justify-between group hover:border-cyan-300 transition-all">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-cyan-50 rounded-lg text-cyan-600">
                <Waves className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Water Level</p>
                <h3 className="text-xl font-bold text-gray-800">{Math.round(sensors.water)} <span className="text-sm font-normal text-gray-400">ml</span></h3>
              </div>
            </div>
          </div>
        </div>

        {/* Manual Weight Override Input */}
        <div className="bg-white p-4 rounded-xl border border-orange-100 shadow-sm flex items-center gap-4 mb-2">
          <div className="p-2 bg-orange-50 rounded-lg text-orange-600">
            <Weight className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Manual Weight Override (Optional)</p>
            <input 
              type="number" 
              placeholder="Enter weight in grams..."
              value={manualWeight}
              onChange={(e) => setManualWeight(e.target.value)}
              className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-bold text-gray-800 focus:outline-none focus:ring-2 focus:ring-orange-500 transition-all"
            />
          </div>
          {manualWeight && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setManualWeight("")}
              className="text-gray-400 hover:text-red-500"
            >
              Clear
            </Button>
          )}
        </div>

        {/* Manual Water Level Input */}
        <div className="bg-white p-4 rounded-xl border border-cyan-100 shadow-sm flex items-center gap-4 mb-2">
          <div className="p-2 bg-cyan-50 rounded-lg text-cyan-600">
            <Droplets className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Manual Water Level (ml)</p>
            <input 
              type="number" 
              placeholder="Enter water level in ml..."
              value={manualWater}
              onChange={(e) => setManualWater(e.target.value)}
              className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-bold text-gray-800 focus:outline-none focus:ring-2 focus:ring-cyan-500 transition-all"
            />
          </div>
          {manualWater && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setManualWater("")}
              className="text-gray-400 hover:text-red-500"
            >
              Clear
            </Button>
          )}
        </div>

        {/* Live Weight Serial Plotter */}
        <SerialPlotter onWeightUpdate={setLiveWeight} />

        <div className="relative w-full h-[450px] rounded-2xl overflow-hidden bg-black border-4 border-white shadow-xl">
           {/* MJPEG Stream from Flask */}
           <img 
             src={STREAM_URL} 
             alt="Live Inference Feed" 
             className="w-full h-full object-contain"
             onError={(e) => {
               e.currentTarget.style.display = 'none';
               setError("Backend Offline. Start 'backend.py'");
             }}
           />
           
           {/* Overlay UI */}
           <div className="absolute top-6 left-6 flex items-center gap-2">
             <div className="bg-green-600 text-white px-3 py-1 rounded-full font-bold text-[10px] tracking-widest uppercase shadow-lg animate-pulse">
               Live Agent Hub
             </div>
             <div className="bg-black/60 backdrop-blur-md text-white/90 px-3 py-1 rounded-full font-mono text-[10px] border border-white/20">
               {liveWeight > 0 ? "STABLE" : "WAITING FOR SENSOR"}
             </div>
           </div>
        </div>

        {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {error}
        </div>
        )}

        {lastResult && (
        <div className="p-5 rounded-2xl bg-white border-2 border-green-500 shadow-lg animate-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xl font-black text-gray-800">
                LATEST GRADE: <span className="text-green-600">{lastResult.grade}</span>
              </div>
              <div className="flex flex-col items-end gap-1">
                <div className="bg-green-100 text-green-700 px-3 py-1 rounded-full font-bold text-sm">
                  {lastResult.score}/100
                </div>
                {lastResult.scratchCount !== undefined && lastResult.scratchCount > 0 && (
                  <div className="text-[10px] font-bold text-orange-600 uppercase tracking-tighter bg-orange-50 px-2 py-0.5 rounded-md border border-orange-100">
                    {lastResult.scratchCount} Scratch{lastResult.scratchCount > 1 ? 'es' : ''}
                  </div>
                )}
                {lastResult.scratchPercentage !== undefined && lastResult.scratchPercentage > 0 && (
                  <div className="text-[10px] font-bold text-red-500 uppercase tracking-tighter bg-red-50 px-2 py-0.5 rounded-md border border-red-100">
                    {lastResult.scratchPercentage}% Scratched
                  </div>
                )}
              </div>
            </div>
            {lastResult.geminiAnalysis && !lastResult.geminiAnalysis.startsWith("Gemini Analysis Error") && (
              <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 italic text-sm text-gray-600 leading-relaxed">
                "{lastResult.geminiAnalysis.split('.')[0]}..."
              </div>
            )}
        </div>
        )}

        <Button 
            onClick={captureAndAnalyze} 
            disabled={isProcessing} 
            className="w-full h-16 bg-green-600 hover:bg-green-700 text-white font-black text-lg shadow-xl shadow-green-200 transition-all active:scale-95" 
            size="lg"
        >
        {isProcessing ? (
            <>
            <Loader2 className="w-6 h-6 mr-3 animate-spin" />
            ANALYZING...
            </>
        ) : (
            <>
            <Camera className="w-6 h-6 mr-3" />
            TRIGGER ASSESSMENT
            </>
        )}
        </Button>
    </div>
  )
}
