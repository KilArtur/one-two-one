// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { CandidateResultPage } from "./CandidateResultPage";

vi.mock("../api/client");

function renderPage() {
  return render(
    <MemoryRouter>
      <CandidateResultPage token="t" candidateId="c1" />
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.mocked(client.getResultCard).mockResolvedValue({
    candidate_id: "c1",
    recommendation: "additional_check",
    recommendation_reason: "mandatory_needs_check",
    confirmed_count: 4,
    needs_check_count: 1,
    not_confirmed_count: 0,
    mandatory_coverage: null,
    desired_coverage: null,
    resume_text: "10 лет Python",
    topics: [
      {
        topic_id: "t1", topic_title: "PostgreSQL", skill_type: "hard", importance: "mandatory",
        system_status: "confirmed", current_status: "confirmed", author: "system",
        reasoning_summary: null,
      },
      {
        topic_id: "t2", topic_title: "Kafka", skill_type: "hard", importance: "mandatory",
        system_status: "needs_check", current_status: "needs_check", author: "system",
        reasoning_summary: null,
      },
    ],
  });
});
afterEach(() => {
  sessionStorage.clear();
  cleanup();
});

describe("CandidateResultPage", () => {
  it("показывает матрицу топиков первым блоком", async () => {
    renderPage();
    await waitFor(() => screen.getAllByTestId("topic-row"));
    const rows = screen.getAllByTestId("topic-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("PostgreSQL")).toBeTruthy();
  });

  it("показывает рекомендацию с расшифровкой правила Р5", async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByText("Требуется дополнительная проверка").length).toBeGreaterThan(0));
    expect(
      screen.getAllByText(/Правило Р5: есть обязательный топик со статусом «требует проверки»/).length,
    ).toBeGreaterThan(0);
  });

  it("разводит слой резюме и не показывает AI-score", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Резюме"));
    expect(screen.getByText("10 лет Python")).toBeTruthy();
    expect(screen.queryByText(/AI-score|балл/i)).toBeNull();
  });

  it("позволяет техспециалисту сменить статус hard-топика", async () => {
    sessionStorage.setItem("internal-role", "technical_specialist");
    vi.mocked(client.changeTopicStatus).mockResolvedValue();
    renderPage();
    await waitFor(() => screen.getByLabelText("Статус топика Kafka"));
    fireEvent.change(screen.getByLabelText("Статус топика Kafka"), {
      target: { value: "confirmed" },
    });
    fireEvent.change(screen.getByLabelText("Комментарий к статусу Kafka"), {
      target: { value: "Проверил видео" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Сохранить" })[1]);
    await waitFor(() =>
      expect(client.changeTopicStatus).toHaveBeenCalledWith(
        "t",
        "c1",
        "t2",
        "confirmed",
        "Проверил видео",
      ),
    );
  });
});
