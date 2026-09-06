// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { TranscriptContent, quoteRanges } from "./TranscriptPanel";
import { CandidateResultPage } from "../pages/CandidateResultPage";

vi.mock("../api/client");
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const answer: api.TranscriptAnswer = {
  answer_id: "a", question_id: "q", topic_id: "t", question: "Опыт Python?",
  transcript: "В начале. Я использовал Python в сервисе.",
  segments: [{ text: "В начале.", start: 0, end: 2 }, { text: "Я использовал", start: 2, end: 4 }, { text: "Python в сервисе.", start: 4, end: 7 }],
  quotes: ["Я использовал Python"], processing_status: "ready", skipped: false, technically_lost: false,
};
it("highlights quotes across segment boundaries without rewriting the text", () => {
  render(<TranscriptContent answers={[answer]} />);
  const list = screen.getByRole("list");
  expect(within(list).getAllByRole("listitem")).toHaveLength(3);
  expect(within(list).getByText("0:02–0:04")).toBeTruthy();
  expect(Array.from(list.querySelectorAll("mark")).map((m) => m.textContent)).toEqual(["Я использовал", "Python"]);
  expect(within(list).getByText("В начале.").tagName).not.toBe("MARK");
});
it("merges repeated overlapping quotes and treats markup as text", () => {
  expect(quoteRanges("one   two one", ["one two", "two", "one", "unmatched"])).toEqual([{ start: 0, end: 9 }, { start: 10, end: 13 }]);
  render(<TranscriptContent answers={[{ ...answer, segments: [], transcript: "<script>alert(1)</script>", quotes: ["<script>"] }]} />);
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getByText("<script>").tagName).toBe("MARK");
});
it("opens the transcript from the card without a resume block", async () => {
  vi.mocked(api.getResultCard).mockResolvedValue({
    candidate_id: "c",
    full_name: "Иван Петров",
    topics: [],
    recommendation: "additional_check",
    recommendation_reason: "mandatory_needs_check",
    confirmed_count: 0,
    needs_check_count: 1,
    not_confirmed_count: 0,
    mandatory_coverage: null,
    desired_coverage: null,
    resume_text: "Заявлено: 10 лет Python",
  });
  vi.mocked(api.getTranscripts).mockResolvedValue([answer]);
  vi.mocked(api.getAnswerMedia).mockResolvedValue({
    video_url: "https://media/video",
    audio_url: null,
  });
  render(
    <MemoryRouter>
      <CandidateResultPage token="token" candidateId="c" />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Открыть полный транскрипт" }));
  expect(await screen.findByRole("article", { name: "Ответ: Опыт Python?" })).toBeTruthy();
  expect(screen.queryByRole("region", { name: "Заявлено в резюме" })).toBeNull();
  expect(screen.queryByText("Заявлено: 10 лет Python")).toBeNull();
  expect(await screen.findByLabelText("Видео ответа")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Смотреть запись" })).toBeNull();
});
it("keeps global question numbers when filtered by topic", () => {
  const first = { ...answer, answer_id: "a1", question_id: "q1", topic_id: "t1", question: "Первый?" };
  const second = { ...answer, answer_id: "a2", question_id: "q2", topic_id: "t2", question: "Второй?" };
  render(<TranscriptContent answers={[first, second]} topicId="t2" />);
  expect(screen.getByText("Вопрос 2")).toBeTruthy();
  expect(screen.getByText("Второй?")).toBeTruthy();
  expect(screen.queryByText("Первый?")).toBeNull();
});
it("explains missing transcripts and flags interrupted or skipped answers", () => {
  render(
    <TranscriptContent
      answers={[{ ...answer, transcript: null, segments: [], skipped: true, technically_lost: true, processing_status: "error" }]}
      token="token"
      candidateId="c"
    />,
  );
  expect(screen.getByText("Вопрос пропущен кандидатом.")).toBeTruthy();
  expect(screen.getByText("Ответ пострадал из-за технического сбоя.")).toBeTruthy();
  expect(screen.getByText("Транскрибация не удалась.")).toBeTruthy();
});
