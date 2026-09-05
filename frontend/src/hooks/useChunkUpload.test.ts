import { beforeEach, expect, it, vi } from "vitest";
import { answerUploadApi, UploadRequestError } from "../api/client";
import { ChunkUploadQueue } from "./useChunkUpload";

vi.mock("../api/client", async (original) => ({
  ...await original<typeof import("../api/client")>(),
  answerUploadApi: { start: vi.fn(), chunk: vi.fn(), complete: vi.fn() },
}));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(answerUploadApi.start).mockResolvedValue({ id: "upload", video_chunks: 0, audio_chunks: 0, saved: false });
  vi.mocked(answerUploadApi.chunk).mockResolvedValue({ index: 0 });
  vi.mocked(answerUploadApi.complete).mockResolvedValue({ id: "answer", question_id: "question", duration_sec: 3, processing_status: "recorded" });
});

it("sends sequential chunks during recording and waits for all acknowledgements before completion", async () => {
  const notify = vi.fn();
  const queue = new ChunkUploadQueue("token", "question", notify);
  await queue.begin();
  let release!: () => void;
  vi.mocked(answerUploadApi.chunk).mockImplementationOnce(() => new Promise((resolve) => { release = () => resolve({ index: 0 }); }));
  queue.enqueue("video", new Blob(["v0"]));
  queue.enqueue("audio", new Blob(["a0"]));
  queue.enqueue("video", new Blob(["v1"]));
  expect(answerUploadApi.chunk).toHaveBeenCalledTimes(1);
  expect(answerUploadApi.complete).not.toHaveBeenCalled();
  const finished = queue.finish(3);
  expect(answerUploadApi.complete).not.toHaveBeenCalled();
  release();
  await finished;
  expect(vi.mocked(answerUploadApi.chunk).mock.calls.map((args) => [args[2], args[3]])).toEqual([["video", 0], ["audio", 0], ["video", 1]]);
  expect(answerUploadApi.complete).toHaveBeenCalledWith("token", "upload", 2, 1, 3, expect.any(AbortSignal));
  expect(notify.mock.lastCall?.[0].status).toBe("saved");
});

it("keeps failed chunks for retry and never claims success before the server commits", async () => {
  const notify = vi.fn();
  const queue = new ChunkUploadQueue("token", "question", notify);
  await queue.begin();
  vi.mocked(answerUploadApi.chunk).mockRejectedValueOnce(new UploadRequestError("failed", false));
  queue.enqueue("video", new Blob(["v0"]));
  queue.enqueue("audio", new Blob(["a0"]));
  await queue.finish(3);
  expect(notify.mock.lastCall?.[0].status).toBe("error");
  expect(answerUploadApi.complete).not.toHaveBeenCalled();
  await queue.retry();
  expect(vi.mocked(answerUploadApi.chunk).mock.calls.map((args) => [args[2], args[3]])).toEqual([["video", 0], ["video", 0], ["audio", 0]]);
  expect(notify.mock.lastCall?.[0].status).toBe("saved");
});

it("retries finalization without sending successful chunks again", async () => {
  const notify = vi.fn();
  const queue = new ChunkUploadQueue("token", "question", notify);
  await queue.begin();
  queue.enqueue("video", new Blob(["v"])); queue.enqueue("audio", new Blob(["a"]));
  vi.mocked(answerUploadApi.complete).mockRejectedValueOnce(new UploadRequestError("failed", false));
  await queue.finish(3);
  expect(notify.mock.lastCall?.[0].status).toBe("error");
  await queue.retry();
  expect(answerUploadApi.chunk).toHaveBeenCalledTimes(2);
  expect(answerUploadApi.complete).toHaveBeenCalledTimes(2);
  expect(notify.mock.lastCall?.[0].status).toBe("saved");
});

it("rejects restarting an existing recording", async () => {
  vi.mocked(answerUploadApi.start).mockResolvedValue({ id: "upload", video_chunks: 1, audio_chunks: 0, saved: false });
  await expect(new ChunkUploadQueue("token", "question", vi.fn()).begin()).rejects.toThrow("Перезапись");
});

it("splits a delayed recorder event into chunks within the server limit", async () => {
  const queue = new ChunkUploadQueue("token", "question", vi.fn());
  await queue.begin();
  const maxBytes = 8 * 1024 * 1024;
  queue.enqueue("video", new Blob([new Uint8Array(maxBytes + 17)], { type: "video/webm" }));
  queue.enqueue("audio", new Blob(["audio"], { type: "audio/webm" }));
  await queue.finish(3);
  const video = vi.mocked(answerUploadApi.chunk).mock.calls.filter((args) => args[2] === "video");
  expect(video.map((args) => [args[3], args[4].size, args[4].type])).toEqual([
    [0, maxBytes, "video/webm"], [1, 17, "video/webm"],
  ]);
  expect(answerUploadApi.complete).toHaveBeenCalledWith("token", "upload", 2, 1, 3, expect.any(AbortSignal));
});
