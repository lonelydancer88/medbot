export interface Message {
  id?: number
  role: 'patient' | 'ai'
  content: string
  thinking?: string
}

export interface Diagnosis {
  disease: string
  probability: string
  reason: string
}

export interface SessionData {
  session_id: string
  status: string
  phase: string
  created_at?: string
  updated_at?: string
  messages?: Message[]
  diagnoses?: Diagnosis[]
  medical_record?: string
}

export interface ChatResponse {
  reply: string
  phase: string
  is_complete: boolean
  thinking?: string
}

export interface CreateSessionResponse {
  session_id: string
  reply: string
  phase: string
  thinking?: string
}

// Streaming types
export interface StreamDoneData {
  text: string
  thinking: string
}

export interface StreamPhaseData {
  phase: string
  is_complete: boolean
}

export interface StreamDiagnosisData {
  diagnoses: Diagnosis[]
  content: string
}

export interface StreamMedicalRecordData {
  content: string
  thinking?: string
}

export interface StreamCallbacks {
  onConnected: () => void
  onThinking: (delta: string) => void
  onText: (delta: string) => void
  onDone: (data: StreamDoneData) => void
  onDiagnosis: (data: StreamDiagnosisData) => void
  onMedicalRecord: (data: StreamMedicalRecordData) => void
  onPhase: (data: StreamPhaseData) => void
  onError: (error: string) => void
}
