import { useEffect, useState } from "react";
import { getProductMetrics, MetricShare, ProductMetrics } from "../api/client";
import { Breadcrumbs, PageHead } from "../layouts/Shell";
import { pct } from "../lib/labels";

const labels: Record<string, string> = {
  confirmed: "подтверждено",
  needs_check: "требует проверки",
  not_confirmed: "не подтверждено",
};

function share(value: MetricShare): string {
  return pct(value.share, value.count, value.total);
}

export function ProductMetricsPage({ token, vacancyId }: { token: string; vacancyId?: string }) {
  const [metrics, setMetrics] = useState<ProductMetrics | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    getProductMetrics(token, vacancyId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setMetrics(data);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Метрики недоступны.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, vacancyId, refresh]);

  return (
    <main>
      <Breadcrumbs items={[{ label: "Команда", to: "/staff/overview" }, { label: "Метрики" }]} />
      <PageHead
        eyebrow="Раздел 11.2"
        title="Метрики"
        actions={
          <button
            type="button"
            className="btn primary"
            disabled={loading}
            onClick={() => setRefresh((v) => v + 1)}
          >
            Обновить метрики
          </button>
        }
      />

      {loading && <p role="status">Обновляем метрики…</p>}
      {error && <p role="alert">{error}</p>}

      {metrics && (
        <>
          <section className="section" aria-label="Доли статусов">
            <div className="section-head">
              <h2>Покрытие требований</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Статус</th>
                    <th scope="col">Исходный статус системы</th>
                    <th>Текущий статус</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(labels).map(([status, label]) => (
                    <tr key={status}>
                      <th scope="row">{label}</th>
                      <td>{share(metrics.system_statuses[status])}</td>
                      <td>{share(metrics.current_statuses[status])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="meta">
              Доли среди оценённых топиков. Топики вне зоны интервью исключены. Исходный статус системы
              сохраняется после ревью.
            </p>
          </section>

          <section className="section" aria-label="Результаты ревью">
            <div className="section-head">
              <h2>Ревью</h2>
            </div>
            <div className="summary-strip">
              <div className="summary-cell">
                <strong>{metrics.reviewed_topics}</strong>
                <span>Топиков с ревью: {metrics.reviewed_topics}</span>
              </div>
              <div className="summary-cell">
                <strong>{share(metrics.changed_after_review)}</strong>
                <span>Итоговый статус изменён среди прошедших ревью</span>
              </div>
              <div className="summary-cell">
                <strong>{share(metrics.disputed_changed_after_review)}</strong>
                <span>Исходно спорные с изменённым статусом</span>
              </div>
              <div className="summary-cell">
                <strong>{metrics.review_directions.length}</strong>
                <span>Направлений изменений</span>
              </div>
            </div>
            <p className="meta">
              Каждый топик учитывается один раз. Направление — от исходного системного статуса к
              текущему; возврат к исходному не считается изменением.
            </p>
            {metrics.review_directions.length ? (
              <ul>
                {metrics.review_directions.map((d) => (
                  <li key={`${d.from_status}-${d.to_status}`}>
                    {labels[d.from_status]} → {labels[d.to_status]}: {d.count}
                  </li>
                ))}
              </ul>
            ) : (
              <p>Итоговых изменений после ревью пока нет.</p>
            )}
          </section>

          <section className="section" aria-label="Прохождение интервью">
            <div className="section-head">
              <h2>Прохождение интервью</h2>
            </div>
            <p>
              Завершены: <strong>{share(metrics.completion)}</strong>
            </p>
            <p>
              С техническими сбоями: <strong>{share(metrics.technical_failures)}</strong>
            </p>
            <p className="meta">
              Знаменатель — начатые интервью; приглашённые, ещё не начавшие интервью, исключены.
              Завершение — отправка интервью. Сбой — хотя бы один технически потерянный ответ или ошибка
              обработки; несколько сбоев одного кандидата учитываются один раз. Завершённое интервью тоже
              может содержать сбой.
            </p>
          </section>
        </>
      )}
    </main>
  );
}
