import { FormEvent, useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { EquipmentCheck } from "../components/EquipmentCheck";
import { InterviewPage } from "./InterviewPage";
import { candidateApi } from "../api/client";

const SESSION_KEY = "candidate-session";

export function CandidatePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const magicToken = new URLSearchParams(location.search).get("token");
  const [token, setToken] = useState(() => sessionStorage.getItem(SESSION_KEY));
  const [ready, setReady] = useState(false);
  const [consented, setConsented] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setReady(false);
    setError("");
    async function load() {
      try {
        if (magicToken) {
          sessionStorage.removeItem(SESSION_KEY);
          const session = await candidateApi.exchange(magicToken);
          if (!active) return;
          sessionStorage.setItem(SESSION_KEY, session.access_token);
          setToken(session.access_token);
          setAccepted(false);
          navigate("/interview/consent", { replace: true });
          return;
        }
        if (!token) throw new Error("Откройте персональную ссылку из приглашения на интервью.");
        const consent = await candidateApi.consent(token);
        if (location.pathname === "/interview/equipment" && consent.consent_given_at) {
          await candidateApi.equipmentAccess(token);
        }
        if (active) {
          setConsented(consent.consent_given_at !== null);
          setReady(true);
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Не удалось открыть интервью.");
      }
    }
    void load();
    return () => { active = false; };
  }, [magicToken, token, location.pathname, navigate, attempt]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!accepted || !token || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await candidateApi.acceptConsent(token);
      if (!result.consent_given_at) throw new Error("Согласие не сохранено. Попробуйте ещё раз.");
      setReady(false);
      navigate("/interview/equipment");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось сохранить согласие.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) return (
    <main>
      <h1>Подготовка к интервью</h1>
      {error ? <><p role="alert">{error}</p><button onClick={() => setAttempt(attempt + 1)}>Повторить</button></>
        : <p role="status">Загружаем приглашение…</p>}
    </main>
  );

  if (location.pathname === "/interview/equipment") {
    if (!consented) return <Navigate to="/interview/consent" replace />;
    return <EquipmentCheck onContinue={() => navigate("/interview/session")} />;
  }

  if (location.pathname === "/interview/session") {
    if (!consented || !token) return <Navigate to="/interview/consent" replace />;
    return <InterviewPage token={token} />;
  }

  return (
    <main>
      <p>Шаг 1 · Подготовка</p>
      <h1>Согласие на запись и обработку данных</h1>
      <p>Интервью займёт около 20–30 минут. До начала записи необходимо ваше согласие.</p>
      <p>Во время интервью будут записаны видео и звук ваших ответов. Записи, расшифровки,
        резюме и результаты интервью обрабатываются для оценки покрытия требований вакансии
        и доступны уполномоченным участникам подбора. Финальное кадровое решение принимает человек.</p>
      <p>Срок хранения материалов — 6 месяцев. Вы можете обратиться к рекрутеру с запросом
        на досрочное удаление. Материалы не используются для обучения моделей без отдельного
        письменного разрешения.</p>
      <form onSubmit={submit}>
        <label style={{ display: "flex", gap: 12, alignItems: "flex-start", margin: "24px 0" }}>
          <input type="checkbox" checked={accepted} disabled={busy}
            onChange={(event) => setAccepted(event.target.checked)} />
          <span>Я согласен(на) на запись видео и звука и обработку моих персональных данных
            для проведения и оценки интервью на описанных условиях.</span>
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={!accepted || busy}>
          {busy ? "Сохраняем согласие…" : "Принять и перейти к проверке оборудования"}
        </button>
      </form>
    </main>
  );
}
