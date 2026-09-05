import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { CandidateOverview, issueInterviewLink, listCandidates } from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";
import { PROCESSING_LABEL, RECOMMENDATION_LABEL, STATUS_TONE, coverageText } from "../lib/labels";

export function CandidateListPage({ token, vacancyId }: { token: string; vacancyId: string }) {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState<CandidateOverview[] | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [linkInfo, setLinkInfo] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setCandidates(null);
    listCandidates(token, vacancyId, filter || undefined, controller.signal)
      .then(setCandidates)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, vacancyId, filter]);

  const summary = useMemo(() => {
    const rows = candidates ?? [];
    return {
      total: rows.length,
      ready: rows.filter((c) => c.processing_status === "ready").length,
      error: rows.filter((c) => c.processing_status === "error").length,
      check: rows.reduce((sum, c) => sum + c.needs_check_count, 0),
    };
  }, [candidates]);

  async function copyLink(candidateId: string) {
    setLinkInfo("");
    try {
      const link = await issueInterviewLink(token, candidateId);
      const url = `${window.location.origin}/interview?token=${link.token}`;
      await navigator.clipboard.writeText(url);
      setLinkInfo(`Ссылка скопирована: ${url}`);
    } catch (reason) {
      setLinkInfo(reason instanceof Error ? reason.message : "Не удалось выпустить ссылку.");
    }
  }

  if (error) {
    return (
      <main>
        <p role="alert">{error}</p>
      </main>
    );
  }

  return (
    <main>
      <Breadcrumbs items={[{ label: "Команда", to: "/staff/overview" }, { label: "Кандидаты" }]} />
      <PageHead eyebrow="Рекрутер" title="Кандидаты" />

      <div className="summary-strip" aria-label="Сводка">
        <div className="summary-cell">
          <strong>{summary.total}</strong>
          <span>Всего</span>
        </div>
        <div className="summary-cell">
          <strong>{summary.ready}</strong>
          <span>Готово</span>
        </div>
        <div className="summary-cell">
          <strong>{summary.check}</strong>
          <span>Топиков к проверке</span>
        </div>
        <div className="summary-cell">
          <strong>{summary.error}</strong>
          <span>Ошибки обработки</span>
        </div>
      </div>

      <div className="filterbar" style={{ marginTop: 28 }}>
        <label>
          Фильтр по статусу:{" "}
          <select className="field" value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="">Все</option>
            {Object.entries(PROCESSING_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <span className="spacer" />
        <Link className="btn ghost" to="/staff/vacancies/new">
          Новая вакансия
        </Link>
      </div>

      {linkInfo && <p className="activity-note">{linkInfo}</p>}

      {candidates === null ? (
        <p role="status">Загружаем кандидатов…</p>
      ) : candidates.length === 0 ? (
        <EmptyState
          title="Кандидатов нет"
          text="Создайте кандидата в БД и выпустите ссылку, либо дождитесь приглашений."
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Кандидат</th>
                <th>Обработка</th>
                <th>Покрытие</th>
                <th>Рекомендация</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr
                  key={candidate.candidate_id}
                  className="clickable"
                  data-testid="candidate-row"
                  data-error={candidate.processing_status === "error" ? "true" : undefined}
                  onClick={() => navigate(`/staff/candidates/${candidate.candidate_id}`)}
                >
                  <td>
                    <div className="title-cell">{candidate.candidate_id.slice(0, 8)}…</div>
                    <div className="cell-sub">{candidate.candidate_status}</div>
                  </td>
                  <td>
                    <StatusPill tone={STATUS_TONE[candidate.processing_status]}>
                      {PROCESSING_LABEL[candidate.processing_status] ?? candidate.processing_status}
                    </StatusPill>
                    {candidate.processing_status === "error" && (
                      <strong role="alert"> · требует внимания</strong>
                    )}
                  </td>
                  <td>
                    {coverageText(
                      candidate.confirmed_count,
                      candidate.needs_check_count,
                      candidate.not_confirmed_count,
                    )}
                  </td>
                  <td>
                    {candidate.recommendation
                      ? RECOMMENDATION_LABEL[candidate.recommendation] ?? candidate.recommendation
                      : "—"}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn small ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        void copyLink(candidate.candidate_id);
                      }}
                    >
                      Ссылка
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
