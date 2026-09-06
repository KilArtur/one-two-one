import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { VacancyTopicWrite, createVacancy, draftVacancyFromPdf } from "../api/client";
import { Breadcrumbs, PageHead } from "../layouts/Shell";

const MIN_TOPICS = 1;

const EMPTY_TOPIC = (): VacancyTopicWrite => ({
  title: "",
  skill_type: "hard",
  importance: "mandatory",
  requirement_description: "",
  order: 0,
});

export function VacancyCreatePage({ token }: { token: string }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [grade, setGrade] = useState("middle");
  const [mainQuestionMinutes, setMainQuestionMinutes] = useState("2");
  const [tasks, setTasks] = useState("");
  const [questionExamples, setQuestionExamples] = useState("");
  const [topics, setTopics] = useState<VacancyTopicWrite[]>([{ ...EMPTY_TOPIC(), order: 1 }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [parsing, setParsing] = useState(false);
  const [draftNote, setDraftNote] = useState("");

  function updateTopic(index: number, patch: Partial<VacancyTopicWrite>) {
    setTopics((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function loadFromPdf(file: File) {
    setParsing(true);
    setDraftNote("");
    try {
      const draft = await draftVacancyFromPdf(token, file);
      setTitle(draft.title);
      setGrade(draft.grade);
      setTasks(draft.tasks);
      setQuestionExamples(draft.question_examples);
      if (draft.topics.length) {
        setTopics(draft.topics.map((topic, index) => ({ ...topic, order: index + 1 })));
      }
      setDraftNote(`Форма заполнена из документа, топиков: ${draft.topics.length}. Проверьте и поправьте.`);
    } catch (reason) {
      setDraftNote(reason instanceof Error ? reason.message : "Не удалось разобрать документ.");
    } finally {
      setParsing(false);
    }
  }

  function addTopic() {
    setTopics((rows) => [...rows, { ...EMPTY_TOPIC(), order: rows.length + 1 }]);
  }

  function removeTopic(index: number) {
    setTopics((rows) => {
      if (rows.length <= 1) return rows;
      return rows.filter((_, i) => i !== index).map((row, order) => ({ ...row, order: order + 1 }));
    });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (topics.length < MIN_TOPICS) {
      setError("Нужен хотя бы один топик.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const vacancy = await createVacancy(token, {
        title,
        grade,
        tasks: tasks || "",
        question_examples: questionExamples || "",
        topics: topics.map((topic, order) => ({
          ...topic,
          order: order + 1,
          requirement_description: topic.requirement_description || "",
          depth_expectations: topic.depth_expectations || "",
        })),
      });
      navigate(`/staff/candidates?vacancy_id=${vacancy.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось создать вакансию.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <Breadcrumbs
        items={[
          { label: "Команда", to: "/staff/overview" },
          { label: "Вакансии", to: "/staff/vacancies" },
          { label: "Новая" },
        ]}
      />
      <PageHead eyebrow="Матрица требований" title="Новая вакансия" />

      <section className={`upload-box${draftNote && !parsing ? " ready" : ""}`}>
        <div>
          <p className="eyebrow">Источник</p>
          <h2 className="upload-box-title">Описание вакансии в PDF</h2>
          <p className="meta">
            Модель разберёт документ на топики и заполнит форму — дальше всё можно поправить руками.
          </p>
        </div>
        <label className={`upload-pick${parsing ? " disabled" : ""}`} htmlFor="vacancy-pdf">
          <span className="upload-pick-icon" aria-hidden>
            ↑
          </span>
          <span>{parsing ? "Разбираем документ…" : "Выбрать PDF"}</span>
          <input
            id="vacancy-pdf"
            type="file"
            accept="application/pdf"
            disabled={parsing}
            aria-label="Описание вакансии в PDF"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) void loadFromPdf(file);
            }}
          />
        </label>
        {parsing && (
          <div className="process-wait" role="status" aria-live="polite">
            <span className="process-spinner" aria-hidden />
            <div>
              <p className="process-wait-title">Разбираем PDF…</p>
              <p className="meta">Модель заполняет форму — подождите, это может занять до минуты.</p>
            </div>
          </div>
        )}
        {!parsing && draftNote && <p role="status">{draftNote}</p>}
      </section>

      <form className="panel" onSubmit={(event) => void submit(event)}>
        <div className="form-grid">
          <div className="form-group">
            <label htmlFor="title">Название</label>
            <input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="form-group">
            <label htmlFor="grade">Грейд</label>
            <select id="grade" value={grade} onChange={(e) => setGrade(e.target.value)}>
              <option value="junior">junior</option>
              <option value="middle">middle</option>
              <option value="middle+">middle+</option>
              <option value="senior">senior</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="main-question-minutes">Время на основной вопрос по топику</label>
            <select
              id="main-question-minutes"
              value={mainQuestionMinutes}
              onChange={(e) => setMainQuestionMinutes(e.target.value)}
            >
              <option value="1">1 минута</option>
              <option value="2">2 минуты</option>
              <option value="3">3 минуты</option>
              <option value="5">5 минут</option>
            </select>
            <p className="meta">В демо на основной вопрос всегда 2 минуты, на уточнение — 1 минута.</p>
          </div>
          <div className="form-group full">
            <label htmlFor="tasks">Задачи</label>
            <textarea id="tasks" value={tasks} onChange={(e) => setTasks(e.target.value)} />
          </div>
          <div className="form-group full">
            <label htmlFor="question-examples">Примеры вопросов</label>
            <textarea
              id="question-examples"
              placeholder="Что примерно спросил бы техспециалист — по одному вопросу в строке. Мы раскроем их под топики."
              value={questionExamples}
              onChange={(e) => setQuestionExamples(e.target.value)}
            />
          </div>
        </div>

        <div className="section-head" style={{ marginTop: 32 }}>
          <h2>Топики</h2>
          <div className="inline">
            <span className="meta">Топиков: {topics.length}</span>
            <button type="button" className="btn small ghost" onClick={addTopic}>
              Добавить топик
            </button>
          </div>
        </div>

        <div className="matrix">
          <div className="matrix-row header">
            <div>Название</div>
            <div>Тип</div>
            <div>Важность</div>
            <div>Описание требования</div>
            <div>Действия</div>
          </div>
          {topics.map((topic, index) => (
            <div className="matrix-row" key={index}>
              <div>
                <input
                  required
                  placeholder="Например, PostgreSQL"
                  value={topic.title}
                  onChange={(e) => updateTopic(index, { title: e.target.value })}
                />
              </div>
              <div>
                <select
                  value={topic.skill_type}
                  onChange={(e) => updateTopic(index, { skill_type: e.target.value as "hard" | "soft" })}
                >
                  <option value="hard">hard</option>
                  <option value="soft">soft</option>
                </select>
              </div>
              <div>
                <select
                  value={topic.importance}
                  onChange={(e) =>
                    updateTopic(index, { importance: e.target.value as "mandatory" | "desired" })
                  }
                >
                  <option value="mandatory">обязательный</option>
                  <option value="desired">желательный</option>
                </select>
              </div>
              <div>
                <textarea
                  placeholder="Что именно проверяем"
                  value={topic.requirement_description ?? ""}
                  onChange={(e) => updateTopic(index, { requirement_description: e.target.value })}
                />
              </div>
              <div>
                <button
                  type="button"
                  className="btn small ghost"
                  disabled={topics.length <= 1}
                  title={topics.length <= 1 ? "Нужен хотя бы один топик" : "Удалить этот топик"}
                  onClick={() => removeTopic(index)}
                >
                  Удалить
                </button>
              </div>
            </div>
          ))}
        </div>

        {error && (
          <p role="alert" style={{ marginTop: 16 }}>
            {error}
          </p>
        )}
        <div className="inline" style={{ marginTop: 24, justifyContent: "flex-end" }}>
          <Link className="btn ghost" to="/staff/vacancies">
            Отмена
          </Link>
          <button className="btn primary" disabled={busy} type="submit">
            {busy ? "Сохраняем…" : "Создать вакансию"}
          </button>
        </div>
      </form>
    </main>
  );
}
