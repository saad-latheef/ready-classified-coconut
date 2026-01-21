-- Create coconut assessments table
CREATE TABLE IF NOT EXISTS coconut_assessments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  weight DECIMAL(5,2) NOT NULL,
  diameter DECIMAL(5,2) NOT NULL,
  water_content DECIMAL(5,2) NOT NULL,
  shell_color VARCHAR(50) NOT NULL,
  shake_sound VARCHAR(50) NOT NULL,
  mold_spots BOOLEAN DEFAULT FALSE,
  cracks_damage BOOLEAN DEFAULT FALSE,
  score INTEGER NOT NULL,
  grade VARCHAR(20) NOT NULL,
  issues TEXT[] DEFAULT ARRAY[]::TEXT[],
  recommendations TEXT[] DEFAULT ARRAY[]::TEXT[],
  webcam_image_url TEXT,
  ml_confidence DECIMAL(5,3),
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_coconut_created_at ON coconut_assessments(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coconut_grade ON coconut_assessments(grade);

-- Enable RLS
ALTER TABLE coconut_assessments ENABLE ROW LEVEL SECURITY;

-- Create RLS policy to allow all reads and writes (adjust based on your auth needs)
DROP POLICY IF EXISTS "Enable read access for all" ON coconut_assessments;
DROP POLICY IF EXISTS "Enable write access for all" ON coconut_assessments;

CREATE POLICY "Enable read access for all" ON coconut_assessments
  FOR SELECT USING (true);

CREATE POLICY "Enable write access for all" ON coconut_assessments
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for all" ON coconut_assessments
  FOR UPDATE USING (true);
