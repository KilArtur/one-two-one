import { useEffect, useState } from "react";

import {
  getInterviewQuestions,
  getInterviewSession,
  InterviewQuestion,
  requestFollowup,
  skipQuestion,
  submitInterview,
} from "../api/client";
import { InterviewQuestionStep } from "../components/InterviewQuestionStep";
import { Brand } from "../layouts/Shell";

export function InterviewPage({ token }: { token: string }) {
  const [questions, setQuestions] = useState<InterviewQuestion[] | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [deciding, setDeciding] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const list = await getInterviewQuestions(token, controller.signal);
        const session = await getInterviewSession(token, controller.signal);
        setQuestions(list);
        const current = session.current_question
          ? list.findIndex((item) => item.id === session.current_question?.id)
          : Math.max(list.length - 1, 0);
        setIndex(Math.max(current, 0));
        if (session.finished) {
          setAnswers(Object.fromEntries(list.map((item) => [item.id, true])));
        }
      } catch (reason) {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки вопросов.");
        }
      }
    }
    void load();
    return () => controller.abort();
  }, [token]);

  if (submitted) {
    return (
      <div className="candidate">
        <div className="saved">
          <div className="saved-mark">✓</div>
          <h1>Интервью отправлено</h1>
          <p>Спасибо! Ваши ответы сохранены и переданы команде. Ссылка больше не активна.</p>
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <main className="error-page">
        <div className="error-box">
          <h1>Интервью недоступно</h1>
          <p role="alert">{error}</p>
        </div>
      </main>
    );
  }
  if (!questions) return <p role="status">Загружаем вопросы…</p>;
  if (!questions.length) {
    return (
      <main className="error-page">
        <div className="error-box">
          <h1>Вопросы ещё не готовы</h1>
          <p>Обратитесь к рекрутеру.</p>
        </div>
      </main>
    );
  }

  const question = questions[index];
  const isLast = index + 1 >= questions.length;
  const isFollowup = question.type === "follow_up";
  const baseTotal = questions.filter((item) => item.type !== "follow_up").length;
  const baseNumber = questions
    .slice(0, index + 1)
    .filter((item) => item.type !== "follow_up").length;
  const answeredBase = questions.filter(
    (item) => item.type !== "follow_up" && answers[item.id],
  ).length;
  const progress = baseTotal === 0 ? 0 : Math.round((answeredBase / baseTotal) * 100);

  async function onSaved() {
    const saved = question;
    setAnswers((current) => ({ ...current, [saved.id]: true }));
    setDeciding(true);
    try {
      let decision = await requestFollowup(token, saved.topic_id);
      for (let attempt = 0; decision.reason === "transcription_pending" && attempt < 30; attempt++) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        decision = await requestFollowup(token, saved.topic_id);
      }
      if (decision.ask && decision.question) {
        const followup = decision.question;
        setQuestions((current) => {
          if (!current) return current;
          const next = [...current];
          next.splice(index + 1, 0, followup);
          return next;
        });
      }
    } catch {
      // сбой решения не блокирует прохождение
    } finally {
      setDeciding(false);
    }
  }

  async function onSkip() {
    setActionError("");
    try {
      await skipQuestion(token, question.id);
    } catch {
      setActionError("Пропуск не сохранён. Повторите попытку.");
      return;
    }
    setAnswers((current) => ({ ...current, [question.id]: true }));
  }

  async function onSubmit() {
    setSubmitting(true);
    try {
      await submitInterview(token);
      setSubmitted(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось отправить интервью.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="interview interview-compact">
      <div className="interview-top">
        <Brand />
        <span className="meta interview-top-meta">
          {isFollowup ? "Уточнение" : `${baseNumber} / ${baseTotal}`}
        </span>
      </div>
      <div className="interview-progress" aria-hidden>
        <span style={{ width: `${progress}%` }} />
      </div>
      {deciding ? (
        <div className="interview-wait" role="status" aria-live="polite">
          <span className="process-spinner interview-wait-spinner" aria-hidden />
          <p className="interview-wait-text">Проверяем, нужно ли уточнение…</p>
          <p className="interview-wait-sub">Это займёт несколько секунд</p>
        </div>
      ) : answers[question.id] ? (
        <div className="interview-wait interview-next-screen">
          <p className="interview-wait-text" role="status">
            Ответ сохранён
          </p>
          {isLast ? (
            <button
              type="button"
              className="btn interview-cta"
              onClick={onSubmit}
              disabled={submitting}
            >
              {submitting ? "Отправляем…" : "Завершить и отправить интервью"}
            </button>
          ) : (
            <button
              type="button"
              className="btn interview-cta"
              onClick={() => setIndex(index + 1)}
            >
              Следующий вопрос
            </button>
          )}
          {actionError && <p role="alert">{actionError}</p>}
        </div>
      ) : (
        <div className="interview-main">
          <div className="interview-question">
            <p className="eyebrow interview-eyebrow">
              {isFollowup ? "Уточняющий" : `Вопрос ${baseNumber} из ${baseTotal}`}
            </p>
            <InterviewQuestionStep
              key={question.id}
              question={question}
              token={token}
              onSaved={onSaved}
              onSkip={() => void onSkip()}
            />
            {actionError && <p role="alert">{actionError}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
