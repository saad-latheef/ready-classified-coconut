"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { CheckCircle2, AlertCircle, Info } from "lucide-react"

interface GradingResult {
  isGradeA: boolean
  score: number
  issues: string[]
  recommendations: string[]
}

interface GradingResultProps {
  result: GradingResult
}

export function GradingResult({ result }: GradingResultProps) {
  return (
    <Card className="md:col-span-1">
      <CardHeader>
        <CardTitle>Grading Result</CardTitle>
        <CardDescription>Food-grade assessment</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="text-center py-4 bg-accent/10 rounded-lg border border-accent/30">
          <div className="text-5xl font-bold text-primary mb-2">{result.score}</div>
          <p className="text-sm text-muted-foreground">Quality Score</p>
        </div>

        <div className="flex items-center gap-3 p-4 rounded-lg bg-secondary/20 border border-secondary/40">
          {result.isGradeA ? (
            <>
              <CheckCircle2 className="w-6 h-6 text-accent flex-shrink-0" />
              <div>
                <p className="font-semibold text-accent">Grade A - Food Grade</p>
                <p className="text-xs text-muted-foreground">Meets premium standards</p>
              </div>
            </>
          ) : result.score >= 60 ? (
            <>
              <Info className="w-6 h-6 text-accent flex-shrink-0" />
              <div>
                <p className="font-semibold text-accent">Grade B - Conditional</p>
                <p className="text-xs text-muted-foreground">Limited food use</p>
              </div>
            </>
          ) : (
            <>
              <AlertCircle className="w-6 h-6 text-destructive flex-shrink-0" />
              <div>
                <p className="font-semibold text-destructive">Below Grade</p>
                <p className="text-xs text-muted-foreground">Not food-grade</p>
              </div>
            </>
          )}
        </div>

        {result.issues.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold mb-3 text-foreground">Issues Found:</h3>
            <ul className="space-y-2">
              {result.issues.map((issue, idx) => (
                <li key={idx} className="text-sm text-muted-foreground flex gap-2">
                  <span className="text-destructive">•</span>
                  {issue}
                </li>
              ))}
            </ul>
          </div>
        )}

        {result.recommendations.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold mb-3 text-foreground">Recommendations:</h3>
            <ul className="space-y-2">
              {result.recommendations.map((rec, idx) => (
                <li key={idx} className="text-sm text-muted-foreground flex gap-2">
                  <span className="text-accent">✓</span>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
