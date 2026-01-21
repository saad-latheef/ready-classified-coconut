"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { CoconutHistory } from "@/components/coconut-history"
import { ArrowLeft, Loader2 } from "lucide-react"
import { useRouter } from "next/navigation"

interface CoconutRecord {
  id: string
  weight: number
  diameter: number
  waterContent: number
  shellColor: string
  shakeSound: string
  moldSpots: boolean
  cracksDamage: boolean
  score: number
  grade: string
  issues: string[]
  recommendations: string[]
  geminiAnalysis?: string
  createdAt: string
}

export default function HistoryPage() {
  const router = useRouter()
  const [history, setHistory] = useState<CoconutRecord[]>([])
  const [selectedRecord, setSelectedRecord] = useState<CoconutRecord | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    try {
      setLoading(true)
      const response = await fetch("http://localhost:5000/api/history")
      if (response.ok) {
        const data = await response.json()
        setHistory(data)
      }
    } catch (error) {
      console.error("Failed to fetch history:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteRecord = async (id: string) => {
    try {
      await fetch(`http://localhost:5000/api/coconut-assessments/${id}`, { method: "DELETE" })
      setHistory(history.filter((r) => r.id !== id))
      setSelectedRecord(null)
    } catch (error) {
      console.error("Failed to delete record:", error)
    }
  }

  const handleViewRecord = (record: CoconutRecord) => {
    setSelectedRecord(record)
  }

  return (
    <div className="flex flex-col min-h-screen bg-white">
      {/* Header */}
      <div className="border-b border-green-200 bg-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/")}
            className="text-green-600 hover:text-green-700 hover:bg-green-50"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Live Stream
          </Button>
          <h1 className="text-2xl font-bold text-green-700">Assessment History</h1>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-green-600" />
          </div>
        ) : (
          <div className="max-w-6xl mx-auto">
            <CoconutHistory
              history={history}
              loading={loading}
              selectedId={selectedRecord?.id}
              onSelectRecord={handleViewRecord}
              onDeleteRecord={handleDeleteRecord}
            />

            {/* Selected Record Detail View */}
            {selectedRecord && (
              <div className="mt-6 p-6 bg-green-50 border border-green-200 rounded-lg">
                <h3 className="text-lg font-bold text-green-800 mb-4">Assessment Details</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-semibold text-green-700">Grade:</span> {selectedRecord.grade}
                  </div>
                  <div>
                    <span className="font-semibold text-green-700">Score:</span> {selectedRecord.score}/100
                  </div>
                  <div>
                    <span className="font-semibold text-green-700">Diameter:</span> {selectedRecord.diameter} cm
                  </div>
                  <div>
                    <span className="font-semibold text-green-700">Shell Color:</span> {selectedRecord.shellColor}
                  </div>
                  <div className="col-span-2">
                    <span className="font-semibold text-green-700">Issues:</span>{" "}
                    {selectedRecord.issues.length > 0 ? selectedRecord.issues.join(", ") : "None"}
                  </div>
                  <div className="col-span-2">
                    <span className="font-semibold text-green-700">Recommendations:</span>{" "}
                    {selectedRecord.recommendations.join(", ")}
                  </div>
                  {selectedRecord.geminiAnalysis && (
                    <div className="col-span-2 mt-4 p-4 bg-white border border-green-300 rounded-md">
                      <h4 className="font-semibold text-green-800 mb-2">🤖 AI Analysis</h4>
                      <p className="text-gray-700 whitespace-pre-wrap">{selectedRecord.geminiAnalysis}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
