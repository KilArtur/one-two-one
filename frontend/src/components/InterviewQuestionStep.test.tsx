// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { getQuestionAudio, InterviewQuestion } from "../api/client";
import { InterviewQuestionStep } from "./InterviewQuestionStep";

vi.mock("../api/client", () => ({ getQuestionAudio: vi.fn() }));
vi.mock("../hooks/questionAudio", () => ({ attachQuestionAudio: vi.fn().mockResolvedValue(undefined) }));

class Track extends EventTarget {
  readyState = "live";
  muted = false;
  stop = vi.fn(() => { this.readyState = "ended"; });
}
class Recorder {
  static instances: Recorder[] = [];
  state = "inactive";
  mimeType = "video/webm";
  onstart: (() => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  constructor() { Recorder.instances.push(this); }
  start() { this.state = "recording"; this.onstart?.(); }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["answer"]) });
    this.onstop?.();
  }
}
let mic: Track;
let camera: Track;
const completed = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  mic = new Track(); camera = new Track(); Recorder.instances = [];
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue({
    getTracks: () => [mic, camera], getAudioTracks: () => [mic], getVideoTracks: () => [camera],
  }) } });
  vi.stubGlobal("MediaRecorder", Recorder);
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
  vi.mocked(getQuestionAudio).mockResolvedValue(new Response("audio"));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

async function open(type: InterviewQuestion["type"] = "core") {
  render(<InterviewQuestionStep token="session" question={{ id: "question", text: "Вопрос?", type }} onRecorded={completed} />);
  await waitFor(() => expect(getQuestionAudio).toHaveBeenCalled());
  return screen.getByLabelText("Озвучка вопроса");
}

it.each([["core", 120], ["personal", 120], ["follow_up", 60]] as const)("starts %s recording only after speech ends and stops at %i seconds", async (type, seconds) => {
  const player = await open(type);
  vi.useFakeTimers();
  fireEvent.canPlay(player);
  act(() => { vi.advanceTimersByTime(10000); });
  expect(Recorder.instances).toHaveLength(0);
  expect(screen.getByRole("timer").textContent).toBe(seconds === 120 ? "2:00" : "1:00");
  fireEvent.ended(player);
  expect(Recorder.instances).toHaveLength(1);
  expect(screen.getByRole("status").textContent).toContain("REC");
  fireEvent.ended(player);
  expect(Recorder.instances).toHaveLength(1);
  act(() => { vi.advanceTimersByTime((seconds - 1) * 1000); });
  expect(screen.getByRole("timer").textContent).toBe("0:01");
  expect(completed).not.toHaveBeenCalled();
  act(() => { vi.advanceTimersByTime(1000); });
  expect(screen.getByRole("timer").textContent).toBe("0:00");
  expect(screen.getByRole("status").textContent).not.toContain("REC");
  expect(completed).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("button", { name: "Повторить озвучку" })).toBeNull();
});

it("does not spend answer time while autoplay is blocked", async () => {
  vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValueOnce(new Error("autoplay"));
  const player = await open();
  fireEvent.canPlay(player);
  const play = await screen.findByRole("button", { name: "Прослушать вопрос" });
  expect(Recorder.instances).toHaveLength(0);
  fireEvent.click(play);
  await waitFor(() => expect(screen.queryByRole("button", { name: "Прослушать вопрос" })).toBeNull());
  expect(Recorder.instances).toHaveLength(0);
});

it("keeps the timer stopped on TTS failure", async () => {
  vi.mocked(getQuestionAudio).mockRejectedValueOnce(new Error("TTS unavailable"));
  await open();
  await screen.findByRole("alert");
  expect(Recorder.instances).toHaveLength(0);
  expect(screen.getByRole("timer").textContent).toBe("2:00");
  expect(screen.getByRole("button", { name: "Повторить озвучку" })).toBeTruthy();
});

it("stops and removes REC when the microphone disconnects", async () => {
  const player = await open();
  fireEvent.ended(player);
  act(() => { mic.dispatchEvent(new Event("ended")); });
  expect(screen.getByRole("alert").textContent).toContain("отключены");
  expect(screen.getByRole("status").textContent).not.toContain("REC");
  expect(completed).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Повторить озвучку" })).toBeNull();
});

it("finishes early without permitting a second recording", async () => {
  const player = await open();
  fireEvent.ended(player);
  fireEvent.click(screen.getByRole("button", { name: "Закончить ответ" }));
  expect(completed).toHaveBeenCalledTimes(1);
  fireEvent.ended(player);
  expect(Recorder.instances).toHaveLength(1);
});

it("uses a deadline instead of counting timer ticks", async () => {
  const player = await open();
  vi.useFakeTimers();
  fireEvent.ended(player);
  vi.setSystemTime(Date.now() + 125000);
  act(() => { vi.advanceTimersByTime(250); });
  expect(completed).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("timer").textContent).toBe("0:00");
});

it("cleans up devices and timers on navigation", async () => {
  const player = await open();
  vi.useFakeTimers();
  fireEvent.ended(player);
  cleanup();
  act(() => { vi.advanceTimersByTime(120000); });
  expect(mic.stop).toHaveBeenCalled();
  expect(camera.stop).toHaveBeenCalled();
  expect(completed).not.toHaveBeenCalled();
});
