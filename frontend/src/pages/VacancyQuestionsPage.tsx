import { useEffect, useMemo, useState } from "react";

import {
  Vacancy,
  VacancyQuestion,
  approveVacancyQuestion,
  approveVacancyQuestions,
  generateCoreQuestions,
  getVacancy,
  listVacancyQuestions,
  updateVacancyQuestion,
} from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";

export function VacancyQuestionsPage({ token, vacancyId }: { token: string; vacancyId: string }) {
  const [vacancy, setVacancy] = useState<Vacancy | null>(null);
  const [questions, setQuestions] = useState<VacancyQuestion[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const specialist = sessionStorage.getItem("internal-role") === "technical_specialist";
  const approved = questions !== null && questions.length > 0 && questions.every((q) => q.reviewed_by_expert);

  const topicTitle = useMemo(() => {
    const map = new Map<string, string>();
    for (const topic of vacancy?.topics ?? []) map.set(topic.id, topic.title);
    return map;
  }, [vacancy]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getVacancy(token, vacancyId, controller.signal),
      listVacancyQuestions(token, vacancyId, controller.signal),
    ])
      .then(([nextVacancy, rows]) => {
        setVacancy(nextVacancy);
        setQuestions(rows);
        setDrafts(Object.fromEntries(rows.map((row) => [row.id, row.text])));
      })
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, vacancyId]);

  async function generate() {
    setBusy(true);
    setNotice("");
    try {
      await generateCoreQuestions(token, vacancyId);
      const rows = await listVacancyQuestions(token, vacancyId);
      setQuestions(rows);
      setDrafts(Object.fromEntries(rows.map((row) => [row.id, row.text])));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Ошибка генерации.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(question: VacancyQuestion) {
    const draft = drafts[question.id] ?? question.text;
    setBusy(true);
    setNotice("");
    try {
      if (draft !== question.text) {
        await updateVacancyQuestion(token, vacancyId, question.id, draft);
      }
      const updated = await approveVacancyQuestion(token, vacancyId, question.id);
      setQuestions((rows) => rows?.map((row) => (row.id === updated.id ? updated : row)) ?? rows);
      setDrafts((rows) => ({ ...rows, [updated.id]: updated.text }));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Не удалось подтвердить вопрос.");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    setBusy(true);
    setNotice("");
    try {
      for (const question of questions ?? []) {
        const draft = drafts[question.id] ?? question.text;
        if (draft !== question.text) {
          await updateVacancyQuestion(token, vacancyId, question.id, draft);
        }
      }
      const rows = await approveVacancyQuestions(token, vacancyId);
      setQuestions(rows);
      setDrafts(Object.fromEntries(rows.map((row) => [row.id, row.text])));
      setNotice("Список вопросов подтверждён — интервью можно запускать.");
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Не удалось подтвердить вопросы.");
    } finally {
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

  return (
    <main>
      <Breadcrumbs
        items={[
          { label: "Команда", to: "/staff/overview" },
          { label: "Вакансии", to: "/staff/vacancies" },
          { label: "Вопросы" },
        ]}
      />
      <PageHead
        eyebrow="Ревью техспециалиста"
        title="Вопросы интервью"
        actions={
          <div className="inline">
            <StatusPill tone={approved ? "success" : "blue"}>
              {approved ? "Подтверждены" : "Черновики"}
            </StatusPill>
            <button type="button" className="btn small ghost" disabled={busy} onClick={() => void generate()}>
              {busy ? "…" : "Сгенерировать"}
            </button>
            {specialist && (
              <button type="button" className="btn small primary" disabled={busy || approved} onClick={() => void approve()}>
                Подтвердить все
              </button>
            )}
          </div>
        }
      />
      {notice && <p className="activity-note" role="status">{notice}</p>}

      {questions === null ? (
        <p role="status">Загружаем вопросы…</p>
      ) : questions.length === 0 ? (
        <EmptyState title="Вопросов нет" text="Сгенерируйте ядро вопросов по топикам вакансии." />
      ) : (
        <div className="question-editor-list compact-questions">
          {questions.map((question) => (
            <section className="question-editor" key={question.id}>
              <div className="question-editor-head">
                <div>
                  <h3>{topicTitle.get(question.topic_id) ?? "Топик"}</h3>
                  <p className="meta" style={{ margin: "4px 0 0" }}>
                    {question.type}
                    {question.source_reason ? ` · ${question.source_reason}` : ""}
                  </p>
                </div>
                <StatusPill tone={question.reviewed_by_expert ? "success" : "blue"}>
                  {question.reviewed_by_expert ? "подтверждён" : "черновик"}
                </StatusPill>
              </div>
              <textarea
                aria-label={`Вопрос · ${topicTitle.get(question.topic_id) ?? question.id}`}
                rows={3}
                value={drafts[question.id] ?? ""}
                disabled={!specialist}
                onChange={(event) =>
                  setDrafts((rows) => ({ ...rows, [question.id]: event.target.value }))
                }
              />
              {specialist && (
                <div className="question-actions">
                  <button
                    type="button"
                    className="btn small ghost"
                    disabled={busy || (question.reviewed_by_expert && drafts[question.id] === question.text)}
                    onClick={() => void confirm(question)}
                  >
                    {drafts[question.id] !== question.text ? "Сохранить и подтвердить" : "Подтвердить"}
                  </button>
                </div>
              )}
            </section>
          ))}
        </div>
      )}
      {!specialist && (
        <p className="meta">Подтверждать и править вопросы может только техспециалист.</p>
      )}
    </main>
  );
}
