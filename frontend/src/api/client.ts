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
  resultLink?: string,
): Promise<ResultCard> {
  const response = await fetch(`${API_BASE_URL}/candidates/${candidateId}/result`, {
    headers: { Authorization: `Bearer ${token}`, ...(resultLink ? { "X-Result-Link": resultLink } : {}) }, signal,
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

export async function internalRequest<T>(path: string, token: string, signal?: AbortSignal, body?: object, resultLink?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: body ? "POST" : "GET", signal,
    headers: { Authorization: `Bearer ${token}`, ...(resultLink ? { "X-Result-Link": resultLink } : {}), ...(body ? { "Content-Type": "application/json" } : {}) },
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
export const getEvidence = (token: string, candidate: string, topic: string, signal?: AbortSignal, resultLink?: string) =>
  internalRequest<EvidenceItem[]>(`/candidates/${candidate}/topics/${topic}/evidence`, token, signal, undefined, resultLink);
export const getAnswerMedia = (token: string, candidate: string, answer: string, signal?: AbortSignal, resultLink?: string) =>
  internalRequest<AnswerMedia>(`/candidates/${candidate}/answers/${answer}/media`, token, signal, undefined, resultLink);
export const recordVideoView = (token: string, candidate: string, answer: string, eventId: string, position: number, resultLink?: string) =>
  internalRequest(`/candidates/${candidate}/answers/${answer}/views`, token, undefined, { event_id: eventId, position_sec: position }, resultLink);
export async function internalLogin(username: string, password: string, role: string): Promise<string> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, role }),
    });
  } catch {
    throw new Error(
      "Нет связи с API. Проверьте, что backend запущен на VITE_API_BASE_URL и CORS разрешает этот origin.",
    );
  }
  if (!response.ok) {
    throw new Error("Не удалось войти. Логин — любой, пароль — INTERNAL_AUTH_PASSWORD из .env.");
  }
  return ((await response.json()) as { access_token: string }).access_token;
}

export interface MetricShare { count: number; total: number; share: number | null }
export interface ProductMetrics {
  system_statuses: Record<string, MetricShare>;
  current_statuses: Record<string, MetricShare>;
  reviewed_topics: number;
  changed_after_review: MetricShare;
  disputed_changed_after_review: MetricShare;
  review_directions: { from_status: string; to_status: string; count: number }[];
  completion: MetricShare;
  technical_failures: MetricShare;
}
export const getProductMetrics = (token: string, vacancyId?: string, signal?: AbortSignal) =>
  internalRequest<ProductMetrics>(`/metrics/product${vacancyId ? `?vacancy_id=${encodeURIComponent(vacancyId)}` : ""}`, token, signal);

export interface TranscriptAnswer {
  answer_id: string; question_id: string; topic_id: string; question: string;
  transcript: string | null; segments: { text: string; start: number; end: number }[];
  quotes: string[]; processing_status: string; skipped: boolean; technically_lost: boolean;
}
export const getTranscripts = (token: string, candidateId: string, topicId?: string, signal?: AbortSignal, resultLink?: string) =>
  internalRequest<TranscriptAnswer[]>(`/candidates/${candidateId}/transcript${topicId ? `?topic_id=${encodeURIComponent(topicId)}` : ""}`, token, signal, undefined, resultLink);

export interface InternalUser { username: string; role: "recruiter" | "technical_specialist" | "hiring_manager" }
export interface ReviewItem {
  assessment_id: string; candidate_id: string; topic_id: string; topic_title: string;
  skill_type: "hard" | "soft"; confidence: "low" | "medium" | "high";
  current_status: string; reasoning_summary: string | null;
}
export const getInternalUser = (token: string, signal?: AbortSignal) => internalRequest<InternalUser>("/auth/me", token, signal);
export const getReviewQueue = (token: string, signal?: AbortSignal) => internalRequest<ReviewItem[]>("/review-queue", token, signal);
export async function changeAssessmentStatus(token: string, assessmentId: string, status: string, comment: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/topic-assessments/${assessmentId}/status`, {
    method: "PATCH", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ new_status: status, comment: comment.trim() }),
  });
  if (!response.ok) throw new Error(response.status === 403 ? "Ваша роль не может изменить этот топик." : "Не удалось сохранить статус. Проверьте комментарий и повторите попытку.");
}

export interface ResultLinkInfo {
  id: string; candidate_id: string; created_by: string; expires_at: string; revoked_at: string | null;
}
export interface VideoViewItem {
  id: string; answer_id: string; viewer: string; role: string; position_sec: number; created_at: string;
}
export const createResultLink = (token: string, candidate: string) =>
  internalRequest<ResultLinkInfo & { token: string }>(`/candidates/${candidate}/result-links`, token, undefined, {});
export const listResultLinks = (token: string, candidate: string, signal?: AbortSignal) =>
  internalRequest<ResultLinkInfo[]>(`/candidates/${candidate}/result-links`, token, signal);
export const revokeResultLink = (token: string, id: string) =>
  internalRequest<ResultLinkInfo>(`/result-links/${id}/revoke`, token, undefined, {});
export const resolveResultLink = (token: string, link: string, signal?: AbortSignal) =>
  internalRequest<ResultLinkInfo>("/result-links/resolve", token, signal, { token: link });
export const getVideoViews = (token: string, candidate: string, signal?: AbortSignal) =>
  internalRequest<VideoViewItem[]>(`/candidates/${candidate}/video-views`, token, signal);

/* --- Vacancies (staff) --- */

export interface VacancyTopic {
  id: string;
  title: string;
  skill_type: "hard" | "soft";
  importance: "mandatory" | "desired";
  requirement_description: string | null;
  depth_expectations: string | null;
  verifiable_by_interview: boolean;
  order: number;
}

export interface Vacancy {
  id: string;
  lineage_id: string;
  title: string;
  grade: string;
  tasks: string | null;
  stop_factors: string[];
  specialist_profile: string | null;
  version: number;
  status: string;
  topics: VacancyTopic[];
}

export interface VacancyTopicWrite {
  title: string;
  skill_type: "hard" | "soft";
  importance: "mandatory" | "desired";
  requirement_description?: string | null;
  depth_expectations?: string | null;
  verifiable_by_interview?: boolean;
  order?: number;
}

export async function listVacancies(token: string, signal?: AbortSignal): Promise<Vacancy[]> {
  return internalRequest<Vacancy[]>("/vacancies", token, signal);
}

export async function getVacancy(token: string, id: string, signal?: AbortSignal): Promise<Vacancy> {
  return internalRequest<Vacancy>(`/vacancies/${id}`, token, signal);
}

export async function createVacancy(
  token: string,
  body: {
    title: string;
    grade: string;
    tasks?: string | null;
    stop_factors?: string[];
    specialist_profile?: string | null;
    topics: VacancyTopicWrite[];
  },
): Promise<Vacancy> {
  const response = await fetch(`${API_BASE_URL}/vacancies`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      response.status === 422
        ? `Не удалось создать вакансию: проверьте поля. ${detail.slice(0, 300)}`
        : detail || "Не удалось создать вакансию.",
    );
  }
  return response.json() as Promise<Vacancy>;
}

export async function generateCoreQuestions(token: string, vacancyId: string): Promise<{id: string; text: string}[]> {
  const response = await fetch(`${API_BASE_URL}/vacancies/${vacancyId}/core-questions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(
      detail
        ? `Не удалось сгенерировать вопросы: ${detail.slice(0, 300)}`
        : "Не удалось сгенерировать вопросы. Проверьте LLM-ключ.",
    );
  }
  return response.json() as Promise<{id: string; text: string}[]>;
}

export async function createCandidate(token: string, vacancyId: string, resumeText: string): Promise<{id: string}> {
  const response = await fetch(`${API_BASE_URL}/candidates`, {
    method: "POST", headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json"},
    body: JSON.stringify({vacancy_id: vacancyId, resume_text: resumeText || null}),
  });
  if (response.status === 409) throw new Error("Сначала откройте «Вакансии» и сгенерируйте Core-вопросы.");
  if (!response.ok) throw new Error("Не удалось создать кандидата. Проверьте роль и соединение.");
  return response.json() as Promise<{id: string}>;
}

export async function issueInterviewLink(
  token: string,
  candidateId: string,
): Promise<{ id: string; token: string; expires_at: string }> {
  const response = await fetch(`${API_BASE_URL}/candidates/${candidateId}/interview-link`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Не удалось выпустить ссылку интервью.");
  return response.json() as Promise<{ id: string; token: string; expires_at: string }>;
}
