import { useEffect, useState } from "react";

import { getInterviewQuestions, InterviewQuestion } from "../api/client";
import { InterviewQuestionStep } from "../components/InterviewQuestionStep";

export function InterviewPage({ token }: { token: string }) {
  const [questions, setQuestions] = useState<InterviewQuestion[] | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  useEffect(() => {
    const controller = new AbortController();
    void getInterviewQuestions(token, controller.signal).then(setQuestions).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Ошибка загрузки вопросов.");
    });
    return () => controller.abort();
  }, [token]);
  if (error) return <main><h1>Интервью недоступно</h1><p role="alert">{error}</p></main>;
  if (!questions) return <p role="status">Загружаем вопросы…</p>;
  if (!questions.length) return <main><h1>Вопросы ещё не готовы</h1><p>Обратитесь к рекрутеру.</p></main>;
  const question = questions[index];
  return <main>
    <h1>Интервью · вопрос {index + 1} из {questions.length}</h1>
    <p>На основной вопрос — 2 минуты, на уточнение — 1 минута. Перезапись ответа недоступна.</p>
    <InterviewQuestionStep key={question.id} question={question} token={token} onSaved={() => {
      setAnswers((current) => ({ ...current, [question.id]: true }));
    }} />
    {answers[question.id] && <>
      {index + 1 < questions.length
        ? <button onClick={() => setIndex(index + 1)}>Следующий вопрос</button>
        : <p>Все ответы сохранены.</p>}
    </>}

  </main>;
}
