import { afterEach, expect, it, vi } from "vitest";
import { getAnswerMedia, getEvidence, getResultCard, getTranscripts, recordVideoView } from "./client";

afterEach(() => vi.unstubAllGlobals());
it("attaches link scope to every shared result data request", async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal("fetch", fetcher);
  await getResultCard("jwt", "candidate", undefined, "secret");
  await getEvidence("jwt", "candidate", "topic", undefined, "secret");
  await getAnswerMedia("jwt", "candidate", "answer", undefined, "secret");
  await getTranscripts("jwt", "candidate", undefined, undefined, "secret");
  await recordVideoView("jwt", "candidate", "answer", "event", 2, "secret");
  expect(fetcher).toHaveBeenCalledTimes(5);
  for (const [, options] of fetcher.mock.calls) {
    expect(options.headers.Authorization).toBe("Bearer jwt");
    expect(options.headers["X-Result-Link"]).toBe("secret");
  }
});
