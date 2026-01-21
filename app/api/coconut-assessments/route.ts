import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"
import { type NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
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

    const data = await request.json()

    const { data: result, error } = await supabase
      .from("coconut_assessments")
      .insert([
        {
          weight: data.weight,
          diameter: data.diameter,
          water_content: data.waterContent,
          shell_color: data.shellColor,
          shake_sound: data.shakeSound,
          mold_spots: data.moldSpots,
          cracks_damage: data.cracksDamage,
          score: data.score,
          grade: data.grade,
          issues: data.issues,
          recommendations: data.recommendations,
          ml_confidence: data.mlConfidence,
        },
      ])
      .select()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 400 })
    }

    return NextResponse.json(result)
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}
