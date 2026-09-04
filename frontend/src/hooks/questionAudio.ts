/** Подключает MP3-поток к плееру, в браузерах без MSE использует Blob. */
export async function attachQuestionAudio(
  player: HTMLAudioElement, response: Response, signal: AbortSignal,
  rememberUrl: (url: string) => void,
): Promise<void> {
  if (typeof MediaSource === "undefined" || !MediaSource.isTypeSupported("audio/mpeg") || !response.body) {
    const blob = await response.blob();
    if (signal.aborted) return;
    if (!blob.size) throw new Error("Получена пустая озвучка.");
    const url = URL.createObjectURL(blob);
    rememberUrl(url);
    player.src = url;
    return;
  }
  const media = new MediaSource();
  const opened = new Promise<void>((resolve, reject) => {
    media.addEventListener("sourceopen", () => resolve(), { once: true });
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  });
  const url = URL.createObjectURL(media);
  rememberUrl(url);
  player.src = url;
  await opened;
  const buffer = media.addSourceBuffer("audio/mpeg");
  const reader = response.body.getReader();
  let received = false;
  try {
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      if (!value.byteLength) continue;
      received = true;
      await new Promise<void>((resolve, reject) => {
        const clear = () => {
          buffer.removeEventListener("updateend", success);
          buffer.removeEventListener("error", failure);
          signal.removeEventListener("abort", failure);
        };
        const success = () => { clear(); resolve(); };
        const failure = () => { clear(); reject(new Error("Не удалось загрузить озвучку.")); };
        buffer.addEventListener("updateend", success, { once: true });
        buffer.addEventListener("error", failure, { once: true });
        signal.addEventListener("abort", failure, { once: true });
        try { buffer.appendBuffer(value); } catch (error) { clear(); reject(error); }
      });
    }
    if (!signal.aborted) {
      if (!received) throw new Error("Получена пустая озвучка.");
      media.endOfStream();
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
