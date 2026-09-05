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
    expect(screen.getByRole("heading").textContent).toContain("вопрос 3 из 3");
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
    expect(screen.getByRole("heading").textContent).toContain("из 4");
  });

  it("без уточнения ведёт к следующему вопросу", async () => {
    render(<InterviewPage token="session" />);
    await waitFor(() => screen.getByText("Вопрос 0"));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => screen.getByRole("button", { name: "Следующий вопрос" }));
    fireEvent.click(screen.getByRole("button", { name: "Следующий вопрос" }));
    expect(screen.getByText("Вопрос 1")).toBeTruthy();
  });
});
