const CROP_NAMES: Record<string, string> = { tomato: "Tomato", "bell-pepper": "Bell pepper" };

export function cropName(cropId: string): string {
  return CROP_NAMES[cropId] ?? cropId;
}

/** "Sat 21 Nov" from "2026-11-21". Read as UTC, so the date never shifts a day. */
export function shortDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

/** "21 Nov, 08:00 UTC" from an ISO timestamp. */
export function shortTimestamp(iso: string): string {
  const date = new Date(iso);
  const day = date.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  const time = date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
  return `${day}, ${time} UTC`;
}

export function wholeNumber(value: number): string {
  return value.toLocaleString("en-GB");
}
