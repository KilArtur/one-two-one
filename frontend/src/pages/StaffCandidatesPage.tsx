import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Vacancy, listVacancies } from "../api/client";
import { EmptyState, PageHead } from "../layouts/Shell";
import { CandidateListPage } from "./CandidateListPage";

/** Выбор вакансии + список кандидатов для маршрута /staff/candidates. */
export function StaffCandidatesPage({ token }: { token: string }) {
  const [params, setParams] = useSearchParams();
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [error, setError] = useState("");
  const vacancyId = params.get("vacancy_id") ?? "";

  useEffect(() => {
    const controller = new AbortController();
    listVacancies(token, controller.signal)
      .then((items) => {
        setVacancies(items);
        if (!params.get("vacancy_id") && items[0]) {
          setParams({ vacancy_id: items[0].id }, { replace: true });
        }
      })
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки вакансий.");
        }
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- автовыбор вакансии один раз при загрузке списка
  }, [token, setParams]);

  if (error) {
    return (
      <main>
        <p role="alert">{error}</p>
      </main>
    );
  }

  if (!vacancyId) {
    return (
      <main>
        <PageHead eyebrow="Рекрутер" title="Кандидаты" />
        <div className="filterbar">
          <label className="meta">
            Вакансия{" "}
            <select
              className="field"
              value=""
              onChange={(event) => setParams({ vacancy_id: event.target.value })}
            >
              <option value="">Выберите вакансию</option>
              {vacancies.map((vacancy) => (
                <option key={vacancy.id} value={vacancy.id}>
                  {vacancy.title} · v{vacancy.version}
                </option>
              ))}
            </select>
          </label>
        </div>
        <EmptyState title="Выберите вакансию" text="Список кандидатов привязан к версии вакансии." />
      </main>
    );
  }

  return (
    <>
      <div className="filterbar" style={{ marginBottom: 0, padding: "0 0 8px" }}>
        <label className="meta">
          Вакансия{" "}
          <select
            className="field"
            value={vacancyId}
            onChange={(event) => setParams({ vacancy_id: event.target.value })}
          >
            {vacancies.map((vacancy) => (
              <option key={vacancy.id} value={vacancy.id}>
                {vacancy.title} · v{vacancy.version}
              </option>
            ))}
          </select>
        </label>
      </div>
      <CandidateListPage token={token} vacancyId={vacancyId} />
    </>
  );
}
