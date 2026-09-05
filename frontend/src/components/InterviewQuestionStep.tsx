import { useEffect, useRef, useState } from "react";

import { getQuestionAudio, InterviewQuestion, SavedAnswer } from "../api/client";
import { useChunkUpload } from "../hooks/useChunkUpload";
import { useRecorder } from "../hooks/useRecorder";
import { attachQuestionAudio } from "../hooks/questionAudio";

type Phase = "preparing" | "speaking" | "recording" | "stopping" | "recorded" | "error";

export function InterviewQuestionStep({ question, token, onSaved }: {
  question: InterviewQuestion; token: string; onSaved: (answer: SavedAnswer) => void;
}) {
  const limit = question.type === "follow_up" ? 60 : 120;
  const [remaining, setRemaining] = useState(limit);
  const [phase, setPhase] = useState<Phase>("preparing");
  const [error, setError] = useState("");
  const [needsPlay, setNeedsPlay] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [canRetry, setCanRetry] = useState(true);
  const player = useRef<HTMLAudioElement>(null);
  const camera = useRef<HTMLVideoElement>(null);
  const stop = useRef<() => void>(() => undefined);
  const saved = useRef(onSaved);
  saved.current = onSaved;
  const upload = useChunkUpload(token, question.id);
  const capture = useRecorder();
  useEffect(() => { if (upload.answer) saved.current(upload.answer); }, [upload.answer]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let media: MediaStream | null = null;
    let audioUrl: string | null = null;
    let interval: ReturnType<typeof setInterval> | undefined;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let started = false;
    let failed = false;
    let playAttempted = false;
    const audio = player.current!;
    setPhase("preparing");
    setRemaining(limit);
    setError("");
    setNeedsPlay(false);
    setCanRetry(true);

    function clearTimers() { clearInterval(interval); clearTimeout(timeout); }
    function fail(message: string) {
      if (!active || failed) return;
      failed = true;
      clearTimers();
      controller.abort();
      audio.pause();
      capture.dispose();
      media?.getTracks().forEach((track) => track.stop());
      setCanRetry(!started);
      setNeedsPlay(false);
      setError(message);
      setPhase("error");
    }
    function lostDevice() { fail("Камера или микрофон отключены. Запись ответа прервана."); }
    let stopping = false;
    stop.current = () => {
      if (started && !stopping) {
        stopping = true;
        clearTimers();
        setPhase("stopping");
        capture.stop();
      }
    };
    audio.oncanplay = () => {
      if (playAttempted || failed || !active) return;
      playAttempted = true;
      setPhase("speaking");
      void audio.play().catch(() => { if (active && !failed) setNeedsPlay(true); });
    };
    audio.onerror = () => fail("Не удалось воспроизвести вопрос. Повторите озвучку.");
    audio.onended = () => {
      if (!active || failed || started || !media) return;
      try {
        capture.start(media, {
          onChunk: (kind, chunk) => upload.queue.enqueue(kind, chunk),
          onStart: () => {
            if (!active || failed) return;
            const deadline = Date.now() + limit * 1000;
            setPhase("recording");
            setCanRetry(false);
            const tick = () => {
              const seconds = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
              setRemaining(seconds);
              if (seconds === 0) stop.current();
            };
            interval = setInterval(tick, 250);
            timeout = setTimeout(tick, limit * 1000);
          },
          onError: () => fail("Ошибка записи ответа. Обратитесь к рекрутеру."),
          onComplete: (duration) => {
            clearTimers();
            if (!active || failed) return;
            media?.getTracks().forEach((track) => track.stop());
            setPhase("recorded");
            void upload.queue.finish(Math.min(limit, duration));
          },
        });
        started = true;
      } catch { fail("Не удалось начать запись ответа. Проверьте устройства и повторите озвучку."); }
    };
    async function prepare() {
      try {
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
          throw new Error("Браузер не поддерживает запись. Используйте современный браузер и HTTPS.");
        }
        media = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
        if (!active) { media.getTracks().forEach((track) => track.stop()); return; }
        if (!media.getAudioTracks().length || !media.getVideoTracks().length ||
            media.getTracks().some((track) => track.readyState !== "live" || track.muted)) {
          throw new Error("Для ответа нужны работающие камера и микрофон.");
        }
        media.getTracks().forEach((track) => {
          track.addEventListener("ended", lostDevice);
          track.addEventListener("mute", lostDevice);
        });
        if (camera.current) camera.current.srcObject = media;
        await upload.queue.begin();
        if (!active) return;
        const response = await getQuestionAudio(token, question.id, controller.signal);
        await attachQuestionAudio(audio, response, controller.signal, (url) => { audioUrl = url; });
      } catch (reason) {
        if (active && !failed) fail(reason instanceof Error ? reason.message : "Не удалось подготовить вопрос.");
      }
    }
    void prepare();
    return () => {
      active = false;
      controller.abort();
      clearTimers();
      audio.onended = audio.oncanplay = audio.onerror = null;
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      capture.dispose();
      media?.getTracks().forEach((track) => {
        track.removeEventListener("ended", lostDevice);
        track.removeEventListener("mute", lostDevice);
        track.stop();
      });
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [question.id, token, limit, attempt]);

  return (
    <section className="live-copy">
      <p className="live-question-label">
        {question.type === "follow_up" ? "Уточнение" : "Вопрос"}
      </p>
      <h2 style={{ color: "white", fontSize: "clamp(28px, 3vw, 42px)", fontWeight: 400 }}>
        {question.text}
      </h2>
      <p style={{ color: "#aaaab0" }}>
        Вопрос озвучен синтезированным голосом. После озвучки запись начнётся автоматически.
      </p>
      <audio ref={player} aria-label="Озвучка вопроса" />
      {needsPlay && (
        <button
          type="button"
          className="btn dark"
          onClick={() => {
            void player.current
              ?.play()
              .then(() => setNeedsPlay(false))
              .catch(() => setNeedsPlay(true));
          }}
        >
          Прослушать вопрос
        </button>
      )}
      <div className="candidate-camera" style={{ marginTop: 24 }}>
        <video
          ref={camera}
          autoPlay
          muted
          playsInline
          aria-label="Камера интервью"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
        {phase === "recording" && (
          <span className="rec-chip">
            <span className="recording-dot" /> REC
          </span>
        )}
      </div>
      <p
        role="timer"
        aria-label="Осталось времени"
        className="timer"
        style={{ color: "white", margin: "18px 0 8px" }}
      >
        {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}
      </p>
      <p
        role="status"
        style={{
          color: phase === "recording" ? "#ff8d86" : "#d0d0d4",
          fontWeight: 600,
        }}
      >
        {phase === "recording"
          ? "● REC — идёт запись ответа"
          : phase === "speaking"
            ? "Звучит вопрос — таймер ещё не запущен"
            : phase === "preparing"
              ? "Подготавливаем озвучку и устройства…"
              : phase === "recorded"
                ? upload.status === "saved"
                  ? "Ответ сохранён"
                  : "Сохраняем ответ…"
                : phase === "stopping"
                  ? "Завершаем запись…"
                  : "Запись остановлена"}
      </p>
      {phase === "recording" && (
        <button type="button" className="btn dark" onClick={() => stop.current()}>
          Закончить ответ
        </button>
      )}
      {upload.status === "error" && (
        <div>
          <p role="alert">
            {upload.error} Не закрывайте вкладку.
          </p>
          <button type="button" className="btn dark" onClick={() => void upload.queue.retry()}>
            Повторить загрузку
          </button>
        </div>
      )}
      {phase === "recording" && upload.status !== "error" && (
        <p style={{ color: "#aaaab0" }}>Части ответа загружаются по ходу записи.</p>
      )}
      {error && <p role="alert">{error}</p>}
      {phase === "error" && canRetry && (
        <button type="button" className="btn dark" onClick={() => setAttempt(attempt + 1)}>
          Повторить озвучку
        </button>
      )}
    </section>
  );
}
