"use client"

import type React from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface CoconutData {
  weight: number
  diameter: number
  waterContent: number
  shellColor: string
  shakeSound: string
  moldSpots: boolean
  cracksDamage: boolean
}

interface AssessmentFormProps {
  formData: CoconutData
  onInputChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void
  onSubmit: (e: React.FormEvent) => void
}

export function AssessmentForm({ formData, onInputChange, onSubmit }: AssessmentFormProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Assessment Form</CardTitle>
        <CardDescription>Enter coconut specifications below</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium mb-2">Weight (kg)</label>
            <input
              type="number"
              name="weight"
              step="0.1"
              min="0"
              value={formData.weight || ""}
              onChange={onInputChange}
              placeholder="1.2 - 1.6 kg"
              className="w-full px-3 py-2 border border-input bg-card rounded-md text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">Ideal: 1.2-1.6 kg</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Diameter (cm)</label>
            <input
              type="number"
              name="diameter"
              step="0.5"
              min="0"
              value={formData.diameter || ""}
              onChange={onInputChange}
              placeholder="15 - 18 cm"
              className="w-full px-3 py-2 border border-input bg-card rounded-md text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">Ideal: 15-18 cm</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Water Content (%)</label>
            <input
              type="number"
              name="waterContent"
              step="0.5"
              min="0"
              max="100"
              value={formData.waterContent || ""}
              onChange={onInputChange}
              placeholder="5 - 12%"
              className="w-full px-3 py-2 border border-input bg-card rounded-md text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">Ideal: 5-12%</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Shell Color</label>
            <select
              name="shellColor"
              value={formData.shellColor}
              onChange={onInputChange}
              className="w-full px-3 py-2 border border-input bg-card rounded-md text-sm"
            >
              <option value="brown">Brown (Mature)</option>
              <option value="green">Green (Immature)</option>
              <option value="golden">Golden</option>
              <option value="blackened">Blackened</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Sound When Shaken</label>
            <select
              name="shakeSound"
              value={formData.shakeSound}
              onChange={onInputChange}
              className="w-full px-3 py-2 border border-input bg-card rounded-md text-sm"
            >
              <option value="full">Full/Splash Sound</option>
              <option value="semi">Semi-Full</option>
              <option value="hollow">Hollow/No Sound</option>
            </select>
          </div>

          <div className="space-y-3 pt-2">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                name="moldSpots"
                checked={formData.moldSpots}
                onChange={onInputChange}
                className="w-4 h-4 rounded border-input"
              />
              <span className="text-sm font-medium">Visible mold spots</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                name="cracksDamage"
                checked={formData.cracksDamage}
                onChange={onInputChange}
                className="w-4 h-4 rounded border-input"
              />
              <span className="text-sm font-medium">Cracks or visible damage</span>
            </label>
          </div>

          <Button type="submit" className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
            Grade Coconut
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
