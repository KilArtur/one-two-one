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
