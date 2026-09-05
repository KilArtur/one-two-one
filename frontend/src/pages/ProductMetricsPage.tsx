import { useEffect, useState } from "react";
import { getProductMetrics, MetricShare, ProductMetrics } from "../api/client";

const labels: Record<string, string> = {
  confirmed: "✅ подтверждено", needs_check: "❓ требует проверки", not_confirmed: "❌ не подтверждено",
};
function share(value: MetricShare): string {
  return value.share === null ? "Нет данных (0 / 0)" : `${(value.share * 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}% (${value.count} / ${value.total})`;
}
export function ProductMetricsPage({ token, vacancyId }: { token: string; vacancyId?: string }) {
  const [metrics, setMetrics] = useState<ProductMetrics | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError("");
    getProductMetrics(token, vacancyId, controller.signal).then((data) => {
      if (!controller.signal.aborted) setMetrics(data);
    }).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Метрики недоступны.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [token, vacancyId, refresh]);
  return <main>
    <h1>Продуктовые метрики</h1>
    <p>{vacancyId ? "По выбранной вакансии" : "По всем вакансиям"} · текущее состояние за всё время.</p>
    <button disabled={loading} onClick={() => setRefresh((v) => v + 1)}>Обновить метрики</button>
    {loading && <p role="status">Обновляем метрики…</p>}
    {error && <p role="alert">{error}</p>}
    {metrics && <>
      <section aria-label="Доли статусов"><h2>Покрытие требований</h2>
        <table style={{ width: "100%", borderSpacing: "12px 8px", textAlign: "left" }}><thead><tr><th>Статус</th><th>Исходный статус системы</th><th>Текущий статус</th></tr></thead>
          <tbody>{Object.entries(labels).map(([status, label]) => <tr key={status}>
            <th>{label}</th><td>{share(metrics.system_statuses[status])}</td><td>{share(metrics.current_statuses[status])}</td>
          </tr>)}</tbody></table>
        <p>Доли среди оценённых топиков. Топики вне зоны интервью исключены. Исходный статус системы сохраняется после ревью.</p>
      </section>
      <section aria-label="Результаты ревью"><h2>Ревью</h2>
        <p>Топиков с ревью: {metrics.reviewed_topics}</p>
        <p>Итоговый статус изменён среди прошедших ревью: <strong>{share(metrics.changed_after_review)}</strong></p>
        <p>Исходно спорные топики с изменённым статусом: <strong>{share(metrics.disputed_changed_after_review)}</strong></p>
        <p>Каждый топик учитывается один раз. Направление — от исходного системного статуса к текущему; возврат к исходному не считается изменением.</p>
        {metrics.review_directions.length ? <ul>{metrics.review_directions.map((d) =>
          <li key={`${d.from_status}-${d.to_status}`}>{labels[d.from_status]} → {labels[d.to_status]}: {d.count}</li>)}</ul>
          : <p>Итоговых изменений после ревью пока нет.</p>}
      </section>
      <section aria-label="Прохождение интервью"><h2>Прохождение интервью</h2>
        <p>Завершены: <strong>{share(metrics.completion)}</strong></p>
        <p>С техническими сбоями: <strong>{share(metrics.technical_failures)}</strong></p>
        <p>Знаменатель — начатые интервью; приглашённые, ещё не начавшие интервью, исключены.
          Завершение — отправка интервью. Сбой — хотя бы один технически потерянный ответ или ошибка обработки;
          несколько сбоев одного кандидата учитываются один раз. Завершённое интервью тоже может содержать сбой.</p>
      </section>
    </>}
  </main>;
}
