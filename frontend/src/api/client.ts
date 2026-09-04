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
