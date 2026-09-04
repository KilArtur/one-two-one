import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <main>
      <h1>ИИ-интервьюер</h1>
      <p>Платформа асинхронного видеоинтервью для первичной технической оценки кандидатов.</p>
      <p>
        Перейти к <Link to="/health">проверке статуса системы</Link>.
      </p>
    </main>
  );
}
