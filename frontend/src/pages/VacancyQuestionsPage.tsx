import { useEffect, useState } from "react";

import {
  VacancyQuestion,
  approveVacancyQuestion,
  approveVacancyQuestions,
  generateCoreQuestions,
  listVacancyQuestions,
  updateVacancyQuestion,
} from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";

export function VacancyQuestionsPage({ token, vacancyId }: { token: string; vacancyId: string }) {
  const [questions, setQuestions] = useState<VacancyQuestion[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const specialist = sessionStorage.getItem("internal-role") === "technical_specialist";
  const approved = questions !== null && questions.length > 0 && questions.every((q) => q.reviewed_by_expert);

  useEffect(() => {
    const controller = new AbortController();
    listVacancyQuestions(token, vacancyId, controller.signal)
      .then((rows) => {
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
          <StatusPill tone={approved ? "success" : "blue"}>
            {approved ? "Подтверждены" : "Ожидают подтверждения"}
          </StatusPill>
        }
      />
      <p className="meta">
        Интервью не запускается, пока техспециалист не подтвердит список. Подтверждённые вопросы
        раскрываются под резюме кандидата при выпуске приглашения.
      </p>
      {notice && <p className="activity-note" role="status">{notice}</p>}

      {questions === null ? (
        <p role="status">Загружаем вопросы…</p>
      ) : questions.length === 0 ? (
        <EmptyState title="Вопросов нет" text="Сгенерируйте ядро вопросов по топикам вакансии." />
      ) : (
        <div className="matrix">
          {questions.map((question, index) => (
            <section className="panel" key={question.id}>
              <div className="inline">
                <span className="meta">Вопрос {index + 1}</span>
                <span className="spacer" />
                <StatusPill tone={question.reviewed_by_expert ? "success" : "blue"}>
                  {question.reviewed_by_expert ? "подтверждён" : "черновик"}
                </StatusPill>
              </div>
              <textarea
                aria-label={`Вопрос ${index + 1}`}
                value={drafts[question.id] ?? ""}
                disabled={!specialist}
                onChange={(event) =>
                  setDrafts((rows) => ({ ...rows, [question.id]: event.target.value }))
                }
              />
              {question.source_reason && <p className="meta">{question.source_reason}</p>}
              {specialist && (
                <button
                  type="button"
                  className="btn small ghost"
                  disabled={busy || (question.reviewed_by_expert && drafts[question.id] === question.text)}
                  onClick={() => void confirm(question)}
                >
                  {drafts[question.id] !== question.text ? "Сохранить и подтвердить" : "Подтвердить"}
                </button>
              )}
            </section>
          ))}
        </div>
      )}

      <div className="inline" style={{ marginTop: 24, justifyContent: "flex-end" }}>
        <button type="button" className="btn ghost" disabled={busy} onClick={() => void generate()}>
          {busy ? "Работаем…" : "Сгенерировать недостающие"}
        </button>
        {specialist && (
          <button type="button" className="btn primary" disabled={busy || approved} onClick={() => void approve()}>
            Подтвердить все
          </button>
        )}
      </div>
      {!specialist && (
        <p className="meta">Подтверждать и править вопросы может только техспециалист.</p>
      )}
    </main>
  );
}
