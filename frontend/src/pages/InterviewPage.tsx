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
  const progress = Math.round(((index + (answers[question.id] ? 1 : 0)) / questions.length) * 100);

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
    <div className="interview">
      <div className="interview-top">
        <Brand />
        <span className="meta" style={{ color: "#aaaab0" }}>
          Непрерывная запись ответа
        </span>
      </div>
      <div className="interview-progress" aria-hidden>
        <span style={{ width: `${progress}%` }} />
      </div>
      <div className="interview-main">
        <div className="interview-question">
          <p className="eyebrow" style={{ color: "#9d99ff" }}>
            Интервью · вопрос {index + 1} из {questions.length}
          </p>
          <h1>
            Интервью · вопрос {index + 1} из {questions.length}
          </h1>
          <p>На основной вопрос — 2 минуты, на уточнение — 1 минута. Перезапись ответа недоступна.</p>
          {!answers[question.id] && <InterviewQuestionStep
            key={question.id}
            question={question}
            token={token}
            onSaved={onSaved}
          />}
          {answers[question.id] && <p role="status">Ответ сохранён.</p>}
          {actionError && <p role="alert">{actionError}</p>}
        </div>
      </div>
      <div className="record-bar">
        <div className="record-status">
          {!answers[question.id] && (
            <div>
              <p className="meta">Пропуск нельзя отменить: вопрос будет засчитан как «не подтверждено».</p>
              <button type="button" className="btn ghost" onClick={onSkip}>
                Пропустить вопрос
              </button>
            </div>
          )}
          {answers[question.id] && (
            <>
              {deciding && <p role="status">Проверяем, нужно ли уточнение…</p>}
              {!deciding &&
                (isLast ? (
                  <button
                    type="button"
                    className="btn primary"
                    onClick={onSubmit}
                    disabled={submitting}
                  >
                    {submitting ? "Отправляем…" : "Завершить и отправить интервью"}
                  </button>
                ) : (
                  <button type="button" className="btn primary" onClick={() => setIndex(index + 1)}>
                    Следующий вопрос
                  </button>
                ))}
            </>
          )}
        </div>
        <div className="health">
          <span>REC после озвучки</span>
          <span>Ответ сохраняется чанками</span>
        </div>
      </div>
    </div>
  );
}
