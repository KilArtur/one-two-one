import { FormEvent, ReactNode, useState } from "react";
import { Brand, StaffShell } from "../layouts/Shell";
import { internalLogin, internalRegister } from "../api/client";

type Role = "recruiter" | "technical_specialist" | "hiring_manager";
type Mode = "login" | "register";

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
  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!role) return;
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const username = String(data.get("username"));
    const password = String(data.get("password"));
    try {
      const next =
        mode === "register"
          ? await internalRegister(username, password, role)
          : await internalLogin(username, password, role);
      sessionStorage.setItem("internal-session", next);
      sessionStorage.setItem("internal-role", role);
      sessionStorage.setItem("internal-username", username);
      setToken(next);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : mode === "register"
            ? "Ошибка регистрации."
            : "Ошибка входа.",
      );
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
    setMode("login");
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
        </div>
        <div className="auth-main">
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
                onClick={() => {
                  setRole(item.id);
                  setMode("login");
                  setError("");
                }}
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
      <div className="auth-main auth-form">
        <p className="eyebrow">{current.title}</p>
        <h1 className="auth-form-title">{mode === "register" ? "Регистрация" : "Вход"}</h1>
        <div className="inline auth-mode">
          <button
            type="button"
            className={`btn small ${mode === "login" ? "primary" : "dark"}`}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            Войти
          </button>
          <button
            type="button"
            className={`btn small ${mode === "register" ? "primary" : "dark"}`}
            onClick={() => {
              setMode("register");
              setError("");
            }}
          >
            Зарегистрироваться
          </button>
        </div>
        <form onSubmit={(event) => void submit(event)}>
          <div className="form-group">
            <label htmlFor="username">Имя пользователя</label>
            <input id="username" name="username" required autoComplete="username" />
          </div>
          <div className="form-group">
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              name="password"
              type="password"
              required
              minLength={mode === "register" ? 6 : 1}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
            />
          </div>
          <input type="hidden" name="role" value={role} />
          <button className="btn primary" disabled={busy} type="submit">
            {busy
              ? mode === "register"
                ? "Создаём…"
                : "Входим…"
              : mode === "register"
                ? "Создать аккаунт"
                : "Войти"}
          </button>
          {error && (
            <p role="alert" className="auth-error">
              {error}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
