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

export function EquipmentCheck() {
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
    <main>
      <p>Шаг 2 · Подготовка</p>
      <h1>Проверка камеры и микрофона</h1>
      <p>Разрешите доступ к обоим устройствам. Запишите короткую пробу: посмотрите в камеру
        и произнесите несколько слов. Тестовая запись остаётся в этой вкладке.</p>
      <video ref={liveVideo} aria-label="Изображение с камеры" autoPlay muted playsInline
        style={{ width: "100%", maxHeight: 360, background: "#111", borderRadius: 8 }} />
      {error && <p role="alert">{error}</p>}
      <p role="status">{recording ? "Идёт тестовая запись — 3 секунды…" : ready
        ? "Камера и микрофон подключены." : error ? "Проверка не пройдена." : "Ожидаем доступ к устройствам…"}</p>
      <button onClick={record} disabled={!ready || recording}>
        {preview ? "Записать пробу заново" : "Записать 3 секунды"}
      </button>{" "}
      <button onClick={() => setAttempt(attempt + 1)} disabled={recording}>Повторить проверку устройств</button>
      {preview && <section>
        <h2>Прослушайте и посмотрите запись</h2>
        <video aria-label="Тестовая запись" src={preview} controls playsInline
          style={{ width: "100%", maxHeight: 360 }} />
        <p>Убедитесь, что вас видно и слышно. Если звука нет, проверьте микрофон и сделайте новую пробу.</p>
      </section>}
    </main>
  );
}
