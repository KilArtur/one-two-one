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

export function InterviewPage({ token }: { token: string }) {
  const [questions, setQuestions] = useState<InterviewQuestion[] | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [deciding, setDeciding] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const list = await getInterviewQuestions(token, controller.signal);
        const session = await getInterviewSession(token, controller.signal);
        setQuestions(list);
        setIndex(Math.min(session.answered_count, Math.max(list.length - 1, 0)));
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
      <main>
        <h1>Интервью отправлено</h1>
        <p>Спасибо! Ваши ответы сохранены и переданы команде. Ссылка больше не активна.</p>
      </main>
    );
  }
  if (error) {
    return (
      <main>
        <h1>Интервью недоступно</h1>
        <p role="alert">{error}</p>
      </main>
    );
  }
  if (!questions) return <p role="status">Загружаем вопросы…</p>;
  if (!questions.length) {
    return (
      <main>
        <h1>Вопросы ещё не готовы</h1>
        <p>Обратитесь к рекрутеру.</p>
      </main>
    );
  }

  const question = questions[index];
  const isLast = index + 1 >= questions.length;

  async function onSaved() {
    const saved = question;
    setAnswers((current) => ({ ...current, [saved.id]: true }));
    setDeciding(true);
    try {
      const decision = await requestFollowup(token, saved.topic_id);
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
    try {
      await skipQuestion(token, question.id);
    } catch {
      // пропуск best-effort — всё равно двигаемся дальше
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
    <main>
      <h1>
        Интервью · вопрос {index + 1} из {questions.length}
      </h1>
      <p>На основной вопрос — 2 минуты, на уточнение — 1 минута. Перезапись ответа недоступна.</p>
      <InterviewQuestionStep key={question.id} question={question} token={token} onSaved={onSaved} />
      {!answers[question.id] && (
        <div>
          <p>Пропуск нельзя отменить: вопрос будет засчитан как «не подтверждено».</p>
          <button onClick={onSkip}>Пропустить вопрос</button>
        </div>
      )}
      {answers[question.id] && (
        <>
          {deciding && <p role="status">Проверяем, нужно ли уточнение…</p>}
          {!deciding &&
            (isLast ? (
              <button onClick={onSubmit} disabled={submitting}>
                {submitting ? "Отправляем…" : "Завершить и отправить интервью"}
              </button>
            ) : (
              <button onClick={() => setIndex(index + 1)}>Следующий вопрос</button>
            ))}
        </>
      )}
    </main>
  );
}
