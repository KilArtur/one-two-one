import { useEffect, useState } from "react";
import { createResultLink, getInternalUser, getVideoViews, listResultLinks, ResultLinkInfo, revokeResultLink, VideoViewItem } from "../api/client";

export function ResultAccessPanel({ token, candidateId }: { token: string; candidateId: string }) {
  const [links, setLinks] = useState<ResultLinkInfo[]>([]);
  const [views, setViews] = useState<VideoViewItem[]>([]);
  const [recruiter, setRecruiter] = useState(false);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setBusy(true); setError("");
    async function load() {
      const user = await getInternalUser(token, controller.signal);
      const [audit, list] = await Promise.all([
        getVideoViews(token, candidateId, controller.signal),
        user.role === "recruiter" ? listResultLinks(token, candidateId, controller.signal) : Promise.resolve([]),
      ]);
      if (!controller.signal.aborted) { setRecruiter(user.role === "recruiter"); setViews(audit); setLinks(list); }
    }
    void load().catch(() => { if (!controller.signal.aborted) setError("Не удалось загрузить ссылки и аудит."); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [token, candidateId, revision]);
  async function create() {
    setBusy(true); setError("");
    try {
      const link = await createResultLink(token, candidateId);
      setUrl(`${window.location.origin}/staff/result-link#${link.token}`);
      setLinks((current) => [link, ...current]);
    } catch { setError("Не удалось создать ссылку."); }
    finally { setBusy(false); }
  }
  async function revoke(id: string) {
    setBusy(true); setError("");
    try {
      const link = await revokeResultLink(token, id);
      setLinks((current) => current.map((v) => v.id === id ? link : v)); setUrl("");
    } catch { setError("Не удалось отозвать ссылку."); }
    finally { setBusy(false); }
  }
  return <section aria-label="Доступ к результату">
    <h2>Ссылки и журнал просмотров</h2>
    <button disabled={busy} onClick={() => setRevision((v) => v + 1)}>Обновить ссылки и аудит</button>
    {error && <p role="alert">{error}</p>}
    {recruiter && <>
      <p>Ссылка действует 30 дней. Получателю нужен вход внутренней ролью.</p>
      <button disabled={busy} onClick={() => void create()}>Создать ссылку на результат</button>
      {url && <p><label>Новая ссылка (сохраните её сейчас)<input readOnly value={url} onFocus={(e) => e.target.select()} style={{ width: "100%" }} /></label></p>}
      <ul>{links.map((link) => <li key={link.id}>
        До {new Date(link.expires_at).toLocaleString("ru-RU")} · {link.created_by}{" "}
        {link.revoked_at ? "Отозвана" : Date.parse(link.expires_at) <= Date.now() ? "Срок истёк" : <button disabled={busy} onClick={() => void revoke(link.id)}>Отозвать ссылку</button>}
      </li>)}</ul>
    </>}
    <h3>Просмотры видео</h3>
    {views.length ? <table><thead><tr><th>Кто</th><th>Роль</th><th>Когда</th><th>Секунда</th></tr></thead>
      <tbody>{views.map((view) => <tr key={view.id}><td>{view.viewer}</td><td>{({ recruiter: "Рекрутер", technical_specialist: "Техспециалист", hiring_manager: "Нанимающий менеджер" } as Record<string, string>)[view.role] ?? view.role}</td><td>{new Date(view.created_at).toLocaleString("ru-RU")}</td><td>{view.position_sec.toFixed(1)}</td></tr>)}</tbody></table>
      : !busy && !error && <p>Просмотров пока нет.</p>}
  </section>;
}
