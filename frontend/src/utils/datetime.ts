const ISO_REGEX = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/;

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "-";

  const raw = typeof value === "string" ? value : value.toISOString();
  const match = raw.match(ISO_REGEX);
  if (!match) return "-";

  const [, year, month, day, hour, minute, second] = match;
  return `${year}/${month}/${day} ${hour}:${minute}:${second}`;
}
