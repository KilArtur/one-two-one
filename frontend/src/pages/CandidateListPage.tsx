import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  CandidateOverview,
  ResumeCard,
  createCandidate,
  draftResumeCard,
  issueInterviewLink,
  listCandidates,
} from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";
import { PROCESSING_LABEL, RECOMMENDATION_LABEL, STATUS_TONE, coverageText } from "../lib/labels";

export function CandidateListPage({ token, vacancyId }: { token: string; vacancyId: string }) {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState<CandidateOverview[] | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [linkInfo, setLinkInfo] = useState("");
  const [revision, setRevision] = useState(0);
  const [resume, setResume] = useState("");
  const [card, setCard] = useState<ResumeCard["profile"] | null>(null);
  const [resumeNote, setResumeNote] = useState("");
  const [parsing, setParsing] = useState(false);
  const [creating, setCreating] = useState(false);
  const recruiter = sessionStorage.getItem("internal-role") === "recruiter";

  useEffect(() => {
    const controller = new AbortController();
    setError("");
    listCandidates(token, vacancyId, filter || undefined, controller.signal)
      .then(setCandidates)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, vacancyId, filter, revision]);

  useEffect(() => {
    const timer = window.setInterval(() => setRevision((value) => value + 1), 5000);
    return () => window.clearInterval(timer);
  }, []);

  async function loadResume(file: File) {
    setParsing(true);
    setResumeNote("");
    try {
      const parsed = await draftResumeCard(token, file);
      setCard(parsed.profile);
      setResume(parsed.resume_text);
      setResumeNote(
        `Резюме разобрано: навыков ${parsed.profile.skills.length}, ` +
          `мест работы ${parsed.profile.experience.length}.`,
      );
    } catch (reason) {
      setResumeNote(reason instanceof Error ? reason.message : "Не удалось разобрать резюме.");
    } finally {
      setParsing(false);
    }
  }

  async function invite() {
    setCreating(true);
    try {
      const candidate = await createCandidate(token, vacancyId, resume);
      await copyLink(candidate.id);
      setResume("");
      setCard(null);
      setResumeNote("");
      setRevision((value) => value + 1);
    } catch (reason) {
      setLinkInfo(reason instanceof Error ? reason.message : "Не удалось создать кандидата.");
    } finally {
      setCreating(false);
    }
  }

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
      setLinkInfo("Ссылка на интервью скопирована.");
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

      {recruiter && <section className="panel" style={{ marginTop: 20 }}>
        <label htmlFor="candidate-resume-pdf">Резюме в PDF (необязательно)</label>
        <input
          id="candidate-resume-pdf"
          type="file"
          accept="application/pdf"
          disabled={parsing}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void loadResume(file);
          }}
        />
        <p className="meta">
          Из файла соберётся карточка кандидата — навыки, опыт и образование. Текст ниже можно
          поправить перед приглашением.
        </p>
        {parsing && <p role="status">Разбираем резюме…</p>}
        {!parsing && resumeNote && <p role="status">{resumeNote}</p>}
        {card && (
          <div className="matrix" style={{ marginBottom: 16 }}>
            <section className="panel">
              <div className="title-cell">{card.full_name || "Кандидат"}</div>
              {card.headline && <p className="meta">{card.headline}</p>}
              {card.skills.length > 0 && (
                <>
                  <p className="meta">Навыки</p>
                  <p>{card.skills.join(" · ")}</p>
                </>
              )}
              {card.experience.length > 0 && (
                <>
                  <p className="meta">Опыт</p>
                  <ul>
                    {card.experience.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </>
              )}
              {card.education.length > 0 && (
                <>
                  <p className="meta">Образование</p>
                  <ul>
                    {card.education.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          </div>
        )}
        <label htmlFor="candidate-resume">Резюме кандидата (необязательно)</label>
        <textarea id="candidate-resume" value={resume} onChange={(event) => setResume(event.target.value)} />
        <button className="btn primary" disabled={creating || parsing} onClick={() => void invite()}>
          {creating ? "Создаём приглашение…" : "Пригласить кандидата"}
        </button>
      </section>}
      {linkInfo && <p className="activity-note" role="status">{linkInfo}</p>}

      {candidates === null ? (
        <p role="status">Загружаем кандидатов…</p>
      ) : candidates.length === 0 ? (
        <EmptyState
          title="Кандидатов нет"
          text="Рекрутер может пригласить кандидата с помощью формы выше."
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
