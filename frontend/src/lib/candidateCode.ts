/** Короткий читаемый код кандидата: из UUID — К-XXXX-XXXX, иначе короткий ярлык. */
export function candidateCode(id: string): string {
  const raw = id.replace(/-/g, "");
  if (/^[0-9a-fA-F]{32}$/.test(raw)) {
    const hex = raw.slice(0, 8).toUpperCase();
    return `К-${hex.slice(0, 4)}-${hex.slice(4)}`;
  }
  if (id.startsWith("К-")) return id;
  return `К-${id}`;
}

/** Имя кандидата, если задано; иначе короткий код. */
export function candidateLabel(id: string, fullName?: string | null): string {
  const name = fullName?.trim();
  return name || candidateCode(id);
}
