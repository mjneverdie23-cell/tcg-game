/** Number/text formatting helpers used across the UI and the content pipeline. */

export function formatNumber(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US").format(n);
}

export function formatCompact(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function formatArea(km2: number | null | undefined): string {
  if (km2 == null || Number.isNaN(km2)) return "—";
  return `${formatNumber(Math.round(km2))} km²`;
}

export function formatDensity(d: number | null | undefined): string {
  if (d == null || Number.isNaN(d)) return "—";
  return `${d < 10 ? d.toFixed(1) : formatNumber(Math.round(d))} /km²`;
}

export function joinNatural(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function formatCoords(lat: number, lng: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lng >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(2)}° ${ns}, ${Math.abs(lng).toFixed(2)}° ${ew}`;
}

export function formatPercent(p: number | null | undefined): string {
  if (p == null || Number.isNaN(p)) return "—";
  return `${p.toFixed(1)}%`;
}
