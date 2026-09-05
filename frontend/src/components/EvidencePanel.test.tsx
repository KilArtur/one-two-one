// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { EvidencePanel } from "./EvidencePanel";

vi.mock("../api/client");
afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  vi.mocked(api.getEvidence).mockResolvedValue([{ answer_id: "answer", question_id: "q", question: "Опыт?", quote: "Делал сам", start_sec: 12, end_sec: 16, video_available: true }]);
  vi.mocked(api.getAnswerMedia).mockResolvedValue({ video_url: "https://media/video", audio_url: "https://media/audio" });
  vi.mocked(api.recordVideoView).mockResolvedValue({});
});

it("highlights the quote, seeks on metadata and logs only actual playback", async () => {
  render(<EvidencePanel token="token" candidateId="candidate" topicId="topic" />);
  const video = await screen.findByLabelText<HTMLVideoElement>("Видео ответа");
  expect(screen.getByText("Делал сам").tagName).toBe("MARK");
  fireEvent.loadedMetadata(video);
  expect(video.currentTime).toBe(12);
  expect(api.recordVideoView).not.toHaveBeenCalled();
  fireEvent.playing(video);
  await waitFor(() => expect(api.recordVideoView).toHaveBeenCalledTimes(1));
  expect(api.recordVideoView).toHaveBeenCalledWith("token", "candidate", "answer", expect.any(String), 12, undefined);
  fireEvent.playing(video);
  expect(api.recordVideoView).toHaveBeenCalledTimes(1);
  fireEvent.play(video); fireEvent.playing(video);
  await waitFor(() => expect(api.recordVideoView).toHaveBeenCalledTimes(2));
  expect(vi.mocked(api.recordVideoView).mock.calls[0][3]).not.toBe(vi.mocked(api.recordVideoView).mock.calls[1][3]);
  const audio = document.querySelector("audio")!;
  expect(audio.currentTime).toBe(12);
  video.currentTime = 15; fireEvent.seeked(video);
  expect(audio.currentTime).toBe(15);
  video.volume = 0.4; video.muted = true; fireEvent.volumeChange(video);
  expect(audio.volume).toBe(0.4);
  expect(audio.muted).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "К фрагменту 12 с" }));
  const next = await screen.findByLabelText<HTMLVideoElement>("Видео ответа");
  fireEvent.loadedMetadata(next);
  expect(next.currentTime).toBe(12);
});

it("pauses on audit failure and retries without claiming successful logging", async () => {
  vi.mocked(api.recordVideoView).mockRejectedValueOnce(new Error("network"));
  render(<EvidencePanel token="token" candidateId="candidate" topicId="topic" />);
  const video = await screen.findByLabelText("Видео ответа");
  fireEvent.playing(video);
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled();
  fireEvent.playing(video);
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(api.recordVideoView).toHaveBeenCalledTimes(2);
});

it("keeps the quote available when media or timestamps are missing", async () => {
  vi.mocked(api.getEvidence).mockResolvedValue([{ answer_id: "answer", question_id: "q", question: "Опыт?", quote: "Делал сам", start_sec: null, end_sec: null, video_available: false }]);
  render(<EvidencePanel token="token" candidateId="candidate" topicId="topic" />);
  expect(await screen.findByText("Делал сам")).toBeTruthy();
  expect(screen.queryByLabelText("Видео ответа")).toBeNull();
  expect(api.getAnswerMedia).not.toHaveBeenCalled();
});
