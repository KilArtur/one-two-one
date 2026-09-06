// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { ReviewQueuePage } from "./ReviewQueuePage";

vi.mock("../api/client");
afterEach(cleanup);

function renderQueue() {
  return render(
    <MemoryRouter>
      <ReviewQueuePage token="token" />
    </MemoryRouter>,
  );
}

const item: api.ReviewItem = {
  assessment_id: "assessment",
  candidate_id: "candidate",
  topic_id: "topic",
  topic_title: "Python",
  skill_type: "hard",
  confidence: "low",
  current_status: "needs_check",
  reasoning_summary: "Неясен личный вклад",
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getInternalUser).mockResolvedValue({ username: "expert", role: "technical_specialist" });
  vi.mocked(api.getReviewQueue).mockResolvedValue([item]);
  vi.mocked(api.getTranscripts).mockResolvedValue([
    {
      answer_id: "answer",
      question_id: "q",
      topic_id: "topic",
      question: "Что сделали лично?",
      transcript: "Я сделал сервис",
      segments: [],
      quotes: ["Я сделал"],
      processing_status: "ready",
      skipped: false,
      technically_lost: false,
    },
  ]);
  vi.mocked(api.getEvidence).mockResolvedValue([
    {
      answer_id: "answer",
      question_id: "q",
      question: "Что сделали лично?",
      quote: "Я сделал",
      start_sec: null,
      end_sec: null,
      video_available: false,
    },
  ]);
  vi.mocked(api.getAnswerMedia).mockResolvedValue({
    video_url: "https://media/video",
    audio_url: null,
  });
  vi.mocked(api.changeAssessmentStatus).mockResolvedValue();
  vi.mocked(api.changeTopicStatus).mockResolvedValue();
  vi.mocked(api.getResultCard).mockResolvedValue({
    candidate_id: "candidate",
    full_name: null,
    topics: [
      {
        topic_id: "topic",
        topic_title: "Python",
        skill_type: "hard",
        importance: "mandatory",
        current_status: "confirmed",
        system_status: "needs_check",
        author: "technical_specialist",
        reasoning_summary: null,
        has_evidence: true,
        reviewable: true,
      },
    ],
    recommendation: "fit",
    recommendation_reason: "all_mandatory_confirmed",
    confirmed_count: 1,
    needs_check_count: 0,
    not_confirmed_count: 0,
    mandatory_coverage: 1,
    desired_coverage: null,
    resume_text: null,
    mandatory_confirmed_share: 1,
    desired_confirmed_share: null,
    mandatory_potential_share: 1,
  });
});

it("removes topic from queue after save without status change", async () => {
  renderQueue();
  fireEvent.click(await screen.findByRole("button", { name: "К-candidate: Python · hard" }));
  vi.mocked(api.getReviewQueue).mockResolvedValue([]);
  fireEvent.click(screen.getByRole("button", { name: "Сохранить статус" }));
  await screen.findByText("Статус сохранён.");
  expect(api.changeAssessmentStatus).toHaveBeenCalledWith(
    "token",
    "assessment",
    "needs_check",
    "",
  );
  expect(await screen.findByText("Нет топиков, требующих проверки.")).toBeTruthy();
});

it("shows context, allows an optional comment and refreshes the result after saving", async () => {
  renderQueue();
  fireEvent.click(await screen.findByRole("button", { name: "К-candidate: Python · hard" }));
  expect(screen.getAllByText("Неясен личный вклад").length).toBeGreaterThan(0);
  expect(await screen.findByRole("article", { name: "Ответ: Что сделали лично?" })).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "Evidence топика" })).getByText("Я сделал")).toBeTruthy();
  const save = screen.getByRole<HTMLButtonElement>("button", { name: "Сохранить статус" });
  const comment = screen.getByLabelText("Комментарий эксперта (необязательно)");
  // Комментарий необязателен: кнопка активна даже без текста.
  expect(save.disabled).toBe(false);
  fireEvent.change(comment, { target: { value: "Проверил видео" } });
  fireEvent.change(screen.getByLabelText("Новый статус"), { target: { value: "confirmed" } });
  vi.mocked(api.getReviewQueue).mockResolvedValue([]);
  fireEvent.click(save);
  await screen.findByText("Статус сохранён.");
  expect(api.changeAssessmentStatus).toHaveBeenCalledWith("token", "assessment", "confirmed", "Проверил видео");
  expect(await screen.findByText("Нет топиков, требующих проверки.")).toBeTruthy();
  expect(await screen.findByText("подтверждено")).toBeTruthy();
  expect(api.getResultCard).toHaveBeenCalledWith("token", "candidate", expect.any(AbortSignal), undefined);
});

it("retains the form on failed save and does not refresh the card prematurely", async () => {
  vi.mocked(api.changeAssessmentStatus).mockRejectedValue(new Error("Ошибка сохранения"));
  renderQueue();
  fireEvent.click(await screen.findByRole("button", { name: "К-candidate: Python · hard" }));
  fireEvent.change(screen.getByLabelText("Комментарий эксперта (необязательно)"), { target: { value: "Проверил" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить статус" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.queryByText("Статус сохранён.")).toBeNull();
  expect(api.getResultCard).not.toHaveBeenCalled();
});

it("explains recruiter restrictions without requesting an expert queue", async () => {
  vi.mocked(api.getInternalUser).mockResolvedValue({ username: "recruiter", role: "recruiter" });
  renderQueue();
  await screen.findByText(/Рекрутер не меняет статусы/);
  expect(api.getReviewQueue).not.toHaveBeenCalled();
  expect(screen.queryByRole("combobox")).toBeNull();
});

it("labels the hiring manager queue and allows loading retry", async () => {
  vi.mocked(api.getInternalUser).mockResolvedValue({ username: "manager", role: "hiring_manager" });
  vi.mocked(api.getReviewQueue)
    .mockRejectedValueOnce(new Error("Нет сети"))
    .mockResolvedValue([{ ...item, skill_type: "soft", topic_title: "Коммуникация" }]);
  renderQueue();
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Повторить загрузку очереди" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "К-candidate: Коммуникация · soft" })).toBeTruthy(),
  );
  expect(screen.getByText("Soft-топики · нанимающий менеджер")).toBeTruthy();
});

it("opens matrix from topic detail", async () => {
  renderQueue();
  fireEvent.click(await screen.findByRole("button", { name: "К-candidate: Python · hard" }));
  const detail = screen.getByRole("region", { name: "Контекст ревью" });
  fireEvent.click(within(detail).getByRole("button", { name: "Матрица требований" }));
  expect(
    await screen.findByText("Можно сохранить матрицу как есть или поправить статусы — затем «Сохранить всё»."),
  ).toBeTruthy();
  expect(api.getResultCard).toHaveBeenCalledWith("token", "candidate", expect.any(AbortSignal), undefined);
});

it("groups queue by candidate and opens confirm matrix", async () => {
  renderQueue();
  expect(await screen.findByRole("region", { name: "Кандидат К-candidate" })).toBeTruthy();
  expect(screen.getAllByRole("button", { name: "К-candidate" }).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Матрица требований" }));
  expect(
    await screen.findByText("Можно сохранить матрицу как есть или поправить статусы — затем «Сохранить всё»."),
  ).toBeTruthy();
  expect(api.getResultCard).toHaveBeenCalledWith("token", "candidate", expect.any(AbortSignal), undefined);
  fireEvent.click(screen.getByRole("button", { name: "К очереди кандидатов" }));
  expect(await screen.findByRole("button", { name: "К-candidate: Python · hard" })).toBeTruthy();
});

it("shows saved notice after matrix confirm save", async () => {
  sessionStorage.setItem("internal-role", "technical_specialist");
  vi.mocked(api.changeTopicStatus).mockResolvedValue();
  vi.mocked(api.getResultCard).mockResolvedValue({
    candidate_id: "candidate",
    full_name: null,
    topics: [
      {
        topic_id: "topic",
        topic_title: "Python",
        skill_type: "hard",
        importance: "mandatory",
        current_status: "needs_check",
        system_status: "needs_check",
        author: "system",
        reasoning_summary: null,
        has_evidence: true,
        reviewable: true,
      },
    ],
    recommendation: "additional_check",
    recommendation_reason: "mandatory_needs_check",
    confirmed_count: 0,
    needs_check_count: 1,
    not_confirmed_count: 0,
    mandatory_coverage: null,
    desired_coverage: null,
    resume_text: null,
    mandatory_confirmed_share: 0,
    desired_confirmed_share: null,
    mandatory_potential_share: 1,
  });
  renderQueue();
  fireEvent.click(await screen.findByRole("button", { name: "Матрица требований" }));
  await screen.findByText("Можно сохранить матрицу как есть или поправить статусы — затем «Сохранить всё».");
  fireEvent.click(screen.getByRole("button", { name: "Сохранить всё" }));
  expect(
    await screen.findAllByText("Изменения сохранены. Можно перейти к подтверждению другого кандидата."),
  ).toBeTruthy();
  expect(screen.getByRole("button", { name: "К очереди кандидатов" })).toBeTruthy();
});
