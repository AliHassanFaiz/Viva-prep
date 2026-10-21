import { API_URL } from "./settings";
import type { DocumentInfo, HistoryItem, Mode, Question, Report, SessionCreated, SessionDetail } from "./types";
import { getUserId } from "./userId";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-User-Id", getUserId());
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try { data = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    throw new ApiError(res.status, data?.error?.code ?? "error", data?.error?.message ?? `Request failed (${res.status}).`);
  }
  return data as T;
}

export const api = {
  uploadDocument(file: File, mode: Mode) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("mode", mode);
    return request<{ document_id: string; status: string }>("/api/documents", { method: "POST", body: fd });
  },
  getDocument: (id: string) => request<DocumentInfo>(`/api/documents/${id}`),
  deleteDocument: (id: string) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  generateQuestions: (id: string, n = 3) =>
    request<{ questions: Question[] }>(`/api/documents/${id}/questions`, { method: "POST", body: JSON.stringify({ n }) }),
  listQuestions: (id: string) => request<{ questions: Question[] }>(`/api/documents/${id}/questions`),
  patchQuestion: (id: string, body: Partial<Pick<Question, "text" | "accepted" | "position">>) =>
    request<Question>(`/api/questions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteQuestion: (id: string) => request<void>(`/api/questions/${id}`, { method: "DELETE" }),
  createSession: (document_id: string, question_ids: string[]) =>
    request<SessionCreated>("/api/sessions", { method: "POST", body: JSON.stringify({ document_id, question_ids }) }),
  getSession: (id: string) => request<SessionDetail>(`/api/sessions/${id}`),
  listSessions: () => request<HistoryItem[]>("/api/sessions"),
  deleteSession: (id: string) => request<void>(`/api/sessions/${id}`, { method: "DELETE" }),
  getReport: (id: string) => request<Report>(`/api/sessions/${id}/report`),
  endSession: (id: string) => request<{ status: string }>(`/api/sessions/${id}/end`, { method: "POST" }),
  async fetchAudio(url: string): Promise<Blob | null> {
    try {
      const res = await fetch(url.startsWith("http") ? url : `${API_URL}${url}`, { headers: { "X-User-Id": getUserId() } });
      if (!res.ok) return null;
      const b = await res.blob();
      return b.size > 0 ? b : null;
    } catch { return null; }
  },
};
