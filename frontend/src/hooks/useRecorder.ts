import { useRef } from "react";
import { TrackKind } from "../api/client";

interface Callbacks {
  onStart: () => void;
  onChunk: (kind: TrackKind, chunk: Blob) => void;
  onComplete: (duration: number) => void;
  onError: () => void;
}

export function useRecorder() {
  const current = useRef<MediaRecorder[]>([]);
  const dispose = () => {
    current.current.forEach((recorder) => {
      recorder.onstart = recorder.onstop = recorder.onerror = recorder.ondataavailable = null;
      if (recorder.state !== "inactive") recorder.stop();
    });
    current.current = [];
  };
  const start = (stream: MediaStream, callbacks: Callbacks) => {
    let started = 0;
    let stopped = 0;
    let startedAt = 0;
    const kinds: TrackKind[] = ["video", "audio"];
    try {
      current.current = kinds.map((kind) => new MediaRecorder(new MediaStream(
        kind === "video" ? stream.getVideoTracks() : stream.getAudioTracks(),
      ), kind === "video" ? { videoBitsPerSecond: 1500000 } : { audioBitsPerSecond: 64000 }));
      current.current.forEach((recorder, index) => {
        recorder.onstart = () => {
          if (++started === 2) { startedAt = Date.now(); callbacks.onStart(); }
        };
        recorder.ondataavailable = (event) => {
          if (event.data.size) callbacks.onChunk(kinds[index], new Blob([event.data], { type: recorder.mimeType }));
        };
        recorder.onstop = () => {
          if (++stopped === 2) callbacks.onComplete(Math.max(1, Math.ceil((Date.now() - startedAt) / 1000)));
        };
        recorder.onerror = () => { dispose(); callbacks.onError(); };
        recorder.start(1000);
      });
    } catch (error) { dispose(); throw error; }
  };
  const stop = () => current.current.forEach((recorder) => { if (recorder.state === "recording") recorder.stop(); });
  return { start, stop, dispose };
}
