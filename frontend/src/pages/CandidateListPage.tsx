import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  CandidateOverview,
  ResumeCard,
  createCandidate,
  deleteCandidate,
  draftResumeCard,
  issueInterviewLink,
  listCandidates,
} from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";
import {
  PROCESSING_LABEL,
  RECOMMENDATION_LABEL,
  STATUS_TONE,
  coveragePct,
  coverageText,
} from "../lib/labels";

type RecommendationFilter = "" | "fit" | "not_fit" | "additional_check" | "none";
type SortBasis = "mandatory" | "desired";
type SortKey = "coverage_desc" | "coverage_asc";

/** Целевое покрытие — по обязательным навыкам. */
function mandatoryOf(candidate: CandidateOverview): number | null {
  return candidate.mandatory_coverage ?? null;
}

/** Дополнительное покрытие — по желательным навыкам. */
function desiredOf(candidate: CandidateOverview): number | null {
  return candidate.desired_coverage ?? null;
}

function coverageBy(candidate: CandidateOverview, basis: SortBasis): number | null {
  return basis === "mandatory" ? mandatoryOf(candidate) : desiredOf(candidate);
}

export function CandidateListPage({ token, vacancyId }: { token: string; vacancyId: string }) {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState<CandidateOverview[] | null>(null);
  const [filter, setFilter] = useState("");
  const [recommendation, setRecommendation] = useState<RecommendationFilter>("");
  const [sort, setSort] = useState<SortKey>("coverage_desc");
  const [sortBasis, setSortBasis] = useState<SortBasis>("mandatory");
  const [error, setError] = useState("");
  const [linkInfo, setLinkInfo] = useState("");
  const [revision, setRevision] = useState(0);
  const [resume, setResume] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [card, setCard] = useState<ResumeCard["profile"] | null>(null);
  const [resumeNote, setResumeNote] = useState("");
  const [parsing, setParsing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState("");
  const recruiter = sessionStorage.getItem("internal-role") === "recruiter";

  useEffect(() => {
    const controller = new AbortController();
    setError("");
    listCandidates(token, vacancyId, controller.signal)
      .then(setCandidates)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, vacancyId, revision]);

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
      setSourceText(parsed.source_text ?? "");
      setResumeNote(
        parsed.parsed_by_model === false
          ? "Текст из PDF получен, модель не извлекла основное. Проверьте текст ниже."
          : `Из PDF извлечено основное: навыков ${parsed.profile.skills.length}, ` +
              `мест работы ${parsed.profile.experience.length}. Проверьте и поправьте.`,
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
      setSourceText("");
      setCard(null);
      setResumeNote("");
      setRevision((value) => value + 1);
    } catch (reason) {
      setLinkInfo(reason instanceof Error ? reason.message : "Не удалось создать кандидата.");
    } finally {
      setCreating(false);
    }
  }

  const visible = useMemo(() => {
    const rows = (candidates ?? []).filter((candidate) => {
      if (filter && candidate.processing_status !== filter) return false;
      if (recommendation === "none") return candidate.recommendation === null;
      if (recommendation && candidate.recommendation !== recommendation) return false;
      return true;
    });
    const ranked = [...rows].sort((left, right) => {
      const a = coverageBy(left, sortBasis);
      const b = coverageBy(right, sortBasis);
      if (a === null && b === null) return 0;
      if (a === null) return 1;
      if (b === null) return -1;
      return sort === "coverage_asc" ? a - b : b - a;
    });
    return ranked;
  }, [candidates, filter, recommendation, sort, sortBasis]);

  const summary = useMemo(() => {
    const rows = candidates ?? [];
    const scored = rows.map(mandatoryOf).filter((value): value is number => value !== null);
    const average = scored.length === 0 ? null : scored.reduce((sum, value) => sum + value, 0) / scored.length;
    return {
      total: rows.length,
      fit: rows.filter((c) => c.recommendation === "fit").length,
      notFit: rows.filter((c) => c.recommendation === "not_fit").length,
      check: rows.filter((c) => c.recommendation === "additional_check").length,
      average,
    };
  }, [candidates]);

  async function remove(candidateId: string) {
    if (!window.confirm("Удалить кандидата и его интервью?")) return;
    setBusyId(candidateId);
    setLinkInfo("");
    try {
      await deleteCandidate(token, candidateId);
      setCandidates((rows) => (rows ?? []).filter((row) => row.candidate_id !== candidateId));
    } catch (reason) {
      setLinkInfo(reason instanceof Error ? reason.message : "Не удалось удалить кандидата.");
    } finally {
      setBusyId("");
    }
  }

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
          <strong>{summary.fit}</strong>
          <span>Проходит</span>
        </div>
        <div className="summary-cell">
          <strong>{summary.notFit}</strong>
          <span>Не проходит</span>
        </div>
        <div className="summary-cell">
          <strong>{summary.check}</strong>
          <span>На проверке</span>
        </div>
        <div className="summary-cell">
          <strong>{coveragePct(summary.average)}</strong>
          <span>Среднее (обязательные)</span>
        </div>
      </div>

      <div className="filterbar" style={{ marginTop: 28 }}>
        <label>
          Обработка{" "}
          <select
            aria-label="Фильтр по статусу обработки"
            className="field"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="">Все</option>
            {Object.entries(PROCESSING_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Рекомендация{" "}
          <select
            aria-label="Фильтр по рекомендации"
            className="field"
            value={recommendation}
            onChange={(event) => setRecommendation(event.target.value as RecommendationFilter)}
          >
            <option value="">Все</option>
            <option value="fit">Проходит</option>
            <option value="not_fit">Не проходит</option>
            <option value="additional_check">На проверке</option>
            <option value="none">Ещё нет оценки</option>
          </select>
        </label>
        <label>
          Покрытие по{" "}
          <select
            aria-label="Основа покрытия для сортировки"
            className="field"
            value={sortBasis}
            onChange={(event) => setSortBasis(event.target.value as SortBasis)}
          >
            <option value="mandatory">обязательным</option>
            <option value="desired">желательным</option>
          </select>
        </label>
        <span className="spacer" />
        <Link className="btn ghost" to="/staff/vacancies/new">
          Новая вакансия
        </Link>
      </div>

      {recruiter && <section className="panel" style={{ marginTop: 20 }}>
        <label htmlFor="candidate-resume-pdf">Резюме в PDF (необязательно)</label>
        <p className="meta">
          Сначала считываем текст из PDF, затем модель извлекает основное — как у вакансии. Карточку
          и текст ниже можно поправить перед приглашением.
        </p>
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
        {parsing && <p role="status">Считываем текст и извлекаем основное…</p>}
        {!parsing && resumeNote && <p role="status">{resumeNote}</p>}
        {card && (card.full_name || card.headline || card.skills.length > 0) && (
          <div className="matrix" style={{ marginBottom: 16 }}>
            <section className="panel" aria-label="Извлечённое основное">
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
        {sourceText && (
          <details style={{ marginBottom: 16 }}>
            <summary className="meta">Текст из PDF</summary>
            <p style={{ whiteSpace: "pre-wrap" }}>{sourceText}</p>
          </details>
        )}
        <label htmlFor="candidate-resume">Основное из резюме (необязательно)</label>
        <textarea id="candidate-resume" value={resume} onChange={(event) => setResume(event.target.value)} />
        <button className="btn primary" disabled={creating || parsing} onClick={() => void invite()}>
          {creating ? "Создаём приглашение…" : "Пригласить кандидата"}
        </button>
      </section>}
      {linkInfo && <p className="activity-note" role="status">{linkInfo}</p>}

      {candidates === null ? (
        <p role="status">Загружаем кандидатов…</p>
      ) : visible.length === 0 ? (
        <EmptyState
          title={candidates.length === 0 ? "Кандидатов нет" : "Никто не попал в фильтр"}
          text={
            candidates.length === 0
              ? "Рекрутер может пригласить кандидата с помощью формы выше."
              : "Снимите фильтр по обработке или рекомендации."
          }
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Кандидат</th>
                <th>Обработка</th>
                <th aria-sort={sort === "coverage_asc" ? "ascending" : "descending"}>
                  <button
                    type="button"
                    className="btn small ghost"
                    aria-label="Сортировать по проценту покрытия"
                    onClick={() =>
                      setSort((value) => (value === "coverage_desc" ? "coverage_asc" : "coverage_desc"))
                    }
                  >
                    Покрытие · {sortBasis === "mandatory" ? "обяз." : "желат."}{" "}
                    {sort === "coverage_asc" ? "↑" : "↓"}
                  </button>
                </th>
                <th>Рекомендация</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visible.map((candidate) => (
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
                    <div className="title-cell">{coveragePct(mandatoryOf(candidate))}</div>
                    <div className="cell-sub">желательные: {coveragePct(desiredOf(candidate))}</div>
                    <div className="cell-sub">
                      {coverageText(
                        candidate.confirmed_count,
                        candidate.needs_check_count,
                        candidate.not_confirmed_count,
                      )}
                    </div>
                  </td>
                  <td>
                    {candidate.recommendation
                      ? RECOMMENDATION_LABEL[candidate.recommendation] ?? candidate.recommendation
                      : "—"}
                  </td>
                  <td className="inline">
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
                    {recruiter && (
                      <button
                        type="button"
                        className="btn small ghost"
                        disabled={busyId === candidate.candidate_id}
                        onClick={(event) => {
                          event.stopPropagation();
                          void remove(candidate.candidate_id);
                        }}
                      >
                        Удалить
                      </button>
                    )}
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
