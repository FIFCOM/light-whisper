export function normalizeSelectionText(value: string): string | null {
  const normalized = value.replace(/\r\n?/g, "\n").trim();
  return normalized || null;
}
