// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { InterviewPage } from "./InterviewPage";

vi.mock("../api/client");

vi.mock("../components/InterviewQuestionStep", () => ({
  InterviewQuestionStep: ({
    question,
    onSaved,
  }: {
    question: client.InterviewQuestion;
    onSaved: () => void;
  }) => (
    <div>
      <p>{question.text}</p>
      <button onClick={() => onSaved()}>Сохранить</button>
    </div>
  ),
}));

const Q = (
  id: string,
  topic: string,
  text: string,
  type: client.InterviewQuestion["type"] = "core",
): client.InterviewQuestion => ({ id, topic_id: topic, text, type });

beforeEach(() => {
  vi.mocked(client.getInterviewQuestions).mockResolvedValue([
    Q("q0", "t0", "Вопрос 0"),
    Q("q1", "t1", "Вопрос 1"),
    Q("q2", "t2", "Вопрос 2"),
  ]);
  vi.mocked(client.getInterviewSession).mockResolvedValue({
    current_question: Q("q0", "t0", "Вопрос 0"),
    answered_count: 0,
    total: 3,
    finished: false,
  });
  vi.mocked(client.requestFollowup).mockResolvedValue({ ask: false, reason: "x", question: null });
  vi.mocked(client.skipQuestion).mockResolvedValue({ question_id: "q0", skipped: true });
  vi.mocked(client.submitInterview).mockResolvedValue({
    candidate_id: "c", used_at: "2026-09-05T00:00:00Z", candidate_status: "submitted",
  });
});
afterEach(() => cleanup());

describe("InterviewPage", () => {
  it("возобновляет сессию с первого неотвеченного вопроса (Р11)", async () => {
    vi.mocked(client.getInterviewSession).mockResolvedValue({
      current_question: Q("q2", "t2", "Вопрос 2"),
      answered_count: 2,
      total: 3,
      finished: false,
    });
    render(<InterviewPage token="session" />);
    await waitFor(() => screen.getByText("Вопрос 2"));
    expect(screen.getByText("Вопрос 3 из 3")).toBeTruthy();
  });

  it("вставляет уточняющий вопрос после сохранения (M4)", async () => {
    vi.mocked(client.requestFollowup).mockResolvedValueOnce({
      ask: true,
      reason: "clarification_needed",
      question: Q("f0", "t0", "Уточнение?", "follow_up"),
    });
    render(<InterviewPage token="session" />);
    await waitFor(() => screen.getByText("Вопрос 0"));

    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => screen.getByRole("button", { name: "Следующий вопрос" }));
    expect(client.requestFollowup).toHaveBeenCalledWith("session", "t0");

    fireEvent.click(screen.getByRole("button", { name: "Следующий вопрос" }));
    await waitFor(() => screen.getByText("Уточнение?"));
    // Уточняющий вопрос помечается как дополнительный и не увеличивает счётчик каркаса.
    expect(screen.getByText("Уточняющий")).toBeTruthy();
  });

  it("без уточнения ведёт к следующему вопросу", async () => {
    render(<InterviewPage token="session" />);
    await waitFor(() => screen.getByText("Вопрос 0"));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => screen.getByRole("button", { name: "Следующий вопрос" }));
    fireEvent.click(screen.getByRole("button", { name: "Следующий вопрос" }));
    expect(screen.getByText("Вопрос 1")).toBeTruthy();
  });

  it("пропуск вопроса вызывает skip и предупреждает о последствии (Р10)", async () => {
    render(<InterviewPage token="session" />);
    await waitFor(() => screen.getByText("Вопрос 0"));
    const skip = screen.getByRole("button", { name: "Пропустить вопрос" });
    expect(skip.getAttribute("title")).toMatch(/нельзя отменить/i);
    fireEvent.click(skip);
    await waitFor(() =>
      expect(client.skipQuestion).toHaveBeenCalledWith("session", "q0"),
    );
    await waitFor(() => screen.getByRole("button", { name: "Следующий вопрос" }));
  });

  it("на последнем вопросе показывает отправку и экран подтверждения", async () => {
    vi.mocked(client.getInterviewSession).mockResolvedValue({
      current_question: Q("q2", "t2", "Вопрос 2"), answered_count: 2, total: 3, finished: false,
    });
    render(<InterviewPage token="session" />);
    await waitFor(() => screen.getByText("Вопрос 2"));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() =>
      screen.getByRole("button", { name: "Завершить и отправить интервью" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Завершить и отправить интервью" }));
    await waitFor(() => screen.getByText("Интервью отправлено"));
    expect(client.submitInterview).toHaveBeenCalledWith("session");
  });
});
