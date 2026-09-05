// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { ResultAccessPanel } from "./ResultAccessPanel";
import { ResultLinkPage } from "../pages/ResultLinkPage";

vi.mock("../api/client");
const link: api.ResultLinkInfo = { id: "link", candidate_id: "candidate", created_by: "recruiter", expires_at: "2099-10-05T00:00:00Z", revoked_at: null };
afterEach(() => { cleanup(); window.location.hash = ""; });
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getInternalUser).mockResolvedValue({ username: "recruiter", role: "recruiter" });
  vi.mocked(api.listResultLinks).mockResolvedValue([]);
  vi.mocked(api.getVideoViews).mockResolvedValue([{ id: "view", answer_id: "answer", viewer: "expert", role: "technical_specialist", position_sec: 12, created_at: "2026-09-05T00:00:00Z" }]);
  vi.mocked(api.createResultLink).mockResolvedValue({ ...link, token: "link-secret" });
  vi.mocked(api.revokeResultLink).mockResolvedValue({ ...link, revoked_at: "2026-09-06T00:00:00Z" });
});
it("creates a fragment link, revokes it and displays the video audit", async () => {
  render(<ResultAccessPanel token="jwt" candidateId="candidate" />);
  fireEvent.click(await screen.findByRole("button", { name: "Создать ссылку на результат" }));
  const input = await screen.findByLabelText<HTMLInputElement>("Новая ссылка (сохраните её сейчас)");
  expect(input.value).toContain("/staff/result-link#link-secret");
  expect(screen.getByText("expert")).toBeTruthy();
  expect(screen.getByText("Техспециалист")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Отозвать ссылку" }));
  await screen.findByText(/Отозвана/);
  expect(api.revokeResultLink).toHaveBeenCalledWith("jwt", "link");
  expect(screen.queryByLabelText("Новая ссылка (сохраните её сейчас)")).toBeNull();
});
it("lets an expert read audit without link management controls", async () => {
  vi.mocked(api.getInternalUser).mockResolvedValue({ username: "expert", role: "technical_specialist" });
  render(<ResultAccessPanel token="jwt" candidateId="candidate" />);
  await screen.findByText("expert");
  expect(screen.queryByText("Создать ссылку на результат")).toBeNull();
  expect(api.listResultLinks).not.toHaveBeenCalled();
});
it("resolves the shared result and passes the secret to scoped card requests", async () => {
  window.location.hash = "link-secret";
  vi.mocked(api.resolveResultLink).mockResolvedValue(link);
  vi.mocked(api.getResultCard).mockResolvedValue({ candidate_id: "candidate", topics: [], recommendation: "additional_check", recommendation_reason: "mandatory_needs_check", confirmed_count: 0, needs_check_count: 1, not_confirmed_count: 0, mandatory_coverage: null, desired_coverage: null, resume_text: null });
  render(<ResultLinkPage token="jwt" />);
  await screen.findByText("Карточка результата");
  expect(api.getResultCard).toHaveBeenCalledWith("jwt", "candidate", expect.any(AbortSignal), "link-secret");
  expect(screen.queryByRole("button", { name: "Ссылки и журнал просмотров" })).toBeNull();
});
it("blocks a revoked result before requesting the card", async () => {
  window.location.hash = "revoked";
  vi.mocked(api.resolveResultLink).mockRejectedValue(new Error("403"));
  render(<ResultLinkPage token="jwt" />);
  await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  expect(api.getResultCard).not.toHaveBeenCalled();
});
