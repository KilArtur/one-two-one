import { ResultLinkContext } from "./ResultLinkContext";
import { useContext, useEffect, useState } from "react";
import { getTranscripts, TranscriptAnswer } from "../api/client";
import { EvidencePlayer } from "./EvidencePanel";

type Range = { start: number; end: number };
export function quoteRanges(text: string, quotes: string[]): Range[] {
  let normalized = "";
  const positions: number[] = [];
  for (let index = 0; index < text.length; index++) {
    const char = /\s/.test(text[index]) ? " " : text[index];
    if (char === " " && normalized.endsWith(" ")) continue;
    normalized += char; positions.push(index);
  }
  const ranges: Range[] = [];
  for (const quote of quotes) {
    const needle = quote.replace(/\s+/g, " ").trim();
    if (!needle) continue;
    let from = 0;
    while (from < normalized.length) {
      const start = normalized.indexOf(needle, from);
      if (start < 0) break;
      ranges.push({ start: positions[start], end: positions[start + needle.length - 1] + 1 });
      from = start + needle.length;
    }
  }
  const merged: Range[] = [];
  for (const range of ranges.sort((a, b) => a.start - b.start)) {
    const last = merged[merged.length - 1];
    if (last && range.start <= last.end) last.end = Math.max(last.end, range.end);
    else merged.push({ ...range });
  }
  return merged;
}
function Highlighted({ text, ranges, offset = 0 }: { text: string; ranges: Range[]; offset?: number }) {
  let cursor = 0;
  const parts = [];
  for (const range of ranges) {
    const start = Math.max(0, range.start - offset), end = Math.min(text.length, range.end - offset);
    if (end <= start) continue;
    parts.push(text.slice(cursor, start), <mark key={start}>{text.slice(start, end)}</mark>); cursor = end;
  }
  parts.push(text.slice(cursor));
  return <>{parts}</>;
}
function timestamp(value: number): string {
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}
export function TranscriptContent({ answers }: { answers: TranscriptAnswer[] }) {
  return <>{!answers.length && <p>Ответов пока нет.</p>}{answers.map((answer) => {
    const text = answer.segments.map((s) => s.text).join("\n");
    const ranges = quoteRanges(text, answer.quotes);
    let offset = 0;
    return <article key={answer.answer_id} aria-label={`Ответ: ${answer.question}`}>
      <h3>{answer.question}</h3>
      {answer.skipped && <p>Вопрос пропущен кандидатом.</p>}
      {answer.technically_lost && <p>Ответ пострадал из-за технического сбоя.</p>}
      {answer.segments.length > 0 ? <>
        <ol>{answer.segments.map((segment, index) => {
          const start = offset; offset += segment.text.length + 1;
          return <li key={index}><span>{timestamp(segment.start)}–{timestamp(segment.end)} </span>
            <span style={{ whiteSpace: "pre-wrap" }}><Highlighted text={segment.text} ranges={ranges} offset={start} /></span>
          </li>;
        })}</ol>
        {answer.transcript && <details><summary>Полный текст без сегментов</summary><p style={{ whiteSpace: "pre-wrap" }}>
          <Highlighted text={answer.transcript} ranges={quoteRanges(answer.transcript, answer.quotes)} />
        </p></details>}
      </> : answer.transcript ? <p style={{ whiteSpace: "pre-wrap" }}><Highlighted text={answer.transcript} ranges={quoteRanges(answer.transcript, answer.quotes)} /></p>
        : <p>{answer.processing_status === "error" ? "Транскрибация не удалась." : "Транскрипт пока недоступен."}</p>}
    </article>;
  })}</>;
}
export function TranscriptPanel({ token, candidateId, topicId }: { token: string; candidateId: string; topicId?: string }) {
  const resultLink = useContext(ResultLinkContext);
  const [answers, setAnswers] = useState<TranscriptAnswer[] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [recording, setRecording] = useState<TranscriptAnswer | null>(null);
  useEffect(() => {
    const controller = new AbortController(); setAnswers(null); setError("");
    getTranscripts(token, candidateId, topicId, controller.signal, resultLink).then((data) => {
      if (!controller.signal.aborted) setAnswers(data);
    }).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Транскрипт недоступен.");
    });
    return () => controller.abort();
  }, [token, candidateId, topicId, attempt, resultLink]);
  return <section aria-label="Транскрипт интервью"><h2>Транскрипт интервью</h2>
    <p>Выделены цитаты, использованные в оценке соответствующего топика.</p>
    {error ? <><p role="alert">{error}</p><button onClick={() => setAttempt((v) => v + 1)}>Повторить загрузку транскрипта</button></>
      : answers ? <TranscriptContent answers={answers} /> : <p role="status">Загружаем транскрипт…</p>}
    {answers?.filter((answer) => !answer.skipped && !answer.technically_lost).map((answer) =>
      <p key={answer.answer_id}><button className="btn ghost" onClick={() => setRecording(answer)}>
        Посмотреть запись: {answer.question}
      </button></p>)}
    {recording && <EvidencePlayer key={recording.answer_id} token={token} candidateId={candidateId} item={{
      answer_id: recording.answer_id, question_id: recording.question_id,
      question: recording.question, quote: "", start_sec: 0, end_sec: null, video_available: true,
    }} />}
  </section>;
}
