import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  changeAssessmentStatus,
  getInternalUser,
  getReviewQueue,
  InternalUser,
  ReviewItem,
} from "../api/client";
import { EvidencePanel } from "../components/EvidencePanel";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";
import { candidateCode } from "../lib/candidateCode";
import { STATUS_TONE } from "../lib/labels";
import { CandidateResultPage } from "./CandidateResultPage";

function ReviewDetail({
  token,
  item,
  onSaved,
}: {
  token: string;
  item: ReviewItem;
  onSaved: () => void;
}) {
  const [status, setStatus] = useState(item.current_status);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const code = candidateCode(item.candidate_id);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await changeAssessmentStatus(token, item.assessment_id, status, comment);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ошибка сохранения.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-label="Контекст ревью">
      <p className="eyebrow">{code}</p>
      <h2>{item.topic_title}</h2>
      <p className="meta">
        Кандидат {code} · {item.skill_type}
        {" · "}
        <Link to={`/staff/candidates/${item.candidate_id}`}>Открыть карточку</Link>
      </p>
      <h3>Причина неопределённости</h3>
      <p>{item.reasoning_summary ?? "Причина не указана. Проверьте ответ и запись."}</p>
      <TranscriptPanel token={token} candidateId={item.candidate_id} topicId={item.topic_id} />
      <EvidencePanel token={token} candidateId={item.candidate_id} topicId={item.topic_id} />
      <form className="review-status-form" onSubmit={(event) => void save(event)}>
        <h3>Результат проверки топика</h3>
        <label className="form-group">
          <span>Новый статус</span>
          <select
            className="field"
            value={status}
            disabled={busy}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="confirmed">подтверждено</option>
            <option value="needs_check">требует проверки</option>
            <option value="not_confirmed">не подтверждено</option>
          </select>
        </label>
        <label className="form-group">
          <span>Комментарий эксперта (необязательно)</span>
          <textarea
            maxLength={2000}
            value={comment}
            disabled={busy}
            onChange={(event) => setComment(event.target.value)}
            rows={4}
          />
        </label>
        <p className="meta">
          Правка изменяет текущий статус. Исходный статус системы и история сохраняются.
        </p>
        <button className="btn primary" disabled={busy}>
          {busy ? "Сохраняем…" : "Сохранить статус"}
        </button>
        {error && <p role="alert">{error}</p>}
      </form>
    </section>
  );
}

export function ReviewQueuePage({ token }: { token: string }) {
  const [user, setUser] = useState<InternalUser | null>(null);
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [confirmCandidate, setConfirmCandidate] = useState<string | null>(null);
  const [savedCandidate, setSavedCandidate] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setItems(null);
    async function load() {
      const current = await getInternalUser(token, controller.signal);
      if (controller.signal.aborted) return;
      setUser(current);
      if (current.role === "recruiter") return;
      const queue = await getReviewQueue(token, controller.signal);
      if (!controller.signal.aborted) setItems(queue);
    }
    void load().catch((reason) => {
      if (!controller.signal.aborted) {
        setError(reason instanceof Error ? reason.message : "Очередь недоступна.");
      }
    });
    return () => controller.abort();
  }, [token, revision]);

  const groups = useMemo(() => {
    const map = new Map<string, ReviewItem[]>();
    for (const item of items ?? []) {
      const rows = map.get(item.candidate_id) ?? [];
      rows.push(item);
      map.set(item.candidate_id, rows);
    }
    return [...map.entries()];
  }, [items]);

  function openConfirm(candidateId: string) {
    setConfirmCandidate(candidateId);
    setSelected(null);
    setSavedCandidate(null);
  }

  if (confirmCandidate) {
    const code = candidateCode(confirmCandidate);
    return (
      <main>
        <Breadcrumbs items={[{ label: "Команда", to: "/staff/overview" }, { label: "Ревью" }]} />
        <PageHead
          eyebrow="Подтверждение кандидата"
          title={code}
          actions={
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                setConfirmCandidate(null);
                setRevision((value) => value + 1);
              }}
            >
              К очереди
            </button>
          }
        />
        <p className="meta" style={{ marginBottom: 24 }}>
          Отметьте статусы в матрице и нажмите «Сохранить всё».
        </p>
        <CandidateResultPage
          key={`${confirmCandidate}-${revision}`}
          token={token}
          candidateId={confirmCandidate}
        />
      </main>
    );
  }

  return (
    <main>
      <Breadcrumbs items={[{ label: "Команда", to: "/staff/overview" }, { label: "Ревью" }]} />
      <PageHead eyebrow="Экспертная проверка" title="Очередь ревью" />

      {error && (
        <>
          <p role="alert">{error}</p>
          <button type="button" className="btn ghost" onClick={() => setRevision((v) => v + 1)}>
            Повторить загрузку очереди
          </button>
        </>
      )}

      {user?.role === "recruiter" ? (
        <div className="panel">
          <p>
            Рекрутер не меняет статусы. Hard-топики проверяет техспециалист, soft-топики — нанимающий
            менеджер.
          </p>
        </div>
      ) : (
        <>
          {user && (
            <p className="meta">
              {user.role === "technical_specialist"
                ? "Hard-топики · техспециалист"
                : "Soft-топики · нанимающий менеджер"}
            </p>
          )}
          {!items && !error && <p role="status">Загружаем очередь…</p>}
          {items && (
            <>
              <button
                type="button"
                className="btn ghost"
                onClick={() => {
                  setSelected(null);
                  setRevision((v) => v + 1);
                }}
              >
                Обновить очередь
              </button>
              {items.length ? (
                <div className="requirement-layout" style={{ marginTop: 24 }}>
                  <div className="requirement-list review-queue-list">
                    {groups.map(([candidateId, topics]) => {
                      const code = candidateCode(candidateId);
                      return (
                        <section
                          key={candidateId}
                          className="review-candidate-group"
                          aria-label={`Кандидат ${code}`}
                        >
                          <div className="review-candidate-head">
                            <button
                              type="button"
                              className="review-candidate-code"
                              onClick={() => openConfirm(candidateId)}
                            >
                              {code}
                            </button>
                            <span className="meta">
                              {topics.length}{" "}
                              {topics.length === 1 ? "топик" : topics.length < 5 ? "топика" : "топиков"}
                            </span>
                            <button
                              type="button"
                              className="btn small primary"
                              onClick={() => openConfirm(candidateId)}
                            >
                              Подтвердить
                            </button>
                          </div>
                          {topics.map((item) => (
                            <button
                              key={item.assessment_id}
                              type="button"
                              className={`requirement${selected?.assessment_id === item.assessment_id ? " active" : ""}`}
                              aria-label={`${code}: ${item.topic_title} · ${item.skill_type}`}
                              aria-pressed={selected?.assessment_id === item.assessment_id}
                              onClick={() => {
                                setSelected(item);
                                setSavedCandidate(null);
                              }}
                            >
                              <strong>
                                {item.topic_title} · {item.skill_type}
                              </strong>
                              <p>{item.reasoning_summary ?? "Требует проверки"}</p>
                              <StatusPill tone={STATUS_TONE.needs_check}>требует проверки</StatusPill>
                            </button>
                          ))}
                        </section>
                      );
                    })}
                  </div>
                  <div>
                    {selected ? (
                      <ReviewDetail
                        key={selected.assessment_id}
                        token={token}
                        item={selected}
                        onSaved={() => {
                          setSavedCandidate(selected.candidate_id);
                          setSelected(null);
                          setRevision((v) => v + 1);
                        }}
                      />
                    ) : (
                      <EmptyState
                        title="Выберите топик или кандидата"
                        text="Топик — точечная проверка. «Подтвердить» открывает матрицу кандидата."
                      />
                    )}
                  </div>
                </div>
              ) : (
                <p>Нет топиков, требующих проверки.</p>
              )}
            </>
          )}
          {savedCandidate && (
            <section aria-label="Обновлённая карточка результата">
              <p role="status">Статус сохранён.</p>
              <CandidateResultPage
                key={`${savedCandidate}-${revision}`}
                token={token}
                candidateId={savedCandidate}
              />
            </section>
          )}
        </>
      )}
    </main>
  );
}
