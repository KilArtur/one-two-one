import { FormEvent, ReactNode, useState } from "react";
import { internalLogin } from "../api/client";

export function InternalSession({ children }: { children: (token: string) => ReactNode }) {
  const [token, setToken] = useState(() => sessionStorage.getItem("internal-session") ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      const next = await internalLogin(String(data.get("username")), String(data.get("password")), String(data.get("role")));
      sessionStorage.setItem("internal-session", next); setToken(next);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Ошибка входа."); }
    finally { setBusy(false); }
  }
  if (token) return <>
    <button onClick={() => { sessionStorage.removeItem("internal-session"); setToken(""); }}>Выйти</button>
    {children(token)}
  </>;
  return <main><h1>Вход для команды</h1><form onSubmit={(event) => void login(event)}>
    <p><label>Имя пользователя <input name="username" required autoComplete="username" /></label></p>
    <p><label>Пароль <input name="password" type="password" required autoComplete="current-password" /></label></p>
    <p><label>Роль <select name="role">
      <option value="recruiter">Рекрутер</option><option value="technical_specialist">Техспециалист</option><option value="hiring_manager">Нанимающий менеджер</option>
    </select></label></p>
    <button disabled={busy}>Войти</button>{error && <p role="alert">{error}</p>}
  </form></main>;
}
