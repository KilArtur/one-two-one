// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { CandidateListPage } from "./CandidateListPage";

vi.mock("../api/client");

function renderList() {
  return render(
    <MemoryRouter>
      <CandidateListPage token="t" vacancyId="v" />
    </MemoryRouter>,
  );
}

const overview = (
  id: string,
  status: string,
  extras: Partial<client.CandidateOverview> = {},
): client.CandidateOverview => ({
  candidate_id: id,
  full_name: extras.full_name ?? `Кандидат ${id}`,
  candidate_status: "submitted",
  processing_status: status,
  confirmed_count: 3,
  needs_check_count: 1,
  not_confirmed_count: 0,
  recommendation: "fit",
  skill_coverage: 0.75,
  mandatory_coverage: null,
  desired_coverage: null,
  mandatory_confirmed_share: extras.mandatory_confirmed_share ?? extras.mandatory_coverage ?? null,
  desired_confirmed_share: extras.desired_confirmed_share ?? extras.desired_coverage ?? null,
  mandatory_potential_share: extras.mandatory_potential_share ?? null,
  ...extras,
});

beforeEach(() => {
  sessionStorage.setItem("internal-role", "recruiter");
  vi.mocked(client.listCandidates).mockResolvedValue([
    overview("c-low", "ready", {
      recommendation: "not_fit",
      confirmed_count: 1,
      needs_check_count: 0,
      not_confirmed_count: 3,
      skill_coverage: 0.25,
      mandatory_coverage: 0.25,
      desired_coverage: 0,
      mandatory_confirmed_share: 0.25,
      desired_confirmed_share: 0,
      mandatory_potential_share: 0.25,
    }),
    overview("c-high", "ready", {
      recommendation: "fit",
      confirmed_count: 4,
      needs_check_count: 0,
      not_confirmed_count: 0,
      skill_coverage: 1,
      mandatory_coverage: 1,
      desired_coverage: 1,
      mandatory_confirmed_share: 1,
      desired_confirmed_share: 1,
      mandatory_potential_share: 1,
    }),
    overview("c-error", "error", {
      recommendation: "additional_check",
      confirmed_count: 2,
      needs_check_count: 2,
      not_confirmed_count: 0,
      skill_coverage: 0.5,
      mandatory_coverage: null,
      desired_coverage: 0.5,
      mandatory_confirmed_share: 0.5,
      desired_confirmed_share: 0.5,
      mandatory_potential_share: 1,
    }),
  ]);
});
afterEach(() => {
  sessionStorage.clear();
  cleanup();
});

describe("CandidateListPage", () => {
  it("показывает процент покрытия и ранжирует по нему", async () => {
    renderList();
    await waitFor(() => screen.getAllByTestId("candidate-row"));
    const rows = screen.getAllByTestId("candidate-row");
    expect(rows).toHaveLength(3);
    expect(rows[0].textContent).toContain("К-c-high");
    expect(rows[0].textContent).toContain("обяз. 100%");
    expect(rows[0].textContent).toContain("желат. 100%");
    expect(rows[0].textContent).toContain("потенциал обяз. 100%");
    expect(screen.getByText("Среднее (обязательные)").previousElementSibling?.textContent).toBe("58%");
    fireEvent.click(screen.getByRole("button", { name: "Сортировать по проценту покрытия" }));
    expect(screen.getAllByTestId("candidate-row")[0].textContent).toContain("К-c-low");
    expect(screen.getAllByTestId("candidate-row")[0].textContent).toContain("обяз. 25%");
  });

  it("визуально помечает кандидата в состоянии error", async () => {
    renderList();
    await waitFor(() => screen.getAllByTestId("candidate-row"));
    const rows = screen.getAllByTestId("candidate-row");
    const errored = rows.find((row) => row.getAttribute("data-error") === "true");
    expect(errored).toBeTruthy();
    expect(screen.getByText(/требует внимания/)).toBeTruthy();
  });

  it("фильтрует по статусу обработки на клиенте", async () => {
    renderList();
    await waitFor(() => screen.getAllByTestId("candidate-row"));
    fireEvent.change(screen.getByLabelText("Фильтр по статусу обработки"), {
      target: { value: "error" },
    });
    await waitFor(() => expect(screen.getAllByTestId("candidate-row")).toHaveLength(1));
    expect(client.listCandidates).toHaveBeenLastCalledWith("t", "v", expect.anything());
  });

  it("фильтрует по проходит / не проходит", async () => {
    renderList();
    await waitFor(() => screen.getAllByTestId("candidate-row"));
    fireEvent.change(screen.getByLabelText("Фильтр по рекомендации"), {
      target: { value: "not_fit" },
    });
    await waitFor(() => expect(screen.getAllByTestId("candidate-row")).toHaveLength(1));
    expect(screen.getAllByTestId("candidate-row")[0].textContent).toContain("К-c-low");
  });

  it("после PDF показывает извлечённое основное и текст из файла", async () => {
    vi.mocked(client.draftResumeCard).mockResolvedValue({
      profile: {
        full_name: "Иван Петров",
        headline: "Backend",
        skills: ["Python"],
        experience: ["Ozon"],
        education: [],
      },
      resume_text: "Иван Петров\n\nНавыки:\n- Python",
      source_text: "Полный текст из PDF",
      parsed_by_model: true,
    });
    renderList();
    await waitFor(() => screen.getByLabelText("Резюме в PDF (необязательно)"));
    const file = new File(["%PDF"], "resume.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Резюме в PDF (необязательно)"), {
      target: { files: [file] },
    });
    await waitFor(() => screen.getByRole("region", { name: "Извлечённое основное" }));
    expect(screen.getByText("Иван Петров")).toBeTruthy();
    expect(screen.getByText("Текст из PDF")).toBeTruthy();
    expect((screen.getByLabelText("Основное из резюме (необязательно)") as HTMLTextAreaElement).value).toContain(
      "Python",
    );
  });

  it("удаляет кандидата из списка после подтверждения", async () => {
    vi.mocked(client.deleteCandidate).mockResolvedValue();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderList();
    await waitFor(() => screen.getAllByTestId("candidate-row"));
    fireEvent.click(screen.getAllByRole("button", { name: "Удалить" })[0]);
    await waitFor(() => expect(client.deleteCandidate).toHaveBeenCalledWith("t", "c-high"));
    await waitFor(() => expect(screen.getAllByTestId("candidate-row")).toHaveLength(2));
  });
});
