// Presentation helpers. Pure + tested — no business logic the API owns.

export function fmtTokens(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1000) return (n / 1000).toFixed(n >= 100000 ? 0 : 1) + "k";
  return String(n);
}

export function fmtInt(n: number | null | undefined): string {
  return n == null ? "—" : n.toLocaleString();
}

export function fmtCost(cost: string | null | undefined): string {
  if (cost == null || cost === "") return "—";
  const num = Number(cost);
  return Number.isFinite(num) ? `$${num.toFixed(2)}` : "—";
}

// Coarse relative time, matching the mockup's "3h / yesterday / 2d ago" register.
export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "—";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "—";
  const secs = Math.max(0, Math.round((now - then) / 1000));
  if (secs < 45) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

export function riskDotClass(risk: string | null | undefined): string {
  if (risk === "high") return "hi";
  if (risk === "medium") return "md";
  return "lo";
}

export function severityRank(sev: string): number {
  return sev === "high" ? 0 : sev === "medium" ? 1 : 2;
}
