// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { candidateApi, getInterviewQuestions } from "../api/client";
import { CandidatePage } from "./CandidatePage";

vi.mock("../api/client", () => ({
  candidateApi: {
    exchange: vi.fn(), consent: vi.fn(), acceptConsent: vi.fn(), equipmentAccess: vi.fn(),
  },
  getInterviewQuestions: vi.fn(),
}));

function open(path = "/interview/consent") {
  render(<MemoryRouter initialEntries={[path]}><CandidatePage /></MemoryRouter>);
}

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  sessionStorage.setItem("candidate-session", "test-session");
  vi.mocked(candidateApi.consent).mockResolvedValue({ consent_given_at: null });
  vi.mocked(candidateApi.equipmentAccess).mockResolvedValue({ consent_given_at: "2026-09-05T12:00:00Z" });
  vi.mocked(getInterviewQuestions).mockResolvedValue([]);
});
afterEach(cleanup);

describe("candidate consent", () => {
  it("shows consent text and blocks continuation until checked", async () => {
    open();
    const checkbox = await screen.findByRole("checkbox");
    const button = screen.getByRole("button", { name: /Принять/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(screen.getByText(/Срок хранения материалов/).textContent).toContain("6 месяцев");
    fireEvent.click(button);
    expect(candidateApi.acceptConsent).not.toHaveBeenCalled();
    fireEvent.click(checkbox);
    expect(button.disabled).toBe(false);
    fireEvent.click(checkbox);
    expect(button.disabled).toBe(true);
  });

  it("redirects a direct equipment URL to consent", async () => {
    open("/interview/equipment");
    await screen.findByRole("checkbox");
    expect(screen.queryByRole("heading", { name: "Проверка камеры и микрофона" })).toBeNull();
    expect(candidateApi.equipmentAccess).not.toHaveBeenCalled();
  });

  it("saves consent before moving to equipment", async () => {
    vi.mocked(candidateApi.acceptConsent).mockImplementation(async () => {
      vi.mocked(candidateApi.consent).mockResolvedValue({ consent_given_at: "2026-09-05T12:00:00Z" });
      return { consent_given_at: "2026-09-05T12:00:00Z" };
    });
    open();
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /Принять/ }));
    await screen.findByRole("heading", { name: "Проверка камеры и микрофона" });
    expect(candidateApi.acceptConsent).toHaveBeenCalledTimes(1);
    expect(candidateApi.acceptConsent).toHaveBeenCalledWith("test-session");
    expect(candidateApi.equipmentAccess).toHaveBeenCalledWith("test-session");
  });

  it("waits for persistence and disables duplicate submissions", async () => {
    let finish!: (value: { consent_given_at: string | null }) => void;
    vi.mocked(candidateApi.acceptConsent).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    open();
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /Принять/ }));
    const saving = await screen.findByRole("button", { name: /Сохраняем/ });
    expect((saving as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(saving);
    expect(candidateApi.acceptConsent).toHaveBeenCalledTimes(1);
    expect(candidateApi.equipmentAccess).not.toHaveBeenCalled();
    finish({ consent_given_at: null });
    await screen.findByRole("alert");
    expect(candidateApi.equipmentAccess).not.toHaveBeenCalled();
  });

  it("stays on consent after a save failure and supports retry", async () => {
    vi.mocked(candidateApi.acceptConsent).mockRejectedValue(new Error("Ошибка сохранения"));
    open();
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /Принять/ }));
    expect((await screen.findByRole("alert")).textContent).toBe("Ошибка сохранения");
    expect((screen.getByRole("button", { name: /Принять/ }) as HTMLButtonElement).disabled).toBe(false);
    expect(candidateApi.equipmentAccess).not.toHaveBeenCalled();
  });

  it("rechecks persisted consent on equipment reload", async () => {
    vi.mocked(candidateApi.consent).mockResolvedValue({ consent_given_at: "2026-09-05T12:00:00Z" });
    open("/interview/equipment");
    await screen.findByRole("heading", { name: "Проверка камеры и микрофона" });
    expect(candidateApi.equipmentAccess).toHaveBeenCalledWith("test-session");
  });

  it("exchanges an invitation and uses its session", async () => {
    vi.mocked(candidateApi.exchange).mockResolvedValue({ access_token: "new-session" });
    open("/interview?token=invitation");
    await screen.findByRole("checkbox");
    expect(candidateApi.exchange).toHaveBeenCalledWith("invitation");
    expect(candidateApi.consent).toHaveBeenCalledWith("new-session");
    expect(sessionStorage.getItem("candidate-session")).toBe("new-session");
  });

  it("does not reuse the previous session when a new invitation fails", async () => {
    vi.mocked(candidateApi.exchange).mockRejectedValue(new Error("Ссылка недоступна"));
    open("/interview?token=invalid");
    await screen.findByRole("alert");
    expect(sessionStorage.getItem("candidate-session")).toBeNull();
    expect(candidateApi.consent).not.toHaveBeenCalled();
  });

  it("blocks equipment when server access is denied", async () => {
    vi.mocked(candidateApi.consent).mockResolvedValue({ consent_given_at: "2026-09-05T12:00:00Z" });
    vi.mocked(candidateApi.equipmentAccess).mockRejectedValue(new Error("Ссылка отозвана"));
    open("/interview/equipment");
    await screen.findByRole("alert");
    expect(screen.queryByRole("heading", { name: "Проверка камеры и микрофона" })).toBeNull();
  });

  it("requires an invitation without a stored session", async () => {
    sessionStorage.clear();
    open();
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("персональную ссылку"));
    expect(candidateApi.consent).not.toHaveBeenCalled();
  });
});
