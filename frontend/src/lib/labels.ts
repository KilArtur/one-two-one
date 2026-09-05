/** Общие подписи статусов и ролей для UI (без AI-score). */

export const PROCESSING_LABEL: Record<string, string> = {
  not_started: "Не начато",
  recorded: "Записано",
  transcribing: "Транскрибация",
  analyzing: "Анализ",
  ready: "Готово",
  error: "Ошибка",
};

export const STATUS_LABEL: Record<string, string> = {
  confirmed: "✅ подтверждено",
  needs_check: "❓ требует проверки",
  not_confirmed: "❌ не подтверждено",
  out_of_scope: "вне зоны интервью",
};

export const STATUS_TONE: Record<string, "success" | "warning" | "risk" | "blue"> = {
  confirmed: "success",
  needs_check: "warning",
  not_confirmed: "risk",
  ready: "success",
  error: "risk",
  analyzing: "blue",
  transcribing: "blue",
  recorded: "blue",
};

export const RECOMMENDATION_LABEL: Record<string, string> = {
  fit: "Рекомендуется к следующему этапу",
  additional_check: "Требуется дополнительная проверка",
  not_fit: "Не рекомендуется",
};

export const REASON_LABEL: Record<string, string> = {
  stop_factor: "сработал стоп-фактор",
  mandatory_not_confirmed: "есть обязательный топик со статусом «не подтверждено»",
  mandatory_needs_check: "есть обязательный топик со статусом «требует проверки»",
  all_mandatory_confirmed: "все обязательные топики подтверждены",
};

export const AUTHOR_LABEL: Record<string, string> = {
  system: "система",
  technical_specialist: "техспециалист",
  hiring_manager: "нанимающий менеджер",
  recruiter: "рекрутер",
};

export const ROLE_LABEL: Record<string, string> = {
  recruiter: "Рекрутер",
  technical_specialist: "Техспециалист",
  hiring_manager: "Нанимающий менеджер",
};

export function coverageText(confirmed: number, needs: number, notConfirmed: number): string {
  return `✅ ${confirmed} · ❓ ${needs} · ❌ ${notConfirmed}`;
}

export function pct(share: number | null, count: number, total: number): string {
  if (share === null) return `Нет данных (${count} / ${total})`;
  return `${Math.round(share * 100)}% (${count} / ${total})`;
}
