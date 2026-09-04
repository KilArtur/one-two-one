import { useEffect, useRef, useState } from "react";

import { getInterviewQuestions, InterviewQuestion } from "../api/client";
import { InterviewQuestionStep } from "../components/InterviewQuestionStep";

export function InterviewPage({ token }: { token: string }) {
  const [questions, setQuestions] = useState<InterviewQuestion[] | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const urls = useRef<string[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    void getInterviewQuestions(token, controller.signal).then(setQuestions).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Ошибка загрузки вопросов.");
    });
    return () => { controller.abort(); urls.current.forEach((url) => URL.revokeObjectURL(url)); };
  }, [token]);
  if (error) return <main><h1>Интервью недоступно</h1><p role="alert">{error}</p></main>;
  if (!questions) return <p role="status">Загружаем вопросы…</p>;
  if (!questions.length) return <main><h1>Вопросы ещё не готовы</h1><p>Обратитесь к рекрутеру.</p></main>;
  const question = questions[index];
  return <main>
    <h1>Интервью · вопрос {index + 1} из {questions.length}</h1>
    <p>На основной вопрос — 2 минуты, на уточнение — 1 минута. Перезапись ответа недоступна.</p>
    <InterviewQuestionStep key={question.id} question={question} token={token} onRecorded={(blob) => {
      const url = URL.createObjectURL(blob);
      urls.current.push(url);
      setAnswers((current) => ({ ...current, [question.id]: url }));
    }} />
    {answers[question.id] && <>
      <p>Отправка ответов пока недоступна. Записи находятся только в этой вкладке; скачайте их перед выходом.</p>
      {index + 1 < questions.length && <button onClick={() => setIndex(index + 1)}>Следующий вопрос</button>}
    </>}
    {Object.entries(answers).map(([id, url], position) => <p key={id}>
      <a href={url} download={`answer-${position + 1}.webm`}>Скачать ответ {position + 1}</a>
    </p>)}
  </main>;
}
