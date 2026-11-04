import type { NormalizedMetric } from "./finlens-api";

export const BALANCE_SHEET_RATIOS = [
  { id: "total_liabilities_to_total_assets", label: "Total liabilities / total assets", inputs: ["total_liabilities", "total_assets"] },
  { id: "cash_and_equivalents_to_total_liabilities", label: "Cash and equivalents / total liabilities", inputs: ["cash_and_equivalents", "total_liabilities"] },
] as const;
const concepts: Readonly<Record<string, string>> = {
  total_liabilities: "Liabilities", total_assets: "Assets", cash_and_equivalents: "CashAndCashEquivalentsAtCarryingValue",
};
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const decimal = (v: unknown): v is string => typeof v === "string" && v.length <= 128
  && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(v) && Number.isFinite(Number(v));
// Inspect the coefficient, not a floating-point conversion: tiny values can underflow to signed zero.
const decimalSign = (v: string): number => !/[1-9]/.test(v.split(/[eE]/)[0]) ? 0 : v.startsWith("-") ? -1 : 1;
const optionalText = (v: unknown): boolean => v === undefined || v === null || typeof v === "string";
const optionalYear = (v: unknown): boolean => v === undefined || v === null || Number.isSafeInteger(v);
const date = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)
  && Number.isFinite(Date.parse(`${v}T00:00:00Z`)) && new Date(`${v}T00:00:00Z`).toISOString().slice(0, 10) === v;
const instant = (v: unknown): v is Record<string, unknown> & { end: string } => record(v) && v.kind === "instant"
  && v.start === null && date(v.end) && v.fiscal_year === null && v.fiscal_period === null && v.fiscal_label_basis === "unknown";

function source(v: unknown, cik: string): v is Record<string, unknown> {
  if (!record(v) || !Number.isSafeInteger(v.fact_id) || Number(v.fact_id) <= 0 || v.company_cik !== cik
    || typeof v.canonical_metric !== "string" || !Object.hasOwn(concepts, v.canonical_metric)
    || v.original_concept !== concepts[v.canonical_metric] || v.source !== `SEC Company Facts API: ${v.original_concept}`
    || !decimal(v.value) || v.unit !== "USD" || v.period_start !== null || !date(v.period_end)
    || !optionalYear(v.source_fiscal_year) || !optionalText(v.source_fiscal_period)
    || !date(v.filed) || v.filed < v.period_end || !["10-Q", "10-Q/A", "10-K", "10-K/A"].includes(String(v.form))
    || typeof v.accession_number !== "string" || !/^\d{10}-\d{2}-\d{6}$/.test(v.accession_number)
    || typeof v.sec_url !== "string") return false;
  try {
    const url = new URL(v.sec_url), path = `/Archives/edgar/data/${cik.replace(/^0+(?=\d)/, "")}/${v.accession_number.replaceAll("-", "")}/`;
    const filename = url.pathname.slice(path.length);
    return url.protocol === "https:" && ["www.sec.gov", "sec.gov"].includes(url.hostname) && !url.port
      && !url.username && !url.password && url.pathname.startsWith(path)
      && /^[A-Za-z0-9_.-]+$/.test(filename) && ![".", ".."].includes(filename);
  } catch { return false; }
}

/** Validate evidence/lineage only. No client financial calculation or source replacement. */
export function balanceSheetRatios(value: unknown, cik: string): Record<string, NormalizedMetric> | null {
  if (!/^\d{10}$/.test(cik) || !record(value) || Object.keys(value).length !== 2) return null;
  const identities = new Map<number, string>();
  for (const definition of BALANCE_SHEET_RATIOS) {
    const p = value[definition.id];
    if (!record(p) || p.metric !== definition.id || p.unit !== "ratio" || p.formula !== definition.inputs.join(" / ")
      || !optionalText(p.revenue_basis)
      || !["available", "unavailable"].includes(String(p.status))
      || !(p.period === null || instant(p.period)) || !Array.isArray(p.inputs)
      || !Array.isArray(p.provenance) || !Array.isArray(p.alternatives) || p.alternatives.length > 256) return null;
    if (p.status === "unavailable") {
      if (p.value !== null || typeof p.reason !== "string" || !p.reason.trim()
        || p.inputs.length || p.provenance.length || p.alternatives.length) return null;
      continue;
    }
    if (!decimal(p.value) || decimalSign(p.value) < 0 || p.reason !== null || !instant(p.period)
      || p.inputs.length !== 2 || p.provenance.length !== 2) return null;
    if (new Set([...p.provenance, ...p.alternatives].map(s => record(s) ? s.fact_id : null)).size !== p.provenance.length + p.alternatives.length) return null;
    for (const s of [...p.provenance, ...p.alternatives]) {
      if (!source(s, cik) || !(definition.inputs as readonly string[]).includes(String(s.canonical_metric))) return null;
      // canonical_metric is a projection; every immutable field of one fact ID
      // must agree across selected/alternative sources and both ratio cards.
      const identity = JSON.stringify(Object.keys(s).sort().filter(k => k !== "canonical_metric").map(k => [k, s[k]]));
      const prior = identities.get(s.fact_id as number);
      if (prior !== undefined && prior !== identity) return null;
      identities.set(s.fact_id as number, identity);
    }
    const selected = p.provenance as Record<string, unknown>[];
    if (new Set(selected.map(s => s.fact_id)).size !== 2
      || selected[0].accession_number !== selected[1].accession_number || selected[0].form !== selected[1].form
      || selected[0].filed !== selected[1].filed) return null;
    if ((p.alternatives as Record<string, unknown>[]).some(a => selected.some(s => a.canonical_metric === s.canonical_metric
      && a.accession_number === s.accession_number && a.form === s.form && a.filed === s.filed
      && a.period_end === s.period_end && a.value !== s.value))) return null;
    for (const [index, name] of definition.inputs.entries()) {
      const inputs = p.inputs.filter(i => record(i) && i.role === name && i.metric === name);
      if (inputs.length !== 1) return null;
      const i = inputs[0] as Record<string, unknown>;
      if (!decimal(i.value) || (index === 0 ? decimalSign(i.value) < 0 : decimalSign(i.value) <= 0)
        || !optionalText(i.revenue_basis)
        || i.unit !== "USD" || !instant(i.period) || i.period.end !== p.period.end
        || !Array.isArray(i.fact_ids) || i.fact_ids.length !== 1) return null;
      const sources = selected.filter(s => s.fact_id === (i.fact_ids as unknown[])[0] && s.canonical_metric === name);
      if (sources.length !== 1 || sources[0].value !== i.value || sources[0].unit !== i.unit || sources[0].period_end !== p.period.end) return null;
    }
  }
  return value as Record<string, NormalizedMetric>;
}
