import { Link, NavLink } from "react-router-dom";
import { ReactNode } from "react";
import { ROLE_LABEL } from "../lib/labels";

export function Brand() {
  return (
    <div className="brand">
      ADAPTIVE<span>.</span>INTERVIEW
    </div>
  );
}

export function StaffShell({
  username,
  role,
  onLogout,
  children,
}: {
  username: string;
  role: string;
  onLogout: () => void;
  children?: ReactNode;
}) {
  const showReview = role !== "recruiter";
  const showMetrics = role !== "technical_specialist";
  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-left">
          <Brand />
          <span className="sep-v" />
          <span className="meta">{ROLE_LABEL[role] ?? role}</span>
        </div>
        <div className="topbar-right">
          <span className="meta">{username}</span>
          <button type="button" className="role-switch" onClick={onLogout}>
            Сменить роль
          </button>
          <button type="button" className="btn small ghost" onClick={onLogout}>
            Выйти
          </button>
        </div>
      </header>
      <div className="recruiter-shell">
        <aside className="sidebar" aria-label="Навигация">
          <div>
            <p className="side-title">Рабочее пространство</p>
            <NavLink to="/staff/overview" className={({ isActive }) => `side-link${isActive ? " active" : ""}`}>
              <span className="side-icon">◈</span>
              <span className="side-label">Обзор</span>
            </NavLink>
            <NavLink to="/staff/vacancies" className={({ isActive }) => `side-link${isActive ? " active" : ""}`}>
              <span className="side-icon">▤</span>
              <span className="side-label">Вакансии</span>
            </NavLink>
            <NavLink to="/staff/candidates" className={({ isActive }) => `side-link${isActive ? " active" : ""}`}>
              <span className="side-icon">◎</span>
              <span className="side-label">Кандидаты</span>
            </NavLink>
            {showReview && (
              <NavLink to="/staff/review" className={({ isActive }) => `side-link${isActive ? " active" : ""}`}>
                <span className="side-icon">✦</span>
                <span className="side-label">Ревью</span>
              </NavLink>
            )}
            {showMetrics && (
              <NavLink to="/staff/metrics" className={({ isActive }) => `side-link${isActive ? " active" : ""}`}>
                <span className="side-icon">▣</span>
                <span className="side-label">Метрики</span>
              </NavLink>
            )}
          </div>
        </aside>
        <div className="main">{children}</div>
      </div>
    </div>
  );
}

export function CandidateChrome({
  step,
  children,
}: {
  step: "consent" | "devices" | "ready" | "live" | "done";
  children: ReactNode;
}) {
  const steps = [
    { id: "consent", label: "Согласие" },
    { id: "devices", label: "Устройства" },
    { id: "ready", label: "Готовность" },
    { id: "live", label: "Интервью" },
    { id: "done", label: "Отправка" },
  ] as const;
  const order = steps.map((s) => s.id);
  const current = order.indexOf(step);
  return (
    <div className={`candidate${step === "devices" ? " equipment-fit" : ""}`}>
      <header className="topbar">
        <Brand />
        <span className="meta">Асинхронное видеоинтервью</span>
      </header>
      <div className="candidate-wrap">
        <nav className="stepper" aria-label="Этапы интервью">
          {steps.map((s, index) => {
            const state = index < current ? "done" : index === current ? "active" : "";
            return (
              <div key={s.id} className={`step ${state}`}>
                <span>
                  {index + 1}. {s.label}
                </span>
              </div>
            );
          })}
        </nav>
        {children}
      </div>
    </div>
  );
}

export function PageHead({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function StatusPill({
  tone,
  children,
}: {
  tone?: "success" | "warning" | "risk" | "blue";
  children: ReactNode;
}) {
  return <span className={`status ${tone ?? ""}`}>{children}</span>;
}

export function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      <p className="meta">{text}</p>
    </div>
  );
}

export function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <nav className="breadcrumbs" aria-label="Хлебные крошки">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`} className="inline">
          {index > 0 && <span>/</span>}
          {item.to ? <Link to={item.to}>{item.label}</Link> : <span>{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}
