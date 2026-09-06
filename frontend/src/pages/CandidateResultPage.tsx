import { ResultAccessPanel } from "../components/ResultAccessPanel";
import { ResultLinkContext } from "../components/ResultLinkContext";
import { useContext, useEffect, useMemo, useState } from "react";

import {
  ResultTopicRow,
  changeTopicStatus,
  deleteCandidate,
  getResultCard,
  ResultCard,
} from "../api/client";
import { useNavigate } from "react-router-dom";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { EvidencePanel } from "../components/EvidencePanel";
import { Breadcrumbs, StatusPill } from "../layouts/Shell";
import {
  AUTHOR_LABEL,
  REASON_LABEL,
  RECOMMENDATION_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  coveragePct,
  coverageText,
} from "../lib/labels";
import { candidateCode } from "../lib/candidateCode";

type TopicDraft = { status: string; comment: string };

function canEditTopic(shared: boolean, skillType: string): boolean {
  if (shared) return false;
  const role = sessionStorage.getItem("internal-role");
  if (role === "technical_specialist") return skillType === "hard";
  if (role === "hiring_manager") return skillType === "soft";
  return false;
}

function TopicStatusEditor({
  topic,
  draft,
  busy,
  onChange,
  onSave,
}: {
  topic: ResultTopicRow;
  draft: TopicDraft;
  busy: boolean;
  onChange: (next: TopicDraft) => void;
  onSave: () => void;
}) {
  return (
    <div className="topic-edit">
      <label>
        <span className="meta">Статус</span>
        <select
          className="field"
          aria-label={`Статус топика ${topic.topic_title}`}
          value={draft.status}
          disabled={busy}
          onChange={(event) => onChange({ ...draft, status: event.target.value })}
        >
          <option value="confirmed">подтверждено</option>
          <option value="needs_check">требует проверки</option>
          <option value="not_confirmed">не подтверждено</option>
        </select>
      </label>
      <label>
        <span className="meta">Комментарий</span>
        <input
          className="field"
          aria-label={`Комментарий к статусу ${topic.topic_title}`}
          maxLength={2000}
          value={draft.comment}
          disabled={busy}
          placeholder="Комментарий (необязательно)"
          onChange={(event) => onChange({ ...draft, comment: event.target.value })}
        />
      </label>
      <button type="button" className="btn small" disabled={busy} onClick={onSave}>
        {busy ? "Сохраняем…" : "Сохранить"}
      </button>
    </div>
  );
}

function isDirty(topic: ResultTopicRow, draft: TopicDraft | undefined): boolean {
  if (!draft) return false;
  return draft.status !== topic.current_status || draft.comment.trim().length > 0;
}

export function CandidateResultPage({
  token,
  candidateId,
  shared = false,
}: {
  token: string;
  candidateId: string;
  shared?: boolean;
}) {
  const navigate = useNavigate();
  const resultLink = useContext(ResultLinkContext);
  const recruiter = !shared && sessionStorage.getItem("internal-role") === "recruiter";
  const [access, setAccess] = useState(false);
  const [card, setCard] = useState<ResultCard | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [topic, setTopic] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, TopicDraft>>({});
  const [savingIds, setSavingIds] = useState<string[]>([]);
  const [saveError, setSaveError] = useState("");
  const [saveNotice, setSaveNotice] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getResultCard(token, candidateId, controller.signal, resultLink)
      .then(setCard)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, candidateId, resultLink, revision]);

  useEffect(() => {
    if (!card) return;
    setDrafts(
      Object.fromEntries(
        card.topics.map((row) => [row.topic_id, { status: row.current_status, comment: "" }]),
      ),
    );
    setSaveError("");
    setSaveNotice("");
  }, [card]);

  const editableTopics = useMemo(
    () => (card ? card.topics.filter((row) => canEditTopic(shared, row.skill_type)) : []),
    [card, shared],
  );
  const dirtyIds = useMemo(
    () =>
      editableTopics
        .filter((row) => isDirty(row, drafts[row.topic_id]))
        .map((row) => row.topic_id),
    [editableTopics, drafts],
  );
  const saving = savingIds.length > 0;

  async function saveTopics(topicIds: string[]) {
    if (!card || topicIds.length === 0 || saving) return;
    setSavingIds(topicIds);
    setSaveError("");
    setSaveNotice("");
    try {
      for (const topicId of topicIds) {
        const row = card.topics.find((item) => item.topic_id === topicId);
        const draft = drafts[topicId];
        if (!row || !draft) continue;
        await changeTopicStatus(token, candidateId, topicId, draft.status, draft.comment);
      }
      setSaveNotice(
        topicIds.length === 1 ? "Статус сохранён." : `Сохранено топиков: ${topicIds.length}.`,
      );
      setRevision((value) => value + 1);
    } catch (reason) {
      setSaveError(reason instanceof Error ? reason.message : "Не удалось сохранить статусы.");
    } finally {
      setSavingIds([]);
    }
  }

  async function remove() {
    if (!window.confirm("Удалить кандидата и его интервью?")) return;
    setBusy(true);
    try {
      await deleteCandidate(token, candidateId);
      navigate("/staff/candidates");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось удалить кандидата.");
      setBusy(false);
    }
  }

  if (error) {
    return (
      <main>
        <p role="alert">{error}</p>
      </main>
    );
  }
  if (!card) return <p role="status">Загружаем карточку…</p>;

  return (
    <main>
      {!shared && (
        <Breadcrumbs
          items={[
            { label: "Кандидаты", to: "/staff/candidates" },
            { label: "Результат" },
          ]}
        />
      )}

      <div className="result-hero">
        <p className="eyebrow" style={{ color: "#9d99ff" }}>
          {candidateCode(card.candidate_id)}
        </p>
        <h1>{RECOMMENDATION_LABEL[card.recommendation] ?? card.recommendation}</h1>
        <p>{REASON_LABEL[card.recommendation_reason] ?? card.recommendation_reason}.</p>
      </div>

      <div className="metric-strip metric-strip-coverage" aria-label="Покрытие">
        <div className="metric recommendation">
          <span className="label">Рекомендация</span>
          <span className="value">{RECOMMENDATION_LABEL[card.recommendation] ?? card.recommendation}</span>
          <span className="detail">{REASON_LABEL[card.recommendation_reason] ?? card.recommendation_reason}</span>
        </div>
        <div className="metric">
          <span className="label">Обязательные</span>
          <span className="value">
            {coveragePct(card.mandatory_confirmed_share ?? card.mandatory_coverage)}
          </span>
          <span className="detail">подтверждено / все обязательные</span>
        </div>
        <div className="metric">
          <span className="label">Желательные</span>
          <span className="value">
            {coveragePct(card.desired_confirmed_share ?? card.desired_coverage, "нет")}
          </span>
          <span className="detail">
            {(card.desired_confirmed_share ?? card.desired_coverage) === null
              ? "желательных топиков нет"
              : "подтверждено / все желательные"}
          </span>
        </div>
        <div className="metric">
          <span className="label">Потенциал обяз.</span>
          <span className="value">{coveragePct(card.mandatory_potential_share ?? null)}</span>
          <span className="detail">
            подтв. + проверка ·{" "}
            {coverageText(card.confirmed_count, card.needs_check_count, card.not_confirmed_count)}
          </span>
        </div>
      </div>

      <section className="section" aria-label="Матрица топиков">
        <div className="section-head">
          <h2>Матрица требований (подтверждено в интервью)</h2>
          <div className="inline">
            {editableTopics.length > 0 && (
              <button
                type="button"
                className="btn primary"
                disabled={saving || dirtyIds.length === 0}
                onClick={() => void saveTopics(dirtyIds)}
              >
                {saving && savingIds.length > 1 ? "Сохраняем всё…" : "Сохранить всё"}
              </button>
            )}
            {recruiter && (
              <button type="button" className="btn small ghost" disabled={busy} onClick={() => void remove()}>
                Удалить кандидата
              </button>
            )}
          </div>
        </div>
        {saveError && <p role="alert">{saveError}</p>}
        {saveNotice && <p role="status">{saveNotice}</p>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Топик</th>
                <th>Тип</th>
                <th>Важность</th>
                <th>Статус</th>
                <th>Автор</th>
                <th>Правка</th>
              </tr>
            </thead>
            <tbody>
              {card.topics.map((row) => (
                <tr key={row.topic_id} data-testid="topic-row">
                  <td className="title-cell">{row.topic_title}</td>
                  <td>{row.skill_type === "hard" ? "hard" : "soft"}</td>
                  <td>{row.importance === "mandatory" ? "обязательный" : "желательный"}</td>
                  <td>
                    <div className="topic-status-cell">
                      <StatusPill tone={STATUS_TONE[row.current_status]}>
                        {STATUS_LABEL[row.current_status] ?? row.current_status}
                      </StatusPill>
                      {(row.reviewable ?? row.has_evidence) && (
                        <button
                          type="button"
                          className="btn small ghost"
                          onClick={() => setTopic(row.topic_id)}
                        >
                          {row.has_evidence ? "Цитата и видео" : "Видео и транскрипт"}
                        </button>
                      )}
                    </div>
                  </td>
                  <td>{AUTHOR_LABEL[row.author] ?? row.author}</td>
                  <td>
                    {canEditTopic(shared, row.skill_type) && drafts[row.topic_id] ? (
                      <TopicStatusEditor
                        topic={row}
                        draft={drafts[row.topic_id]}
                        busy={saving}
                        onChange={(next) =>
                          setDrafts((current) => ({ ...current, [row.topic_id]: next }))
                        }
                        onSave={() => void saveTopics([row.topic_id])}
                      />
                    ) : (
                      <span className="meta">
                        {shared || recruiter
                          ? "Только эксперт"
                          : row.skill_type === "hard"
                            ? "Hard — техспециалист"
                            : "Soft — нанимающий менеджер"}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="meta" style={{ marginTop: 12 }}>
          Покрытие:{" "}
          {coverageText(card.confirmed_count, card.needs_check_count, card.not_confirmed_count)}
          {" · "}
          обяз. {coveragePct(card.mandatory_confirmed_share ?? card.mandatory_coverage)}
          {" · "}
          желат. {coveragePct(card.desired_confirmed_share ?? card.desired_coverage, "нет")}
          {" · "}
          потенциал обяз. {coveragePct(card.mandatory_potential_share ?? null)}
        </p>
      </section>

      <section className="section" aria-label="Рекомендация">
        <div className="section-head">
          <h2>Итоговая рекомендация</h2>
        </div>
        <div className="feedback-box">
          <p>
            <strong>{RECOMMENDATION_LABEL[card.recommendation] ?? card.recommendation}</strong>
          </p>
          <p>{REASON_LABEL[card.recommendation_reason] ?? card.recommendation_reason}.</p>
        </div>
      </section>

      {topic && (
        <div key={topic}>
          {card.topics.find((row) => row.topic_id === topic)?.has_evidence && (
            <EvidencePanel token={token} candidateId={candidateId} topicId={topic} />
          )}
          <TranscriptPanel token={token} candidateId={candidateId} topicId={topic} />
        </div>
      )}

      <button
        type="button"
        className="btn ghost"
        aria-expanded={showTranscript}
        onClick={() => setShowTranscript((v) => !v)}
      >
        {showTranscript ? "Скрыть транскрипт" : "Открыть полный транскрипт"}
      </button>
      {showTranscript && <TranscriptPanel token={token} candidateId={candidateId} />}

      {!shared && (
        <>
          <button type="button" className="btn ghost" style={{ marginLeft: 8 }} onClick={() => setAccess((v) => !v)}>
            Ссылки и журнал просмотров
          </button>
          {access && <ResultAccessPanel token={token} candidateId={candidateId} />}
        </>
      )}

    </main>
  );
}
