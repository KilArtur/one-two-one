// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { getProductMetrics, ProductMetrics } from "../api/client";
import { ProductMetricsPage } from "./ProductMetricsPage";

vi.mock("../api/client");
afterEach(() => { cleanup(); vi.resetAllMocks(); });
function data(): ProductMetrics {
  const statuses = {
    confirmed: { count: 1, total: 2, share: 0.5 },
    needs_check: { count: 1, total: 2, share: 0.5 },
    not_confirmed: { count: 0, total: 2, share: 0 },
  };
  return { system_statuses: statuses, current_statuses: statuses, reviewed_topics: 0,
    changed_after_review: { count: 0, total: 0, share: null },
    disputed_changed_after_review: { count: 0, total: 1, share: 0 },
    review_directions: [], completion: { count: 1, total: 1, share: 1 },
    technical_failures: { count: 0, total: 1, share: 0 } };
}
it("shows fractions and refreshes review and completion after changes", async () => {
  const initial = data();
  const updated = { ...data(), reviewed_topics: 1,
    changed_after_review: { count: 1, total: 1, share: 1 },
    review_directions: [{ from_status: "needs_check", to_status: "confirmed", count: 1 }],
    completion: { count: 1, total: 2, share: 0.5 }, technical_failures: { count: 1, total: 2, share: 0.5 } };
  vi.mocked(getProductMetrics).mockResolvedValueOnce(initial).mockResolvedValueOnce(updated);
  render(<ProductMetricsPage token="token" vacancyId="vacancy" />);
  expect(await screen.findByText("100% (1 / 1)")).toBeTruthy();
  expect(screen.getByText("Нет данных (0 / 0)")).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Исходный статус системы" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Обновить метрики" }));
  await waitFor(() => expect(screen.getByText("Топиков с ревью: 1")).toBeTruthy());
  expect(screen.getByText("❓ требует проверки → ✅ подтверждено: 1")).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "Прохождение интервью" })).getAllByText("50% (1 / 2)")).toHaveLength(2);
  expect(getProductMetrics).toHaveBeenLastCalledWith("token", "vacancy", expect.any(AbortSignal));
});
it("shows a fetch error and allows retry", async () => {
  vi.mocked(getProductMetrics).mockRejectedValueOnce(new Error("Нет связи")).mockResolvedValueOnce(data());
  render(<ProductMetricsPage token="token" />);
  expect(await screen.findByRole("alert")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Обновить метрики" }));
  expect(await screen.findByText("100% (1 / 1)")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});
