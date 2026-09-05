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

const overview = (id: string, status: string): client.CandidateOverview => ({
  candidate_id: id,
  candidate_status: "submitted",
  processing_status: status,
  confirmed_count: 3,
  needs_check_count: 1,
  not_confirmed_count: 0,
  recommendation: "fit",
});

beforeEach(() => {
  vi.mocked(client.listCandidates).mockResolvedValue([
    overview("c1", "ready"),
    overview("c2", "error"),
  ]);
});
afterEach(() => cleanup());

describe("CandidateListPage", () => {
  it("показывает список кандидатов со статусами и тройкой чисел", async () => {
    renderList();
    await waitFor(() => screen.getAllByTestId("candidate-row"));
    expect(screen.getAllByTestId("candidate-row")).toHaveLength(2);
    expect(screen.getAllByText(/✅ 3 · ❓ 1 · ❌ 0/).length).toBeGreaterThan(0);
  });

  it("визуально помечает кандидата в состоянии error", async () => {
    renderList();
    await waitFor(() => screen.getAllByTestId("candidate-row"));
    const rows = screen.getAllByTestId("candidate-row");
    const errored = rows.find((row) => row.getAttribute("data-error") === "true");
    expect(errored).toBeTruthy();
    expect(screen.getByText(/требует внимания/)).toBeTruthy();
  });

  it("фильтрует по статусу обработки", async () => {
    renderList();
    await waitFor(() => screen.getAllByTestId("candidate-row"));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "error" } });
    await waitFor(() =>
      expect(client.listCandidates).toHaveBeenLastCalledWith("t", "v", "error", expect.anything()),
    );
  });
});
