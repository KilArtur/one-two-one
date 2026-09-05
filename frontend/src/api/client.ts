/** Типизированный клиент backend API (FastAPI). */

export interface HealthResponse {
  status: string;
  app_env: string;
  version: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Запрос ${path} завершился со статусом ${response.status}`);
  }
  return (await response.json()) as T;
}

export const apiClient = {
  getHealth: (): Promise<HealthResponse> => request<HealthResponse>("/health"),
};

export interface ConsentResponse {
  consent_given_at: string | null;
}

async function candidateRequest<T>(path: string, token?: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/candidate-auth/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    throw new Error(response.status === 401 || response.status === 403
      ? "Не удалось получить доступ. Откройте приглашение заново или обратитесь к рекрутеру."
      : "Не удалось сохранить или загрузить данные. Попробуйте ещё раз.");
  }
  return response.json() as Promise<T>;
}

export const candidateApi = {
  exchange: (token: string) => candidateRequest<{ access_token: string }>("exchange", undefined, { token }),
  consent: (token: string) => candidateRequest<ConsentResponse>("consent", token),
  acceptConsent: (token: string) => candidateRequest<ConsentResponse>("consent", token, { accepted: true }),
  equipmentAccess: (token: string) => candidateRequest<ConsentResponse>("equipment-check", token),
};


export interface InterviewQuestion {
  id: string;
  topic_id: string;
  type: "core" | "personal" | "follow_up";
  text: string;
}

export interface FollowupDecision {
  ask: boolean;
  reason: string;
  question: InterviewQuestion | null;
}

export interface InterviewSessionState {
  current_question: InterviewQuestion | null;
  answered_count: number;
  total: number;
  finished: boolean;
}

export async function getInterviewSession(
  token: string,
  signal?: AbortSignal,
): Promise<InterviewSessionState> {
  const response = await fetch(`${API_BASE_URL}/candidate-interview/session`, {
    headers: { Authorization: `Bearer ${token}` }, signal,
  });
  if (!response.ok) throw new Error("Сессия недоступна. Проверьте приглашение.");
  return response.json() as Promise<InterviewSessionState>;
}

export async function interruptInterviewSession(
  token: string,
  signal?: AbortSignal,
): Promise<InterviewSessionState> {
  const response = await fetch(`${API_BASE_URL}/candidate-interview/session/interrupt`, {
    method: "POST", headers: { Authorization: `Bearer ${token}` }, signal,
  });
  if (!response.ok) throw new Error("Не удалось обновить состояние сессии.");
  return response.json() as Promise<InterviewSessionState>;
}

export async function requestFollowup(
  token: string,
  topicId: string,
  signal?: AbortSignal,
): Promise<FollowupDecision> {
  const response = await fetch(
    `${API_BASE_URL}/candidate-interview/topics/${topicId}/followup`,
    { method: "POST", headers: { Authorization: `Bearer ${token}` }, signal },
  );
  if (!response.ok) throw new Error("Не удалось получить уточняющий вопрос.");
  return response.json() as Promise<FollowupDecision>;
}

export async function getInterviewQuestions(token: string, signal?: AbortSignal): Promise<InterviewQuestion[]> {
  const response = await fetch(`${API_BASE_URL}/candidate-interview/questions`, {
    headers: { Authorization: `Bearer ${token}` }, signal,
  });
  if (!response.ok) throw new Error("Не удалось открыть вопросы. Проверьте приглашение или обратитесь к рекрутеру.");
  return response.json() as Promise<InterviewQuestion[]>;
}

export async function getQuestionAudio(token: string, questionId: string, signal: AbortSignal): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}/candidate-interview/questions/${questionId}/audio`, {
    headers: { Authorization: `Bearer ${token}` }, signal,
  });
  if (!response.ok) throw new Error("Озвучка недоступна. Попробуйте ещё раз.");
  return response;
}

export async function skipQuestion(
  token: string,
  questionId: string,
  signal?: AbortSignal,
): Promise<{ question_id: string; skipped: boolean }> {
  const response = await fetch(
    `${API_BASE_URL}/candidate-interview/questions/${questionId}/skip`,
    { method: "POST", headers: { Authorization: `Bearer ${token}` }, signal },
  );
  if (!response.ok) throw new Error("Не удалось пропустить вопрос.");
  return response.json() as Promise<{ question_id: string; skipped: boolean }>;
}

export interface SubmitResult {
  candidate_id: string;
  used_at: string;
  candidate_status: string;
}

export async function submitInterview(token: string, signal?: AbortSignal): Promise<SubmitResult> {
  const response = await fetch(`${API_BASE_URL}/candidate-auth/submit`, {
    method: "POST", headers: { Authorization: `Bearer ${token}` }, signal,
  });
  if (!response.ok) throw new Error("Не удалось отправить интервью.");
  return response.json() as Promise<SubmitResult>;
}

export interface CandidateOverview {
  candidate_id: string;
  candidate_status: string;
  processing_status: string;
  confirmed_count: number;
  needs_check_count: number;
  not_confirmed_count: number;
  recommendation: string | null;
}

export async function listCandidates(
  token: string,
  vacancyId: string,
  processingStatus?: string,
  signal?: AbortSignal,
): Promise<CandidateOverview[]> {
  const params = new URLSearchParams({ vacancy_id: vacancyId });
  if (processingStatus) params.set("processing_status", processingStatus);
  const response = await fetch(`${API_BASE_URL}/candidates?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` }, signal,
  });
  if (!response.ok) throw new Error("Не удалось загрузить список кандидатов.");
  return response.json() as Promise<CandidateOverview[]>;
}

export interface ResultTopicRow {
  topic_id: string;
  topic_title: string;
  skill_type: "hard" | "soft";
  importance: "mandatory" | "desired";
  system_status: string;
  current_status: string;
  author: string;
  reasoning_summary: string | null;
  has_evidence?: boolean;
}

export interface ResultCard {
  candidate_id: string;
  recommendation: string;
  recommendation_reason: string;
  confirmed_count: number;
  needs_check_count: number;
  not_confirmed_count: number;
  mandatory_coverage: number | null;
  desired_coverage: number | null;
  resume_text: string | null;
  topics: ResultTopicRow[];
}

export async function getResultCard(
  token: string,
  candidateId: string,
  signal?: AbortSignal,
): Promise<ResultCard> {
  const response = await fetch(`${API_BASE_URL}/candidates/${candidateId}/result`, {
    headers: { Authorization: `Bearer ${token}` }, signal,
  });
  if (!response.ok) throw new Error("Не удалось загрузить карточку результата.");
  return response.json() as Promise<ResultCard>;
}

export interface UploadSession {
  id: string;
  video_chunks: number;
  audio_chunks: number;
  saved: boolean;
}
export interface SavedAnswer {
  id: string;
  question_id: string;
  duration_sec: number;
  processing_status: string;
}
export type TrackKind = "video" | "audio";

export class UploadRequestError extends Error {
  constructor(message: string, public retryable: boolean) { super(message); }
}

async function uploadRequest<T>(path: string, token: string, signal: AbortSignal, body: FormData | object): Promise<T> {
  let response: Response;
  const isFile = body instanceof FormData;
  try {
    response = await fetch(`${API_BASE_URL}/candidate-interview/${path}`, {
      method: isFile ? "PUT" : "POST", signal,
      headers: { Authorization: `Bearer ${token}`, ...(isFile ? {} : { "Content-Type": "application/json" }) },
      body: isFile ? body : JSON.stringify(body),
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new UploadRequestError("Нет связи с сервером. Запись пока не сохранена.", true);
  }
  if (!response.ok) throw new UploadRequestError(
    "Не удалось сохранить ответ. Проверьте соединение и приглашение.", response.status >= 500 || response.status === 429,
  );
  return response.json() as Promise<T>;
}

export const answerUploadApi = {
  start: (token: string, questionId: string, signal: AbortSignal, uploadId: string) =>
    uploadRequest<UploadSession>(`questions/${questionId}/uploads`, token, signal, { upload_id: uploadId }),
  chunk: (token: string, id: string, kind: TrackKind, index: number, blob: Blob, signal: AbortSignal) => {
    const form = new FormData(); form.append("file", blob, "chunk");
    return uploadRequest<{ index: number }>(`uploads/${id}/${kind}/${index}`, token, signal, form);
  },
  complete: (token: string, id: string, videoChunks: number, audioChunks: number, duration: number, signal: AbortSignal) =>
    uploadRequest<SavedAnswer>(`uploads/${id}/complete`, token, signal, {
      video_chunks: videoChunks, audio_chunks: audioChunks, duration_sec: duration,
    }),
};

export async function internalRequest<T>(path: string, token: string, signal?: AbortSignal, body?: object): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: body ? "POST" : "GET", signal,
    headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) throw new Error(response.status === 401 ? "Сессия истекла. Войдите снова." : "Не удалось загрузить данные. Повторите попытку.");
  return response.json() as Promise<T>;
}

export interface EvidenceItem {
  answer_id: string; question_id: string; question: string; quote: string;
  start_sec: number | null; end_sec: number | null; video_available: boolean;
}
export interface AnswerMedia { video_url: string; audio_url: string | null }
export const getEvidence = (token: string, candidate: string, topic: string, signal?: AbortSignal) =>
  internalRequest<EvidenceItem[]>(`/candidates/${candidate}/topics/${topic}/evidence`, token, signal);
export const getAnswerMedia = (token: string, candidate: string, answer: string, signal?: AbortSignal) =>
  internalRequest<AnswerMedia>(`/candidates/${candidate}/answers/${answer}/media`, token, signal);
export const recordVideoView = (token: string, candidate: string, answer: string, eventId: string, position: number) =>
  internalRequest(`/candidates/${candidate}/answers/${answer}/views`, token, undefined, { event_id: eventId, position_sec: position });
export async function internalLogin(username: string, password: string, role: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/token`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password, role }),
  });
  if (!response.ok) throw new Error("Не удалось войти. Проверьте данные.");
  return ((await response.json()) as { access_token: string }).access_token;
}
