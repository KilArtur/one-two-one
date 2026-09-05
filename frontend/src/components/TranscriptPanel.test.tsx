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
it("opens the transcript from the card and keeps the resume separate", async () => {
  vi.mocked(api.getResultCard).mockResolvedValue({ candidate_id: "c", topics: [], recommendation: "additional_check", recommendation_reason: "mandatory_needs_check", confirmed_count: 0, needs_check_count: 1, not_confirmed_count: 0, mandatory_coverage: null, desired_coverage: null, resume_text: "Заявлено: 10 лет Python" });
  vi.mocked(api.getTranscripts).mockResolvedValue([answer]);
  render(
    <MemoryRouter>
      <CandidateResultPage token="token" candidateId="c" />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Открыть полный транскрипт" }));
  expect(await screen.findByRole("article", { name: "Ответ: Опыт Python?" })).toBeTruthy();
  const resume = screen.getByRole("region", { name: "Заявлено в резюме" });
  expect(resume.querySelector("mark")).toBeNull();
  expect(within(resume).getByText("Заявлено: 10 лет Python")).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "Транскрипт интервью" })).queryByText("Заявлено: 10 лет Python")).toBeNull();
});
it("explains missing transcripts and flags interrupted or skipped answers", () => {
  render(<TranscriptContent answers={[{ ...answer, transcript: null, segments: [], skipped: true, technically_lost: true, processing_status: "error" }]} />);
  expect(screen.getByText("Вопрос пропущен кандидатом.")).toBeTruthy();
  expect(screen.getByText("Ответ пострадал из-за технического сбоя.")).toBeTruthy();
  expect(screen.getByText("Транскрибация не удалась.")).toBeTruthy();
});
