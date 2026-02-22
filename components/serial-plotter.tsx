"use client"

import { useRef, useEffect, useState, useCallback } from "react"
import { io, Socket } from "socket.io-client"
import { Activity, Pause, Play } from "lucide-react"

interface SerialPlotterProps {
  /** Called whenever a new calibrated weight value arrives */
  onWeightUpdate?: (weight: number) => void
}

const BUFFER_SIZE = 500        // Number of data points visible in the window
const GRID_LINES_Y = 6         // Horizontal grid lines
const GRID_LINES_X = 10        // Vertical grid lines
const BG_COLOR = "#0a0f1a"     // Dark navy background
const GRID_COLOR = "#1a2744"   // Subtle grid
const LINE_COLOR = "#10b981"   // Emerald green (matches existing theme)
const LINE_GLOW = "#34d399"    // Lighter green for glow effect
const TEXT_COLOR = "#94a3b8"   // Slate gray for labels
const ACCENT_COLOR = "#059669" // Accent for current value

export function SerialPlotter({ onWeightUpdate }: SerialPlotterProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const dataRef = useRef<number[]>(new Array(BUFFER_SIZE).fill(0))
  const currentValueRef = useRef<number>(0)
  const socketRef = useRef<Socket | null>(null)
  const animFrameRef = useRef<number>(0)
  const mouseRef = useRef<{ x: number; y: number } | null>(null)
  const pausedRef = useRef(false)
  const [connected, setConnected] = useState(false)
  const [paused, setPaused] = useState(false)
  const [currentWeight, setCurrentWeight] = useState(0)

  // Canvas draw function — runs every animation frame, never triggers React re-renders
  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth
    const h = canvas.clientHeight

    // Set canvas resolution to match display size
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.scale(dpr, dpr)
    }

    const data = dataRef.current
    const pad = { top: 30, right: 60, bottom: 25, left: 10 }
    const plotW = w - pad.left - pad.right
    const plotH = h - pad.top - pad.bottom

    // Auto-range Y axis
    let minVal = Infinity, maxVal = -Infinity
    for (let i = 0; i < data.length; i++) {
      if (data[i] < minVal) minVal = data[i]
      if (data[i] > maxVal) maxVal = data[i]
    }
    // Add some padding to range
    const range = maxVal - minVal || 1
    minVal = minVal - range * 0.1
    maxVal = maxVal + range * 0.1

    // Clear
    ctx.fillStyle = BG_COLOR
    ctx.fillRect(0, 0, w, h)

    // Draw grid
    ctx.strokeStyle = GRID_COLOR
    ctx.lineWidth = 1
    ctx.setLineDash([2, 4])

    // Horizontal grid lines + Y labels
    ctx.fillStyle = TEXT_COLOR
    ctx.font = "10px 'Rajdhani', monospace"
    ctx.textAlign = "right"
    for (let i = 0; i <= GRID_LINES_Y; i++) {
      const y = pad.top + (plotH / GRID_LINES_Y) * i
      ctx.beginPath()
      ctx.moveTo(pad.left, y)
      ctx.lineTo(w - pad.right, y)
      ctx.stroke()

      const val = maxVal - ((maxVal - minVal) / GRID_LINES_Y) * i
      ctx.fillText(`${val.toFixed(0)}`, w - pad.right + 40, y + 4)
    }

    // Vertical grid lines
    for (let i = 0; i <= GRID_LINES_X; i++) {
      const x = pad.left + (plotW / GRID_LINES_X) * i
      ctx.beginPath()
      ctx.moveTo(x, pad.top)
      ctx.lineTo(x, h - pad.bottom)
      ctx.stroke()
    }
    ctx.setLineDash([])

    // Draw the data line with glow
    if (data.length > 1) {
      // Glow layer
      ctx.strokeStyle = LINE_GLOW
      ctx.lineWidth = 4
      ctx.globalAlpha = 0.2
      ctx.beginPath()
      for (let i = 0; i < data.length; i++) {
        const x = pad.left + (i / (data.length - 1)) * plotW
        const y = pad.top + plotH - ((data[i] - minVal) / (maxVal - minVal)) * plotH
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()
      ctx.globalAlpha = 1.0

      // Main line
      ctx.strokeStyle = LINE_COLOR
      ctx.lineWidth = 2
      ctx.lineJoin = "round"
      ctx.beginPath()
      for (let i = 0; i < data.length; i++) {
        const x = pad.left + (i / (data.length - 1)) * plotW
        const y = pad.top + plotH - ((data[i] - minVal) / (maxVal - minVal)) * plotH
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()

      // Current value dot
      const lastX = w - pad.right
      const lastY = pad.top + plotH - ((data[data.length - 1] - minVal) / (maxVal - minVal)) * plotH
      ctx.beginPath()
      ctx.arc(lastX, lastY, 4, 0, Math.PI * 2)
      ctx.fillStyle = LINE_COLOR
      ctx.fill()
      ctx.strokeStyle = LINE_GLOW
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // Draw current value overlay (top-right)
    const curVal = currentValueRef.current
    ctx.fillStyle = LINE_COLOR
    ctx.font = "bold 16px 'Rajdhani', monospace"
    ctx.textAlign = "right"
    ctx.fillText(`${curVal.toFixed(1)}`, w - pad.right + 50, 18)
    ctx.fillStyle = TEXT_COLOR
    ctx.font = "10px 'Rajdhani', monospace"
    ctx.fillText("raw", w - pad.right + 50, 28)

    // Title
    ctx.fillStyle = TEXT_COLOR
    ctx.font = "bold 11px 'Rajdhani', sans-serif"
    ctx.textAlign = "left"
    ctx.fillText("SERIAL PLOTTER — WEIGHT (LIVE)", pad.left + 4, 16)

    // Draw hover tooltip
    const mouse = mouseRef.current
    if (mouse && data.length > 1) {
      const mx = mouse.x
      const my = mouse.y

      // Only show if mouse is within the plot area
      if (mx >= pad.left && mx <= w - pad.right && my >= pad.top && my <= h - pad.bottom) {
        // Find the data index closest to the mouse X
        const dataIndex = Math.round(((mx - pad.left) / plotW) * (data.length - 1))
        const clampedIndex = Math.max(0, Math.min(data.length - 1, dataIndex))
        const val = data[clampedIndex]
        const snapX = pad.left + (clampedIndex / (data.length - 1)) * plotW
        const snapY = pad.top + plotH - ((val - minVal) / (maxVal - minVal)) * plotH

        // Vertical crosshair line
        ctx.strokeStyle = "#475569"
        ctx.lineWidth = 1
        ctx.setLineDash([3, 3])
        ctx.beginPath()
        ctx.moveTo(snapX, pad.top)
        ctx.lineTo(snapX, h - pad.bottom)
        ctx.stroke()
        ctx.setLineDash([])

        // Horizontal crosshair line
        ctx.strokeStyle = "#475569"
        ctx.lineWidth = 1
        ctx.setLineDash([3, 3])
        ctx.beginPath()
        ctx.moveTo(pad.left, snapY)
        ctx.lineTo(w - pad.right, snapY)
        ctx.stroke()
        ctx.setLineDash([])

        // Snap dot
        ctx.beginPath()
        ctx.arc(snapX, snapY, 5, 0, Math.PI * 2)
        ctx.fillStyle = "#f0fdf4"
        ctx.fill()
        ctx.strokeStyle = LINE_COLOR
        ctx.lineWidth = 2
        ctx.stroke()

        // Tooltip box
        const label = `${val.toFixed(2)} g`
        ctx.font = "bold 12px 'Rajdhani', monospace"
        const textW = ctx.measureText(label).width
        const boxW = textW + 16
        const boxH = 24
        // Position tooltip to the right of cursor, flip if near edge
        let tooltipX = snapX + 10
        if (tooltipX + boxW > w - pad.right) tooltipX = snapX - boxW - 10
        let tooltipY = snapY - boxH - 8
        if (tooltipY < pad.top) tooltipY = snapY + 10

        // Box background
        ctx.fillStyle = "#1e293b"
        ctx.beginPath()
        ctx.roundRect(tooltipX, tooltipY, boxW, boxH, 6)
        ctx.fill()
        ctx.strokeStyle = LINE_COLOR
        ctx.lineWidth = 1
        ctx.stroke()

        // Box text
        ctx.fillStyle = "#f0fdf4"
        ctx.textAlign = "center"
        ctx.fillText(label, tooltipX + boxW / 2, tooltipY + 16)
      }
    }

    animFrameRef.current = requestAnimationFrame(draw)
  }, [])

  // Socket.IO connection + data handling
  useEffect(() => {
    const socket = io("http://localhost:5000", {
      transports: ["websocket"],
      reconnection: true,
      reconnectionDelay: 1000,
    })
    socketRef.current = socket

    socket.on("connect", () => {
      setConnected(true)
      console.log("[SerialPlotter] WebSocket connected")
    })

    socket.on("disconnect", () => {
      setConnected(false)
      console.log("[SerialPlotter] WebSocket disconnected")
    })

    socket.on("weight_data", (payload: { w: number; t: number }) => {
      const w = payload.w
      // Push to ring buffer only if not paused
      if (!pausedRef.current) {
        dataRef.current.push(w)
        if (dataRef.current.length > BUFFER_SIZE) {
          dataRef.current.shift()
        }
      }
      currentValueRef.current = w

      // Throttle React state updates to ~10Hz for the display number
      // (Canvas draws independently at 60fps)
    })

    // Throttled state update for the displayed weight number (not the canvas)
    const stateInterval = setInterval(() => {
      const val = currentValueRef.current
      setCurrentWeight(val)
      onWeightUpdate?.(val)
    }, 100)

    return () => {
      socket.disconnect()
      clearInterval(stateInterval)
    }
  }, [onWeightUpdate])

  // Start canvas animation loop
  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(animFrameRef.current)
  }, [draw])

  return (
    <div className="bg-[#0d1424] rounded-xl border border-emerald-900/40 shadow-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-emerald-900/30">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-500" />
          <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest font-[Rajdhani]">
            Serial Plotter
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-[10px] font-mono text-slate-500 uppercase">
            {connected ? "STREAMING" : "OFFLINE"}
          </span>
          <span className="text-lg font-black text-emerald-400 font-[Rajdhani] tabular-nums min-w-[80px] text-right">
            {currentWeight.toFixed(1)}
          </span>
          <button
            onClick={() => {
              const next = !paused
              setPaused(next)
              pausedRef.current = next
            }}
            className={`p-1.5 rounded-md transition-all ${
              paused
                ? 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30'
                : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
            }`}
            title={paused ? "Resume" : "Pause"}
          >
            {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        className="w-full cursor-crosshair"
        style={{ height: "200px", display: "block" }}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top }
        }}
        onMouseLeave={() => {
          mouseRef.current = null
        }}
      />
    </div>
  )
}
