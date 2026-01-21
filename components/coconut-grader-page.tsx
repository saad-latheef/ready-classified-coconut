"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { CheckCircle2, AlertCircle, Info, Trash2, Camera, History } from "lucide-react"
import { AssessmentForm } from "./assessment-form"
import { GradingResult } from "./grading-result"
import { CoconutHistory } from "./coconut-history"
import { WebcamFeed } from "./webcam-feed"

interface CoconutData {
  weight: number
  diameter: number
  waterContent: number
  shellColor: string
  shakeSound: string
  moldSpots: boolean
  cracksDamage: boolean
}

interface GradingResultType {
  isGradeA: boolean
  score: number
  issues: string[]
  recommendations: string[]
}

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
  createdAt: string
  mlConfidence?: number
}

export function CoconutGraderPage() {
  const [activeTab, setActiveTab] = useState<"live" | "history">("live")
  const [formData, setFormData] = useState<CoconutData>({
    weight: 0,
    diameter: 0,
    waterContent: 0,
    shellColor: "brown",
    shakeSound: "full",
    moldSpots: false,
    cracksDamage: false,
  })

  const [result, setResult] = useState<GradingResultType | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [history, setHistory] = useState<CoconutRecord[]>([])
  const [selectedRecord, setSelectedRecord] = useState<CoconutRecord | null>(null)
  const [loading, setLoading] = useState(true)

  // Fetch history on component mount
  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    try {
      setLoading(true)
      const response = await fetch("/api/coconut-history")
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

  const gradeCoconut = (): GradingResultType => {
    let score = 100
    const issues: string[] = []
    const recommendations: string[] = []

    // Weight check (ideal: 1.2-1.6 kg)
    if (formData.weight < 1.0 || formData.weight > 1.8) {
      score -= 15
      issues.push("Weight outside ideal range (1.2-1.6 kg)")
    }

    // Diameter check (ideal: 15-18 cm)
    if (formData.diameter < 14 || formData.diameter > 19) {
      score -= 12
      issues.push("Diameter outside ideal range (15-18 cm)")
    }

    // Water content check (ideal: 5-12%)
    if (formData.waterContent < 5 || formData.waterContent > 12) {
      score -= 20
      issues.push("Water content outside optimal range (5-12%)")
    }

    // Shell color assessment
    if (formData.shellColor === "green") {
      score -= 25
      issues.push("Coconut not mature enough - green shell indicates premature harvest")
    } else if (formData.shellColor === "blackened") {
      score -= 30
      issues.push("Shell showing signs of age or damage - darkened coloration")
    }

    // Shake sound assessment
    if (formData.shakeSound === "hollow") {
      score -= 18
      issues.push("Hollow sound indicates low or no water content")
    }

    // Mold spots
    if (formData.moldSpots) {
      score -= 25
      issues.push("Mold spots detected - food safety concern")
      recommendations.push("Do not use for food grade purposes")
    }

    // Cracks or damage
    if (formData.cracksDamage) {
      score -= 20
      issues.push("Visible cracks or physical damage")
      recommendations.push("Inspect for potential contamination")
    }

    // Add recommendations based on score
    if (score >= 80) {
      recommendations.push("Meets Grade A food quality standards")
    } else if (score >= 60) {
      recommendations.push("Meets Grade B standards - suitable for some food applications")
    } else {
      recommendations.push("Does not meet food-grade standards - consider for non-food use")
    }

    score = Math.max(0, score)

    return {
      isGradeA: score >= 80 && !formData.moldSpots && !formData.cracksDamage,
      score,
      issues,
      recommendations,
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? (e.target as HTMLInputElement).checked : Number.parseFloat(value) || value,
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const gradingResult = gradeCoconut()
    setResult(gradingResult)
    setSubmitted(true)

    // Save to database
    try {
      await fetch("/api/coconut-assessments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...formData,
          score: gradingResult.score,
          grade: gradingResult.isGradeA ? "Grade A" : gradingResult.score >= 60 ? "Grade B" : "Below Grade",
          issues: gradingResult.issues,
          recommendations: gradingResult.recommendations,
        }),
      })
      // Refresh history
      await fetchHistory()
    } catch (error) {
      console.error("Failed to save assessment:", error)
    }
  }

  const handleDeleteRecord = async (id: string) => {
    try {
      await fetch(`/api/coconut-assessments/${id}`, { method: "DELETE" })
      setHistory(history.filter((r) => r.id !== id))
      setSelectedRecord(null)
    } catch (error) {
      console.error("Failed to delete record:", error)
    }
  }

  const handleViewRecord = (record: CoconutRecord) => {
    setSelectedRecord(record)
  }

  const handleWebcamCapture = (data: Partial<CoconutData> & { mlConfidence?: number }) => {
    // Pre-fill form with ML detected data
    setFormData((prev) => ({
      ...prev,
      ...data,
    }))
  }

  return (
    <div className="flex h-screen bg-background">
      <div className="w-80 border-r border-border bg-card flex flex-col">
        <div className="flex gap-2 p-3 border-b border-border">
          <Button
            variant={activeTab === "live" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("live")}
            className="flex-1 gap-2"
          >
            <Camera className="w-4 h-4" />
            Live Stream
          </Button>
          <Button
            variant={activeTab === "history" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("history")}
            className="flex-1 gap-2"
          >
            <History className="w-4 h-4" />
            History
          </Button>
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === "live" ? (
            <WebcamFeed onCapture={handleWebcamCapture} />
          ) : (
            <div className="overflow-y-auto p-4 h-full">
              <CoconutHistory
                history={history}
                loading={loading}
                selectedId={selectedRecord?.id}
                onSelectRecord={handleViewRecord}
                onDeleteRecord={handleDeleteRecord}
              />
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          {selectedRecord ? (
            <div className="space-y-6">
              <Button variant="outline" onClick={() => setSelectedRecord(null)} className="mb-4">
                ← Back to Assessment
              </Button>

              <div className="mb-8">
                <h1 className="text-4xl font-bold text-primary mb-2">Coconut Assessment Details</h1>
                <p className="text-lg text-muted-foreground">
                  Assessed on {new Date(selectedRecord.createdAt).toLocaleString()}
                </p>
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                {/* Assessment Data */}
                <Card>
                  <CardHeader>
                    <CardTitle>Measurement Data</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Weight</p>
                        <p className="text-lg font-semibold">{selectedRecord.weight} kg</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Diameter</p>
                        <p className="text-lg font-semibold">{selectedRecord.diameter} cm</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Water Content</p>
                        <p className="text-lg font-semibold">{selectedRecord.waterContent}%</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Shell Color</p>
                        <p className="text-lg font-semibold capitalize">{selectedRecord.shellColor}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Shake Sound</p>
                        <p className="text-lg font-semibold capitalize">{selectedRecord.shakeSound}</p>
                      </div>
                      {selectedRecord.mlConfidence && (
                        <div>
                          <p className="text-sm text-muted-foreground">ML Confidence</p>
                          <p className="text-lg font-semibold">{(selectedRecord.mlConfidence * 100).toFixed(1)}%</p>
                        </div>
                      )}
                    </div>

                    <div className="pt-4 space-y-2 border-t border-border">
                      <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={selectedRecord.moldSpots} disabled className="w-4 h-4" />
                        <span>Mold Spots</span>
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={selectedRecord.cracksDamage} disabled className="w-4 h-4" />
                        <span>Cracks or Damage</span>
                      </label>
                    </div>
                  </CardContent>
                </Card>

                {/* Grade Result */}
                <Card>
                  <CardHeader>
                    <CardTitle>Grade Result</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="text-center py-4 bg-accent/10 rounded-lg border border-accent/30">
                      <div className="text-5xl font-bold text-primary mb-2">{selectedRecord.score}</div>
                      <p className="text-sm text-muted-foreground">Quality Score</p>
                    </div>

                    <div className="flex items-center gap-3 p-4 rounded-lg bg-secondary/20 border border-secondary/40">
                      {selectedRecord.grade === "Grade A" ? (
                        <>
                          <CheckCircle2 className="w-6 h-6 text-accent flex-shrink-0" />
                          <div>
                            <p className="font-semibold text-accent">{selectedRecord.grade}</p>
                            <p className="text-xs text-muted-foreground">Meets premium standards</p>
                          </div>
                        </>
                      ) : selectedRecord.grade === "Grade B" ? (
                        <>
                          <Info className="w-6 h-6 text-accent flex-shrink-0" />
                          <div>
                            <p className="font-semibold text-accent">{selectedRecord.grade}</p>
                            <p className="text-xs text-muted-foreground">Limited food use</p>
                          </div>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-6 h-6 text-destructive flex-shrink-0" />
                          <div>
                            <p className="font-semibold text-destructive">{selectedRecord.grade}</p>
                            <p className="text-xs text-muted-foreground">Not food-grade</p>
                          </div>
                        </>
                      )}
                    </div>

                    <Button
                      variant="destructive"
                      onClick={() => handleDeleteRecord(selectedRecord.id)}
                      className="w-full"
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      Delete Record
                    </Button>
                  </CardContent>
                </Card>

                {/* Issues */}
                {selectedRecord.issues.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Issues Found</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2">
                        {selectedRecord.issues.map((issue, idx) => (
                          <li key={idx} className="text-sm text-muted-foreground flex gap-2">
                            <span className="text-destructive">•</span>
                            {issue}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {/* Recommendations */}
                {selectedRecord.recommendations.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Recommendations</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2">
                        {selectedRecord.recommendations.map((rec, idx) => (
                          <li key={idx} className="text-sm text-muted-foreground flex gap-2">
                            <span className="text-accent">✓</span>
                            {rec}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          ) : (
            <div>
              <div className="mb-8">
                <h1 className="text-4xl font-bold text-primary mb-2">🥥 Coconut Grader</h1>
                <p className="text-lg text-muted-foreground">Professional food-grade quality assessment system</p>
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                {/* Input Form */}
                <AssessmentForm formData={formData} onInputChange={handleInputChange} onSubmit={handleSubmit} />

                {/* Results Display */}
                {submitted && result && <GradingResult result={result} />}

                {/* Initial Guidance */}
                {!submitted && (
                  <Card className="md:col-span-1">
                    <CardHeader>
                      <CardTitle>Grading Standards</CardTitle>
                      <CardDescription>What makes a Grade A coconut</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4 text-sm">
                      <div>
                        <h3 className="font-semibold text-foreground mb-2">Weight & Size</h3>
                        <p className="text-muted-foreground">Optimal weight is 1.2-1.6 kg with diameter of 15-18 cm</p>
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground mb-2">Water Content</h3>
                        <p className="text-muted-foreground">
                          Ideal range is 5-12% for optimal flavor and preservation
                        </p>
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground mb-2">Shell Quality</h3>
                        <p className="text-muted-foreground">
                          Brown mature shell with no visible damage or discoloration
                        </p>
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground mb-2">Safety</h3>
                        <p className="text-muted-foreground">
                          No mold, cracks, or contamination for food-grade approval
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
