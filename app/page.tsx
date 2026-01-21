"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Camera, History, Menu, X, MessageSquare, ChevronRight } from "lucide-react"
import { WebcamFeed } from "@/components/webcam-feed"
import { CoconutHistory } from "@/components/coconut-history"
import { AIChatbot } from "@/components/ai-chatbot"

interface CoconutRecord {
  id: string
  weight: number
  diameter: number
  height: number
  majorAxis: number
  minorAxis: number
  volume: number
  density: number
  waterContent: number
  shellColor: string
  shakeSound: string
  moldSpots: boolean
  cracksDamage: boolean
  score: number
  grade: string
  issues: string[]
  recommendations: string[]
  createdAt: string
  mlConfidence?: number
  geminiAnalysis?: string
  predictions?: any
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<"live" | "history">("live")
  const [history, setHistory] = useState<CoconutRecord[]>([])
  const [selectedRecord, setSelectedRecord] = useState<CoconutRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [chatbotOpen, setChatbotOpen] = useState(false)

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
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } md:translate-x-0 fixed md:static inset-y-0 left-0 z-50 w-64 bg-white border-r border-green-200 transition-transform duration-300 ease-in-out flex flex-col`}
      >
        {/* Sidebar Header */}
        <div className="p-6 border-b border-green-200">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-green-700">Coconut Grader</h1>
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-5 h-5" />
            </Button>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 p-4 space-y-2">
          <Button
            variant={activeTab === "live" ? "default" : "ghost"}
            onClick={() => {
              setActiveTab("live")
              setSelectedRecord(null)
              setSidebarOpen(false)
            }}
            className={`w-full justify-start ${
              activeTab === "live"
                ? "bg-green-600 hover:bg-green-700 text-white"
                : "text-green-600 hover:bg-green-50"
            }`}
          >
            <Camera className="w-4 h-4 mr-3" />
            Live Stream
          </Button>
          <Button
            variant={activeTab === "history" ? "default" : "ghost"}
            onClick={() => {
              setActiveTab("history")
              setSidebarOpen(false)
              fetchHistory() // Fetch fresh data from database
            }}
            className={`w-full justify-start ${
              activeTab === "history"
                ? "bg-green-600 hover:bg-green-700 text-white"
                : "text-green-600 hover:bg-green-50"
            }`}
          >
            <History className="w-4 h-4 mr-3" />
            History
          </Button>
        </nav>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-green-200">
          <p className="text-xs text-gray-500 text-center">
            Powered by AI & ML Agents
          </p>
        </div>
      </div>

      {/* Mobile Menu Button */}
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden fixed top-4 left-4 z-40 bg-white shadow-md"
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        <Menu className="w-5 h-5" />
      </Button>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Primary Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-3xl font-bold text-gray-800 mb-6">
              {activeTab === "live" ? "Live Coconut Detection" : "Assessment History"}
            </h2>
            {activeTab === "live" ? (
              <WebcamFeed />
            ) : (
              <CoconutHistory
                history={history}
                loading={loading}
                selectedId={selectedRecord?.id}
                onSelectRecord={handleViewRecord}
                onDeleteRecord={handleDeleteRecord}
              />
            )}
          </div>
        </div>
      </div>

      {/* AI Chatbot Toggle Button */}
      <Button
        onClick={() => setChatbotOpen(!chatbotOpen)}
        className={`fixed bottom-6 right-6 md:bottom-auto md:top-6 ${
          chatbotOpen ? "md:right-[25rem]" : "md:right-6"
        } z-50 bg-green-600 hover:bg-green-700 text-white shadow-lg transition-all duration-300`}
        size="lg"
      >
        {chatbotOpen ? (
          <>
            <ChevronRight className="w-5 h-5 mr-2" />
            <span className="hidden md:inline">Close AI</span>
          </>
        ) : (
          <>
            <MessageSquare className="w-5 h-5 mr-2" />
            <span className="hidden md:inline">AI Copilot</span>
          </>
        )}
      </Button>

      {/* AI Chatbot Panel - Collapsible */}
      <div
        className={`${
          chatbotOpen ? "translate-x-0" : "translate-x-full"
        } fixed right-0 top-0 bottom-0 w-full md:w-96 bg-white border-l border-green-200 shadow-2xl transition-transform duration-300 ease-in-out z-40`}
      >
        <AIChatbot />
      </div>

      {/* Overlay for mobile chatbot */}
      {chatbotOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black bg-opacity-50 z-30"
          onClick={() => setChatbotOpen(false)}
        />
      )}

      {/* Overlay for mobile sidebar */}
      {sidebarOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  )
}
