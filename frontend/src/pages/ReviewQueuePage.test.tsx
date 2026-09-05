// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { ReviewQueuePage } from "./ReviewQueuePage";

vi.mock("../api/client");
afterEach(cleanup);
const item: api.ReviewItem = { assessment_id: "assessment", candidate_id: "candidate", topic_id: "topic", topic_title: "Python", skill_type: "hard", confidence: "low", current_status: "needs_check", reasoning_summary: "Неясен личный вклад" };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getInternalUser).mockResolvedValue({ username: "expert", role: "technical_specialist" });
  vi.mocked(api.getReviewQueue).mockResolvedValue([item]);
  vi.mocked(api.getTranscripts).mockResolvedValue([{ answer_id: "answer", question_id: "q", topic_id: "topic", question: "Что сделали лично?", transcript: "Я сделал сервис", segments: [], quotes: ["Я сделал"], processing_status: "ready", skipped: false, technically_lost: false }]);
  vi.mocked(api.getEvidence).mockResolvedValue([{ answer_id: "answer", question_id: "q", question: "Что сделали лично?", quote: "Я сделал", start_sec: null, end_sec: null, video_available: false }]);
  vi.mocked(api.changeAssessmentStatus).mockResolvedValue();
  vi.mocked(api.getResultCard).mockResolvedValue({ candidate_id: "candidate", topics: [{ topic_id: "topic", topic_title: "Python", skill_type: "hard", importance: "mandatory", current_status: "confirmed", system_status: "needs_check", author: "technical_specialist", reasoning_summary: null }], recommendation: "fit", recommendation_reason: "all_mandatory_confirmed", confirmed_count: 1, needs_check_count: 0, not_confirmed_count: 0, mandatory_coverage: 1, desired_coverage: null, resume_text: null });
});
it("shows context, requires a nonblank comment and refreshes the result after saving", async () => {
  render(<ReviewQueuePage token="token" />);
  fireEvent.click(await screen.findByRole("button", { name: "Python · hard" }));
  expect(screen.getByText("Неясен личный вклад")).toBeTruthy();
  expect(await screen.findByRole("article", { name: "Ответ: Что сделали лично?" })).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "Evidence топика" })).getByText("Я сделал")).toBeTruthy();
  const save = screen.getByRole<HTMLButtonElement>("button", { name: "Сохранить статус" });
  const comment = screen.getByLabelText("Комментарий эксперта (обязательно)");
  fireEvent.change(comment, { target: { value: "   " } });
  expect(save.disabled).toBe(true);
  fireEvent.change(comment, { target: { value: "Проверил видео" } });
  fireEvent.change(screen.getByLabelText("Новый статус"), { target: { value: "confirmed" } });
  vi.mocked(api.getReviewQueue).mockResolvedValue([]);
  fireEvent.click(save);
  await screen.findByText("Статус сохранён.");
  expect(api.changeAssessmentStatus).toHaveBeenCalledWith("token", "assessment", "confirmed", "Проверил видео");
  expect(await screen.findByText("Нет топиков, требующих проверки.")).toBeTruthy();
  expect(await screen.findByText("✅ подтверждено")).toBeTruthy();
  expect(api.getResultCard).toHaveBeenCalledWith("token", "candidate", expect.any(AbortSignal), undefined);
});
it("retains the form on failed save and does not refresh the card prematurely", async () => {
  vi.mocked(api.changeAssessmentStatus).mockRejectedValue(new Error("Ошибка сохранения"));
  render(<ReviewQueuePage token="token" />);
  fireEvent.click(await screen.findByRole("button", { name: "Python · hard" }));
  fireEvent.change(screen.getByLabelText("Комментарий эксперта (обязательно)"), { target: { value: "Проверил" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить статус" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.queryByText("Статус сохранён.")).toBeNull();
  expect(api.getResultCard).not.toHaveBeenCalled();
});
it("explains recruiter restrictions without requesting an expert queue", async () => {
  vi.mocked(api.getInternalUser).mockResolvedValue({ username: "recruiter", role: "recruiter" });
  render(<ReviewQueuePage token="token" />);
  await screen.findByText(/Рекрутер не меняет статусы/);
  expect(api.getReviewQueue).not.toHaveBeenCalled();
  expect(screen.queryByRole("combobox")).toBeNull();
});
it("labels the hiring manager queue and allows loading retry", async () => {
  vi.mocked(api.getInternalUser).mockResolvedValue({ username: "manager", role: "hiring_manager" });
  vi.mocked(api.getReviewQueue).mockRejectedValueOnce(new Error("Нет сети")).mockResolvedValue([{ ...item, skill_type: "soft", topic_title: "Коммуникация" }]);
  render(<ReviewQueuePage token="token" />);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Повторить загрузку очереди" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Коммуникация · soft" })).toBeTruthy());
  expect(screen.getByText("Soft-топики · нанимающий менеджер")).toBeTruthy();
});
