import { useEffect, useMemo, useState } from "react";

import { answerUploadApi, SavedAnswer, TrackKind, UploadRequestError } from "../api/client";

type UploadState = { status: "idle" | "uploading" | "saving" | "error" | "saved"; error?: string; answer?: SavedAnswer };
type Chunk = { kind: TrackKind; index: number; blob: Blob };

export class ChunkUploadQueue {
  private id: string | null = null;
  private requestId = crypto.randomUUID();
  private queue: Chunk[] = [];
  private counts = { video: 0, audio: 0 };
  private running: Promise<void> | null = null;
  private failed = false;
  private duration: number | null = null;
  private controller = new AbortController();
  private completed = false;

  constructor(private token: string, private questionId: string, private notify: (state: UploadState) => void) {}

  private async request<T>(operation: () => Promise<T>): Promise<T> {
    const signal = this.controller.signal;
    for (let attempt = 0; ; attempt++) {
      if (signal.aborted) throw new DOMException("Aborted", "AbortError");
      try {
        const result = await operation();
        if (signal.aborted) throw new DOMException("Aborted", "AbortError");
        return result;
      }
      catch (error) {
        if (signal.aborted || attempt >= 2 || !(error instanceof UploadRequestError) || !error.retryable) throw error;
        await new Promise((resolve) => setTimeout(resolve, 300 * 2 ** attempt));
      }
    }
  }

  async begin(): Promise<void> {
    if (this.id) return;
    const session = await this.request(() => answerUploadApi.start(this.token, this.questionId, this.controller.signal, this.requestId));
    if (session.saved || session.video_chunks || session.audio_chunks) {
      throw new Error("Для этого вопроса уже есть запись. Перезапись недоступна; обратитесь к рекрутеру.");
    }
    this.id = session.id;
  }

  enqueue(kind: TrackKind, blob: Blob): void {
    if (!blob.size || this.controller.signal.aborted) return;
    const maxBytes = 8 * 1024 * 1024;
    for (let offset = 0; offset < blob.size; offset += maxBytes) {
      this.queue.push({ kind, index: this.counts[kind]++, blob: blob.slice(offset, offset + maxBytes, blob.type) });
    }
    if (!this.failed) void this.drain().catch(() => undefined);
  }

  private drain(): Promise<void> {
    if (this.running) return this.running;
    this.running = (async () => {
      while (this.queue.length && !this.controller.signal.aborted) {
        const part = this.queue[0];
        this.notify({ status: "uploading" });
        await this.request(() => answerUploadApi.chunk(this.token, this.id!, part.kind, part.index, part.blob, this.controller.signal));
        this.queue.shift();
      }
    })().catch((error) => {
      this.failed = true;
      if (!this.controller.signal.aborted) this.notify({ status: "error", error: error instanceof Error ? error.message : "Ошибка загрузки" });
      throw error;
    }).finally(() => { this.running = null; });
    return this.running;
  }

  async finish(duration: number): Promise<void> {
    this.duration = duration;
    if (this.completed || this.controller.signal.aborted) return;
    try {
      if (this.failed) return;
      await this.drain();
      if (this.controller.signal.aborted) return;
      this.notify({ status: "saving" });
      const answer = await this.request(() => answerUploadApi.complete(this.token, this.id!, this.counts.video, this.counts.audio, duration, this.controller.signal));
      this.completed = true;
      this.notify({ status: "saved", answer });
    } catch (error) {
      this.failed = true;
      if (!this.controller.signal.aborted) this.notify({ status: "error", error: error instanceof Error ? error.message : "Ошибка сохранения" });
    }
  }

  async retry(): Promise<void> {
    if (this.running || this.completed) return;
    this.failed = false;
    try {
      await this.drain();
      if (this.duration !== null) await this.finish(this.duration);
    } catch { return; }
  }

  activate(): void { if (this.controller.signal.aborted) this.controller = new AbortController(); }

  dispose(): void { this.controller.abort(); this.queue = []; }
}

export function useChunkUpload(token: string, questionId: string) {
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const queue = useMemo(() => new ChunkUploadQueue(token, questionId, setState), [token, questionId]);
  useEffect(() => { queue.activate(); return () => queue.dispose(); }, [queue]);
  return { queue, ...state };
}
