import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"
import { NextResponse } from "next/server"

export async function GET() {
  try {
    const cookieStore = await cookies()
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() {
            return cookieStore.getAll()
          },
          setAll(cookiesToSet) {
            try {
              cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options))
            } catch {
              // Handle cookie setting errors
            }
          },
        },
      },
    )

    const { data, error } = await supabase
      .from("coconut_assessments")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(50)

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 400 })
    }

    return NextResponse.json(
      data.map((record: any) => ({
        id: record.id,
        weight: record.weight,
        diameter: record.diameter,
        waterContent: record.water_content,
        shellColor: record.shell_color,
        shakeSound: record.shake_sound,
        moldSpots: record.mold_spots,
        cracksDamage: record.cracks_damage,
        score: record.score,
        grade: record.grade,
        issues: record.issues,
        recommendations: record.recommendations,
        createdAt: record.created_at,
        mlConfidence: record.ml_confidence,
      })),
    )
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}
