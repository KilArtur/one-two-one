import { useEffect, useRef, useState } from "react";

function deviceError(reason: unknown): string {
  const name = reason instanceof DOMException ? reason.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Разрешите доступ к камере и микрофону в настройках браузера и повторите проверку.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return "Камера или микрофон не найдены. Подключите оба устройства и повторите проверку.";
  }
  return "Не удалось включить камеру и микрофон. Закройте использующие их приложения и повторите проверку.";
}

export function EquipmentCheck({
  onContinue,
}: {
  onContinue?: () => void;
}) {
  const liveVideo = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previewUrl = useRef<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [ready, setReady] = useState(false);
  const [recording, setRecording] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState("");

  function clearRecording() {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    const current = recorder.current;
    recorder.current = null;
    if (current) {
      current.ondataavailable = null;
      current.onstop = null;
      current.onerror = null;
      if (current.state !== "inactive") current.stop();
    }
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current = null;
  }

  useEffect(() => {
    let active = true;
    let acquired: MediaStream | null = null;
    setReady(false);
    setRecording(false);
    setPreview(null);
    setError("");

    function unavailable() {
      if (!active) return;
      clearRecording();
      setRecording(false);
      setPreview(null);
      setReady(false);
      setError("Камера или микрофон отключены либо недоступны. Подключите устройства и повторите проверку.");
      acquired?.getTracks().forEach((track) => track.stop());
    }

    async function connect() {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
        setError("Этот браузер не поддерживает проверку записи. Используйте современный браузер и HTTPS (или localhost).");
        return;
      }
      try {
        acquired = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        if (!active) {
          acquired.getTracks().forEach((track) => track.stop());
          return;
        }
        stream.current = acquired;
        const tracks = acquired.getTracks();
        if (!acquired.getAudioTracks().length || !acquired.getVideoTracks().length ||
            tracks.some((track) => track.readyState !== "live" || track.muted)) {
          unavailable();
          return;
        }
        tracks.forEach((track) => {
          track.addEventListener("ended", unavailable);
          track.addEventListener("mute", unavailable);
        });
        if (liveVideo.current) liveVideo.current.srcObject = acquired;
        setReady(true);
      } catch (reason) {
        if (active) setError(deviceError(reason));
      }
    }
    void connect();
    return () => {
      active = false;
      clearRecording();
      acquired?.getTracks().forEach((track) => {
        track.removeEventListener("ended", unavailable);
        track.removeEventListener("mute", unavailable);
        track.stop();
      });
      stream.current = null;
    };
  }, [attempt]);

  function record() {
    if (!ready || recording || !stream.current) return;
    clearRecording();
    setPreview(null);
    setError("");
    const chunks: Blob[] = [];
    try {
      const current = new MediaRecorder(stream.current);
      recorder.current = current;
      current.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      current.onerror = () => {
        clearRecording();
        setRecording(false);
        setError("Не удалось записать пробу. Повторите запись или проверку устройств.");
      };
      current.onstop = () => {
        if (timer.current !== null) clearTimeout(timer.current);
        timer.current = null;
        recorder.current = null;
        setRecording(false);
        const blob = new Blob(chunks, { type: current.mimeType || chunks[0]?.type || "video/webm" });
        if (!blob.size) {
          setError("Запись получилась пустой. Повторите запись и произнесите несколько слов.");
          return;
        }
        previewUrl.current = URL.createObjectURL(blob);
        setPreview(previewUrl.current);
      };
      current.start();
      setRecording(true);
      timer.current = setTimeout(() => {
        if (current.state !== "inactive") current.stop();
      }, 3000);
    } catch {
      clearRecording();
      setRecording(false);
      setError("Не удалось начать запись. Повторите проверку устройств или используйте другой браузер.");
    }
  }

  return (
    <main className="equipment-screen">
      <div className="equipment-head">
        <div>
          <p className="eyebrow">Шаг 2 · Подготовка</p>
          <h1>Проверка камеры и микрофона</h1>
          <p className="equipment-lead">
            Разрешите доступ, запишите 3 секунды и убедитесь, что вас видно и слышно.
          </p>
        </div>
      </div>

      <div className="equipment-row">
        <div className="camera equipment-camera">
          <video
            ref={liveVideo}
            aria-label="Изображение с камеры"
            autoPlay
            muted
            playsInline
          />
          <span className="camera-label">LIVE</span>
        </div>

        <aside className="equipment-controls">
          <div className="inline">
            <strong>Камера и микрофон</strong>
            <span className={`status ${ready ? "success" : error ? "risk" : "blue"}`}>
              {ready ? "Готово" : error ? "Ошибка" : "Ожидание"}
            </span>
          </div>
          <p role="status" className="equipment-status">
            {recording
              ? "Идёт тестовая запись — 3 секунды…"
              : ready
                ? "Камера и микрофон подключены."
                : error
                  ? "Проверка не пройдена."
                  : "Ожидаем доступ к устройствам…"}
          </p>
          {error && <p role="alert">{error}</p>}
          <div className="equipment-actions">
            <button type="button" className="btn primary" onClick={record} disabled={!ready || recording}>
              {preview ? "Записать пробу заново" : "Записать 3 секунды"}
            </button>
            <button
              type="button"
              className="btn ghost"
              onClick={() => setAttempt(attempt + 1)}
              disabled={recording}
            >
              Повторить проверку устройств
            </button>
          </div>
          {/* Слот всегда на месте — превью не сдвигает live-камеру */}
          <div className={`equipment-preview-frame${preview ? " has-preview" : ""}`}>
            {preview ? (
              <video
                aria-label="Тестовая запись"
                src={preview}
                controls
                playsInline
                className="equipment-preview-video"
              />
            ) : (
              <span className="equipment-preview-placeholder">Пробная запись (3 с)</span>
            )}
          </div>
        </aside>
      </div>

      <div className="equipment-foot">
        {onContinue && (
          <button
            type="button"
            className="btn primary"
            onClick={onContinue}
            disabled={!ready || !preview}
          >
            Меня видно и слышно — начать
          </button>
        )}
      </div>
    </main>
  );
}
