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
    full_name: "Иван Петров",
    recommendation: "additional_check",
    recommendation_reason: "mandatory_needs_check",
    confirmed_count: 4,
    needs_check_count: 1,
    not_confirmed_count: 0,
    mandatory_coverage: null,
    desired_coverage: null,
    resume_text: "10 лет Python",
    mandatory_confirmed_share: 0.5,
    desired_confirmed_share: null,
    mandatory_potential_share: 0.75,
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

  it("показывает id кандидата и рекомендацию без правила Р5", async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByText("Требуется дополнительная проверка").length).toBeGreaterThan(0));
    expect(screen.getByText("К-c1")).toBeTruthy();
    expect(
      screen.getAllByText(/есть обязательный топик со статусом «требует проверки»/).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/Правило Р5/)).toBeNull();
    expect(screen.queryByText("Иван Петров")).toBeNull();
  });

  it("не показывает резюме и AI-score", async () => {
    renderPage();
    await waitFor(() => screen.getByText("К-c1"));
    expect(screen.queryByText("Резюме")).toBeNull();
    expect(screen.queryByText("10 лет Python")).toBeNull();
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

  it("сохраняет все изменённые топики одной кнопкой", async () => {
    sessionStorage.setItem("internal-role", "technical_specialist");
    vi.mocked(client.changeTopicStatus).mockResolvedValue();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: "Сохранить всё" }));
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Сохранить всё" }).disabled).toBe(
      true,
    );
    fireEvent.change(screen.getByLabelText("Статус топика PostgreSQL"), {
      target: { value: "needs_check" },
    });
    fireEvent.change(screen.getByLabelText("Статус топика Kafka"), {
      target: { value: "confirmed" },
    });
    fireEvent.change(screen.getByLabelText("Комментарий к статусу Kafka"), {
      target: { value: "Ок" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить всё" }));
    await waitFor(() => expect(client.changeTopicStatus).toHaveBeenCalledTimes(2));
    expect(client.changeTopicStatus).toHaveBeenCalledWith("t", "c1", "t1", "needs_check", "");
    expect(client.changeTopicStatus).toHaveBeenCalledWith("t", "c1", "t2", "confirmed", "Ок");
  });
});
