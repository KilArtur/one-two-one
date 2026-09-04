// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { EquipmentCheck } from "./EquipmentCheck";

class Track extends EventTarget {
  readyState = "live";
  muted = false;
  stop = vi.fn(() => { this.readyState = "ended"; });
}

class Recorder {
  static instances: Recorder[] = [];
  state = "inactive";
  mimeType = "video/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public stream: unknown) { Recorder.instances.push(this); }
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["test video"], { type: this.mimeType }) });
    this.onstop?.();
  }
}

let audio: Track;
let video: Track;
let media: { getTracks: () => Track[]; getAudioTracks: () => Track[]; getVideoTracks: () => Track[] };
let getUserMedia: ReturnType<typeof vi.fn>;

beforeEach(() => {
  audio = new Track();
  video = new Track();
  media = { getTracks: () => [audio, video], getAudioTracks: () => [audio], getVideoTracks: () => [video] };
  getUserMedia = vi.fn().mockResolvedValue(media);
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  vi.stubGlobal("MediaRecorder", Recorder);
  Recorder.instances = [];
  URL.createObjectURL = vi.fn().mockReturnValue("blob:test-recording");
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function connected() {
  render(<EquipmentCheck />);
  await waitFor(() => expect((screen.getByRole("button", { name: "Записать 3 секунды" }) as HTMLButtonElement).disabled).toBe(false));
}

it("requests both devices and shows a muted live preview", async () => {
  await connected();
  expect(getUserMedia).toHaveBeenCalledWith({ video: true, audio: true });
  const preview = screen.getByLabelText("Изображение с камеры") as HTMLVideoElement;
  expect(preview.srcObject).toBe(media);
  expect(preview.muted).toBe(true);
});

it("records for three seconds and offers playback with sound", async () => {
  await connected();
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Записать 3 секунды" }));
  expect(Recorder.instances[0].stream).toBe(media);
  expect(screen.getByRole("status").textContent).toContain("Идёт тестовая запись");
  act(() => { vi.advanceTimersByTime(2999); });
  expect(screen.queryByLabelText("Тестовая запись")).toBeNull();
  act(() => { vi.advanceTimersByTime(1); });
  const playback = screen.getByLabelText("Тестовая запись") as HTMLVideoElement;
  expect(playback.src).toBe("blob:test-recording");
  expect(playback.controls).toBe(true);
  expect(playback.muted).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Записать пробу заново" }));
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:test-recording");
});

it.each(["ended", "mute"])("blocks recording when the microphone emits %s", async (event) => {
  await connected();
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Записать 3 секунды" }));
  act(() => { audio.dispatchEvent(new Event(event)); });
  expect(screen.getByRole("alert").textContent).toContain("отключены");
  expect((screen.getByRole("button", { name: "Записать 3 секунды" }) as HTMLButtonElement).disabled).toBe(true);
  act(() => { vi.advanceTimersByTime(3000); });
  expect(screen.queryByLabelText("Тестовая запись")).toBeNull();
  expect(video.stop).toHaveBeenCalled();
});

it.each(["NotAllowedError", "NotFoundError", "NotReadableError"])("explains %s and allows retry", async (name) => {
  getUserMedia.mockRejectedValueOnce(new DOMException("failure", name));
  render(<EquipmentCheck />);
  await screen.findByRole("alert");
  expect((screen.getByRole("button", { name: "Записать 3 секунды" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Повторить проверку устройств" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Записать 3 секунды" }) as HTMLButtonElement).disabled).toBe(false));
});

it("rejects a stream without a microphone", async () => {
  media.getAudioTracks = () => [];
  render(<EquipmentCheck />);
  await screen.findByRole("alert");
  expect(video.stop).toHaveBeenCalled();
});

it("stops tracks and a recording on unmount", async () => {
  await connected();
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Записать 3 секунды" }));
  cleanup();
  expect(audio.stop).toHaveBeenCalled();
  expect(video.stop).toHaveBeenCalled();
  expect(Recorder.instances[0].state).toBe("inactive");
  act(() => { vi.advanceTimersByTime(3000); });
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});

it("stops tracks if permission resolves after leaving the page", async () => {
  let finish!: (value: typeof media) => void;
  getUserMedia.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  render(<EquipmentCheck />);
  cleanup();
  await act(async () => { finish(media); });
  expect(audio.stop).toHaveBeenCalled();
  expect(video.stop).toHaveBeenCalled();
});

it("handles unsupported browsers", async () => {
  vi.stubGlobal("MediaRecorder", undefined);
  render(<EquipmentCheck />);
  expect((await screen.findByRole("alert")).textContent).toContain("не поддерживает");
  expect(getUserMedia).not.toHaveBeenCalled();
});

it("handles recorder errors without offering broken playback", async () => {
  await connected();
  fireEvent.click(screen.getByRole("button", { name: "Записать 3 секунды" }));
  act(() => { Recorder.instances[0].onerror?.(); });
  expect(screen.getByRole("alert").textContent).toContain("Не удалось записать");
  expect(screen.queryByLabelText("Тестовая запись")).toBeNull();
});
