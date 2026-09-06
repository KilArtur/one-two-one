import { ResultLinkContext } from "./ResultLinkContext";
import { useContext, useEffect, useRef, useState } from "react";
import { AnswerMedia, EvidenceItem, getAnswerMedia, getEvidence, recordVideoView } from "../api/client";

export function EvidencePlayer({ token, candidateId, item }: { token: string; candidateId: string; item: EvidenceItem }) {
  const resultLink = useContext(ResultLinkContext);
  const [media, setMedia] = useState<AnswerMedia | null>(null);
  const [error, setError] = useState("");
  const video = useRef<HTMLVideoElement>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const eventId = useRef(crypto.randomUUID());
  const logged = useRef(false);
  const logging = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    getAnswerMedia(token, candidateId, item.answer_id, controller.signal, resultLink).then(setMedia).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Запись недоступна.");
    });
    return () => controller.abort();
  }, [token, candidateId, item.answer_id, resultLink]);
  const sync = () => {
    if (audio.current && video.current) {
      audio.current.currentTime = video.current.currentTime;
      audio.current.playbackRate = video.current.playbackRate;
    }
  };
  const playing = async () => {
    if (!video.current) return;
    sync();
    if (audio.current) void audio.current.play().catch(() => {
      video.current?.pause(); setError("Не удалось запустить аудио. Нажмите воспроизведение ещё раз.");
    });
    if (logged.current || logging.current) return;
    logging.current = true;
    try {
      await recordVideoView(token, candidateId, item.answer_id, eventId.current, video.current.currentTime, resultLink);
      logged.current = true; setError("");
    } catch {
      video.current?.pause(); audio.current?.pause();
      setError("Не удалось зарегистрировать просмотр. Нажмите воспроизведение для повторной попытки.");
    } finally { logging.current = false; }
  };
  return <div>
    {error && <p role="alert">{error}</p>}
    {media ? <>
      {media.audio_url && <audio ref={audio} src={media.audio_url} preload="auto" onError={() => {
        video.current?.pause(); setError("Аудиодорожка недоступна. Откройте фрагмент повторно.");
      }} />}
      <video ref={video} src={media.video_url} controls preload="auto"
        aria-label="Видео ответа" style={{ width: "100%" }}
        onLoadedMetadata={() => { if (video.current) video.current.currentTime = item.start_sec ?? 0; }}
        onPlay={() => { if (logged.current) { eventId.current = crypto.randomUUID(); logged.current = false; } }}
        onPlaying={() => void playing()} onPause={() => audio.current?.pause()}
        onWaiting={() => audio.current?.pause()} onEnded={() => audio.current?.pause()}
        onSeeked={sync} onRateChange={sync}
        onVolumeChange={() => {
          if (audio.current && video.current) {
            audio.current.volume = video.current.volume;
            audio.current.muted = video.current.muted;
          }
        }}
        onTimeUpdate={() => { if (audio.current && video.current && Math.abs(audio.current.currentTime - video.current.currentTime) > 0.3) sync(); }}
        onError={() => setError("Видео недоступно. Откройте фрагмент повторно.")} />
    </> : !error && <p role="status">Загружаем запись…</p>}
  </div>;
}

export function EvidencePanel({ token, candidateId, topicId }: { token: string; candidateId: string; topicId: string }) {
  const resultLink = useContext(ResultLinkContext);
  const [items, setItems] = useState<EvidenceItem[] | null>(null);
  const [selected, setSelected] = useState(0);
  const [selection, setSelection] = useState(0);
  const [error, setError] = useState("");
  const quoteRef = useRef<HTMLQuoteElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    getEvidence(token, candidateId, topicId, controller.signal, resultLink).then(setItems).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Evidence недоступно.");
    });
    return () => controller.abort();
  }, [token, candidateId, topicId, resultLink]);
  useEffect(() => {
    if (selection === 0) return;
    const node = quoteRef.current;
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [selection]);
  return <section aria-label="Evidence топика" className="evidence-panel">
    {error && <p role="alert">{error}</p>}
    {!items && !error && <p role="status">Загружаем цитаты…</p>}
    {items?.length === 0 && <p>Цитаты с доступным ответом отсутствуют.</p>}
    {items?.map((item, index) => <div key={`${item.answer_id}-${index}`} className="evidence-item-block">
      <p>{item.question}</p>
      <blockquote ref={index === selected ? quoteRef : undefined}>
        {index === selected ? <mark>{item.quote}</mark> : item.quote}
      </blockquote>
      <button type="button" disabled={!item.video_available} onClick={() => { setSelected(index); setSelection((v) => v + 1); }}>
        {item.video_available ? `К фрагменту ${item.start_sec} с` : "Видео или таймкод недоступны"}
      </button>
    </div>)}
    {items?.[selected]?.video_available && (
      <div className="evidence-video" id="evidence-video">
        <EvidencePlayer key={`${selected}-${selection}`} token={token} candidateId={candidateId} item={items[selected]} />
      </div>
    )}
  </section>;
}
