import { FormEvent, ReactNode, useState } from "react";
import { Brand, StaffShell } from "../layouts/Shell";
import { internalLogin } from "../api/client";

type Role = "recruiter" | "technical_specialist" | "hiring_manager";

const ROLES: { id: Role; title: string; text: string }[] = [
  {
    id: "recruiter",
    title: "Рекрутер",
    text: "Вакансии, приглашения кандидатов, статусы обработки и ссылки на результат.",
  },
  {
    id: "technical_specialist",
    title: "Техспециалист",
    text: "Очередь hard-топиков, требующих проверки, с evidence и записью.",
  },
  {
    id: "hiring_manager",
    title: "Нанимающий менеджер",
    text: "Очередь soft-топиков и карточки результата без изменения hard-статусов.",
  },
];

export function InternalSession({ children }: { children: (token: string) => ReactNode }) {
  const [token, setToken] = useState(() => sessionStorage.getItem("internal-session") ?? "");
  const [role, setRole] = useState<Role | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!role) return;
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const next = await internalLogin(
        String(data.get("username")),
        String(data.get("password")),
        role,
      );
      sessionStorage.setItem("internal-session", next);
      sessionStorage.setItem("internal-role", role);
      sessionStorage.setItem("internal-username", String(data.get("username")));
      setToken(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ошибка входа.");
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    sessionStorage.removeItem("internal-session");
    sessionStorage.removeItem("internal-role");
    sessionStorage.removeItem("internal-username");
    setToken("");
    setRole(null);
  }

  if (token) {
    const storedRole = sessionStorage.getItem("internal-role") ?? "recruiter";
    const username = sessionStorage.getItem("internal-username") ?? "user";
    return (
      <StaffShell username={username} role={storedRole} onLogout={logout}>
        {children(token)}
      </StaffShell>
    );
  }

  if (!role) {
    return (
      <div className="auth">
        <div className="auth-head">
          <Brand />
          <span className="meta" style={{ color: "#9a9aa0" }}>
            Вход для команды подбора
          </span>
        </div>
        <div className="auth-main">
          <p className="eyebrow" style={{ color: "#8f8f95" }}>
            Adaptive Interview
          </p>
          <h1>
            Выберите роль,
            <br />
            <em>чтобы открыть рабочее пространство</em>
          </h1>
          <div className="role-grid">
            {ROLES.map((item) => (
              <button
                key={item.id}
                type="button"
                className="role-card"
                onClick={() => setRole(item.id)}
              >
                <div>
                  <b>{item.title}</b>
                  <p>{item.text}</p>
                </div>
                <span className="arrow">→</span>
              </button>
            ))}
          </div>
        </div>
        <div className="auth-foot">
          <span>Логин любой · пароль = INTERNAL_AUTH_PASSWORD из .env (по умолчанию change-me)</span>
          <span>Финальное решение всегда за человеком</span>
        </div>
      </div>
    );
  }

  const current = ROLES.find((item) => item.id === role)!;
  return (
    <div className="auth">
      <div className="auth-head">
        <Brand />
        <button type="button" className="btn dark small" onClick={() => setRole(null)}>
          Другая роль
        </button>
      </div>
      <div className="auth-main" style={{ maxWidth: 520 }}>
        <p className="eyebrow" style={{ color: "#8f8f95" }}>
          {current.title}
        </p>
        <h1 style={{ fontSize: "clamp(42px, 6vw, 64px)", marginBottom: 36 }}>Вход</h1>
        <form onSubmit={(event) => void login(event)}>
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label htmlFor="username" style={{ color: "#b8b8bd" }}>
              Имя пользователя
            </label>
            <input
              id="username"
              name="username"
              required
              autoComplete="username"
              style={{ background: "#1c1c20", borderColor: "#414146", color: "white" }}
            />
          </div>
          <div className="form-group" style={{ marginBottom: 24 }}>
            <label htmlFor="password" style={{ color: "#b8b8bd" }}>
              Пароль
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              style={{ background: "#1c1c20", borderColor: "#414146", color: "white" }}
            />
          </div>
          <input type="hidden" name="role" value={role} />
          <button className="btn primary" disabled={busy} type="submit">
            {busy ? "Входим…" : "Войти"}
          </button>
          {error && (
            <p role="alert" style={{ color: "#ff8d86", marginTop: 16 }}>
              {error}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
