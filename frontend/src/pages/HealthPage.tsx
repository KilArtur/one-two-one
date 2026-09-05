import { useState } from "react";

import { apiClient, type HealthResponse } from "../api/client";

export function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await apiClient.getHealth());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Неизвестная ошибка");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main>
      <h1>Статус системы</h1>
      <button onClick={checkHealth} disabled={loading}>
        {loading ? "Запрос..." : "Проверить /health"}
      </button>
      {health && (
        <p data-testid="health-status">
          status: {health.status} · env: {health.app_env} · version: {health.version}
        </p>
      )}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
