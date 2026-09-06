// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { VacanciesPage } from "./VacanciesPage";

vi.mock("../api/client");

const vacancy = (id: string, title: string): client.Vacancy => ({
  id,
  lineage_id: id,
  title,
  grade: "middle",
  tasks: "",
  specialist_profile: null,
  question_examples: null,
  version: 1,
  status: "draft",
  topics: [],
});

beforeEach(() => {
  sessionStorage.setItem("internal-role", "recruiter");
  vi.mocked(client.listVacancies).mockResolvedValue([
    vacancy("v1", "Backend"),
    vacancy("v2", "Frontend"),
  ]);
});
afterEach(() => {
  sessionStorage.clear();
  cleanup();
});

describe("VacanciesPage", () => {
  it("удаляет вакансию из списка после подтверждения", async () => {
    vi.mocked(client.deleteVacancy).mockResolvedValue();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <MemoryRouter>
        <VacanciesPage token="t" />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText("Backend"));
    fireEvent.click(screen.getAllByRole("button", { name: "Удалить" })[0]);
    await waitFor(() => expect(client.deleteVacancy).toHaveBeenCalledWith("t", "v1"));
    await waitFor(() => expect(screen.queryByText("Backend")).toBeNull());
    expect(screen.getByText("Frontend")).toBeTruthy();
  });
});
