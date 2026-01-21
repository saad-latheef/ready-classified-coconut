"use client"

import { useRef, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Camera, Loader2, AlertCircle, Weight, Ruler, Waves, TrendingUp } from "lucide-react"
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts"

interface CaptureResult {
  grade: string
  score: number
  geminiAnalysis?: string
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
  const [weightHistory, setWeightHistory] = useState<{ time: string, weight: number }[]>([])
  const [manualWeight, setManualWeight] = useState<string>("")
  
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
          
          // Update graph history
          setWeightHistory(prev => {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], { second: '2-digit' }) + '.' + Math.floor(now.getMilliseconds() / 10);
            
            const newHistory = [...prev, { 
              time: timeStr, 
              weight: Number(data.weight.toFixed(1)) 
            }]
            // Keep last 100 readings for a high-frequency trend
            return newHistory.slice(-100)
          })
        }
      } catch (err) {
        console.error("Sensor polling failed:", err)
      }
    }

    const interval = setInterval(pollSensors, 50) // Max frequency: 50ms (20 times per second)
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
          manual_weight: manualWeight ? parseFloat(manualWeight) : null 
        })
      })

      if (response.ok) {
        const result = await response.json()
        setLastResult({
          grade: result.grade,
          score: result.score,
          geminiAnalysis: result.geminiAnalysis
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
          <div className="bg-white p-4 rounded-xl border border-green-100 shadow-sm flex items-center justify-between group hover:border-green-300 transition-all">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-50 rounded-lg text-green-600">
                <Weight className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Live Weight</p>
                <h3 className="text-xl font-bold text-gray-800">{sensors.weight.toFixed(1)} <span className="text-sm font-normal text-gray-400">g</span></h3>
              </div>
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
                <h3 className="text-xl font-bold text-gray-800">{sensors.water.toFixed(2)} <span className="text-sm font-normal text-gray-400">L</span></h3>
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

        {/* Live Weight Graph */}
        <div className="bg-white p-4 rounded-xl border border-green-100 shadow-sm mb-4">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-green-600" />
            <span className="text-sm font-bold text-gray-700 uppercase tracking-wider">Weight Trend (Live)</span>
          </div>
          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={weightHistory}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                <XAxis dataKey="time" hide />
                <YAxis domain={[0, 'auto']} tick={{fontSize: 10}} stroke="#9ca3af" unit="g" />
                <Tooltip 
                  contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelStyle={{ fontWeight: 'bold', color: '#059669' }}
                  formatter={(value: number) => [`${value} g`, 'Weight']}
                />
                <Line 
                  type="monotone" 
                  dataKey="weight" 
                  stroke="#10b981" 
                  strokeWidth={3} 
                  dot={false}
                  isAnimationActive={false} // Disable animation for smoother real-time look
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

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
               {sensors.weight > 0 ? "STABLE" : "WAITING FOR SENSOR"}
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
              <div className="bg-green-100 text-green-700 px-3 py-1 rounded-full font-bold text-sm">
                {lastResult.score}/100
              </div>
            </div>
            {lastResult.geminiAnalysis && (
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
