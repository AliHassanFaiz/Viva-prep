export interface AuthUser { id: string; email: string }
export interface AuthResponse { access_token: string; token_type: string; user: AuthUser }
export type Mode = "viva" | "interview";
export interface Question {
  id: string; position: number; text: string; topic: string | null; difficulty: string | null;
  key_points: string[]; accepted: boolean;
}
export interface SessionQuestion { session_question_id: string; position: number; text: string; audio_url: string | null }
export interface SessionCreated { session_id: string; mode: Mode; audio_ready: boolean; questions: SessionQuestion[]; static_audio: string[] }
export interface DocumentInfo { id: string; filename: string; status: "processing" | "ready" | "failed"; error: string | null; page_count: number | null; chunk_count: number | null; mode: Mode }
export type CallState = "idle" | "speaking" | "listening" | "thinking" | "ended";

export interface Scores { accuracy: number; completeness: number; clarity: number; justification: number }
export interface ReportQuestion {
  session_question_id: string; position: number; question: string; topic: string | null; status: "ok" | "failed" | null;
  question_score: number | null; scores: Scores | null; covered_points: string[]; missed_points: string[];
  incorrect_claims: string[]; feedback: string | null; model_answer: string | null;
  transcript: { answer: string; followup: string | null; followup_answer: string | null };
}
export interface Report {
  status: "pending" | "running" | "ready" | "failed";
  progress: { done: number; total: number };
  overall_score: number | null; band: "needs_work" | "developing" | "ready" | null; avg_wpm: number | null;
  summary: { strengths: string[]; gaps: string[]; practice_next: string[]; overall_comment: string } | null;
  error: string | null; questions: ReportQuestion[];
}
export interface HistoryItem { id: string; created_at: string; document_name: string; status: string; overall_score: number | null; band: string | null; mode?: Mode }
export interface SessionDetail {
  id: string; status: string; document_name: string; mode: Mode; audio_ready: boolean; static_audio: string[]; questions: SessionQuestion[];
}
