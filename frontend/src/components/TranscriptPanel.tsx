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
    normalized += char;
    positions.push(index);
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
    const start = Math.max(0, range.start - offset);
    const end = Math.min(text.length, range.end - offset);
    if (end <= start) continue;
    parts.push(text.slice(cursor, start), <mark key={start}>{text.slice(start, end)}</mark>);
    cursor = end;
  }
  parts.push(text.slice(cursor));
  return <>{parts}</>;
}

function timestamp(value: number): string {
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}

export function TranscriptContent({
  answers,
  token,
  candidateId,
}: {
  answers: TranscriptAnswer[];
  token: string;
  candidateId: string;
}) {
  const [openId, setOpenId] = useState<string | null>(null);

  if (!answers.length) return <p>Ответов пока нет.</p>;

  return (
    <div className="transcript-feed">
      {answers.map((answer, index) => {
        const text = answer.segments.map((s) => s.text).join("\n");
        const ranges = quoteRanges(text, answer.quotes);
        let offset = 0;
        const canPlay = !answer.skipped && !answer.technically_lost;
        const open = openId === answer.answer_id;
        return (
          <article
            key={answer.answer_id}
            className="transcript-item"
            aria-label={`Ответ: ${answer.question}`}
          >
            <header className="transcript-card-head">
              <span className="eyebrow">Вопрос {index + 1}</span>
            </header>

            <div className="transcript-block">
              <p className="transcript-label">Вопрос</p>
              <p className="transcript-question">{answer.question}</p>
            </div>

            <div className="transcript-block">
              <p className="transcript-label">Ответ</p>
              {answer.skipped && <p>Вопрос пропущен кандидатом.</p>}
              {answer.technically_lost && <p>Ответ пострадал из-за технического сбоя.</p>}
              {answer.segments.length > 0 ? (
                <ol className="transcript-segments">
                  {answer.segments.map((segment, segmentIndex) => {
                    const start = offset;
                    offset += segment.text.length + 1;
                    return (
                      <li key={segmentIndex} className="transcript-segment">
                        <span className="transcript-time">
                          {timestamp(segment.start)}–{timestamp(segment.end)}
                        </span>
                        <span className="transcript-text">
                          <Highlighted text={segment.text} ranges={ranges} offset={start} />
                        </span>
                      </li>
                    );
                  })}
                </ol>
              ) : answer.transcript ? (
                <p className="transcript-text">
                  <Highlighted
                    text={answer.transcript}
                    ranges={quoteRanges(answer.transcript, answer.quotes)}
                  />
                </p>
              ) : (
                <p>
                  {answer.processing_status === "error"
                    ? "Транскрибация не удалась."
                    : "Транскрипт пока недоступен."}
                </p>
              )}
              {answer.segments.length > 0 && answer.transcript && (
                <details className="transcript-full">
                  <summary>Полный текст без сегментов</summary>
                  <p className="transcript-text">
                    <Highlighted
                      text={answer.transcript}
                      ranges={quoteRanges(answer.transcript, answer.quotes)}
                    />
                  </p>
                </details>
              )}
            </div>

            {canPlay && (
              <div className="transcript-block transcript-media">
                <p className="transcript-label">Видео</p>
                <button
                  type="button"
                  className="btn small ghost"
                  onClick={() => setOpenId(open ? null : answer.answer_id)}
                >
                  {open ? "Скрыть запись" : "Смотреть запись"}
                </button>
                {open && (
                  <div className="transcript-inline-player">
                    <EvidencePlayer
                      key={answer.answer_id}
                      token={token}
                      candidateId={candidateId}
                      item={{
                        answer_id: answer.answer_id,
                        question_id: answer.question_id,
                        question: answer.question,
                        quote: "",
                        start_sec: 0,
                        end_sec: null,
                        video_available: true,
                      }}
                    />
                  </div>
                )}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

export function TranscriptPanel({
  token,
  candidateId,
  topicId,
}: {
  token: string;
  candidateId: string;
  topicId?: string;
}) {
  const resultLink = useContext(ResultLinkContext);
  const [answers, setAnswers] = useState<TranscriptAnswer[] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setAnswers(null);
    setError("");
    getTranscripts(token, candidateId, topicId, controller.signal, resultLink)
      .then((data) => {
        if (!controller.signal.aborted) setAnswers(data);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Транскрипт недоступен.");
        }
      });
    return () => controller.abort();
  }, [token, candidateId, topicId, attempt, resultLink]);

  return (
    <section aria-label="Транскрипт интервью" className="transcript-panel">
      <h2>Транскрипт интервью</h2>
      <p className="meta">Выделены цитаты, использованные в оценке соответствующего топика.</p>
      {error ? (
        <>
          <p role="alert">{error}</p>
          <button type="button" className="btn ghost" onClick={() => setAttempt((v) => v + 1)}>
            Повторить загрузку транскрипта
          </button>
        </>
      ) : answers ? (
        <TranscriptContent answers={answers} token={token} candidateId={candidateId} />
      ) : (
        <p role="status">Загружаем транскрипт…</p>
      )}
    </section>
  );
}
