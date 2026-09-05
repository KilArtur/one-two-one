import { useEffect, useState } from "react";

import {
  getInterviewQuestions,
  getInterviewSession,
  InterviewQuestion,
  requestFollowup,
} from "../api/client";
import { InterviewQuestionStep } from "../components/InterviewQuestionStep";

export function InterviewPage({ token }: { token: string }) {
  const [questions, setQuestions] = useState<InterviewQuestion[] | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [deciding, setDeciding] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const list = await getInterviewQuestions(token, controller.signal);
        // Р11: восстановление сессии — продолжаем с первого неотвеченного вопроса.
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

  async function onSaved() {
    const saved = question;
    setAnswers((current) => ({ ...current, [saved.id]: true }));
    // M4/Р12: синхронное решение об уточнении по текущему топику.
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
      // сбой решения не блокирует прохождение — просто идём дальше
    } finally {
      setDeciding(false);
    }
  }

  const isLast = index + 1 >= questions.length;

  return (
    <main>
      <h1>
        Интервью · вопрос {index + 1} из {questions.length}
      </h1>
      <p>На основной вопрос — 2 минуты, на уточнение — 1 минута. Перезапись ответа недоступна.</p>
      <InterviewQuestionStep key={question.id} question={question} token={token} onSaved={onSaved} />
      {answers[question.id] && (
        <>
          {deciding && <p role="status">Проверяем, нужно ли уточнение…</p>}
          {!deciding &&
            (isLast ? (
              <p>Все ответы сохранены.</p>
            ) : (
              <button onClick={() => setIndex(index + 1)}>Следующий вопрос</button>
            ))}
        </>
      )}
    </main>
  );
}
