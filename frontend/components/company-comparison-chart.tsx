"use client";
import { useId, useState } from "react";
import { COMPARISON_METRICS, metricComparability } from "@/lib/company-comparison";
import { formatMetric, METRIC_LABELS, periodLabel } from "@/lib/research";
import type { AnnualFinancialComparison, Company } from "@/lib/finlens-api";

type Metric = typeof COMPARISON_METRICS[number];
export type CompanyChartColumn = { company: Company; result?: AnnualFinancialComparison; error?: string };

function canonicalDecimal(value: string): string | null {
  if (value.length > 128) return null;
  const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(value);
  if (!match) return null;
  let digits = (match[2] + (match[3] ?? "")).replace(/^0+/, "");
  if (!digits) return "0";
  let exponent = Number(match[4] ?? "0") - (match[3]?.length ?? 0);
  if (!Number.isSafeInteger(exponent)) return null;
  while (digits.endsWith("0")) { digits = digits.slice(0, -1); exponent++; }
  return `${match[1]}${digits}e${exponent}`;
}

// Display projection only; callers supply the same validated columns as the table.
export function companyChartProjection(metric: Metric, columns: CompanyChartColumn[]) {
  const rows = columns.map(column => {
    const point = column.result?.metrics[metric];
    const value = point?.status === "available" && point.value !== null ? Number(point.value) : null;
    const unsafe = value !== null && (!Number.isFinite(value) || typeof point?.value !== "string" || canonicalDecimal(point.value) === null || canonicalDecimal(point.value) !== canonicalDecimal(String(value)));
    return { column, point, value, invalid: unsafe };
  });
  const available = rows.filter(row => row.value !== null);
  const units = new Set(available.map(row => row.point!.unit));
  const diagnostics = metricComparability(metric, columns.map(column => column.result));
  // Scaling can lose most of the visible differences when values are close
  // relative to their magnitude, even if each Number round-trips as text.
  const finite = available.filter(row => !row.invalid);
  const distinct = new Set(finite.map(row => canonicalDecimal(row.point!.value!)));
  const magnitude = Math.max(...finite.map(row => Math.abs(row.value!)), 1);
  const scaled = finite.map(row => row.value! / magnitude);
  const unstable = distinct.size > 1 && Math.max(...scaled) - Math.min(...scaled) <= 1e-8;
  const reason = rows.some(row => row.invalid) ? "A value cannot be plotted safely. See the exact values in the table."
    : unstable ? "Differences are too small to plot reliably. See the exact values in the table."
    : units.size > 1 ? "Units differ; these values cannot share a chart axis."
    : diagnostics.windowsDiffer ? "Reporting windows differ; these values cannot share a chart axis."
    : diagnostics.basesDiffer ? "Revenue bases differ; these values cannot share a chart axis."
    : diagnostics.basisUnknown ? "Revenue basis is unknown; these values cannot share a chart axis."
    : available.length === 0 ? "No available observations can be plotted. See the reasons in the table." : null;
  return { rows, available, diagnostics, reason };
}

export default function CompanyComparisonChart({ columns, onShowAll }: { columns: CompanyChartColumn[]; onShowAll?: () => void }) {
  const [metric, setMetric] = useState<Metric | "">("");
  const id = useId();
  const plot = metric ? companyChartProjection(metric, columns) : null;
  const values = plot?.available.map(row => row.value!) ?? [];
  const magnitude = Math.max(...values.map(Math.abs), 1);
  const scaled = values.map(value => value / magnitude);
  const low = Math.min(...scaled), high = Math.max(...scaled);
  const lowPoint = plot?.available[scaled.indexOf(low)]?.point;
  const highPoint = plot?.available[scaled.indexOf(high)]?.point;
  const y = (value: number) => high === low ? 90 : 155 - 120 * ((value / magnitude - low) / (high - low));
  return <details className="provenance"><summary>Visualize a metric (optional)</summary><div className="details-body">
    <p className="small muted">Dots are separate observations in selected-company order. Exact values, source details and exclusions are in the full table. A shared display does not establish accounting equivalence.</p>
    {onShowAll && <p className="notice">The coverage-gap filter may hide the selected metric. <button type="button" className="secondary-button" onClick={onShowAll}>Show all metric rows and sources</button></p>}
    <label htmlFor={id}>Metric to visualize</label>{" "}<select id={id} value={metric} onChange={event => setMetric(event.target.value as Metric | "")}>
      <option value="">Choose a metric</option>{COMPARISON_METRICS.map(name => <option key={name} value={name}>{METRIC_LABELS[name]}</option>)}
    </select>
    {metric && plot && <>
      {plot.diagnostics.basisUnknown && <p className="notice" role="note">Revenue basis is unknown for at least one response; equivalence is not established.</p>}
      {plot.reason ? <p role="status">{plot.reason}</p> : <div role="region" aria-label="Company observation chart" tabIndex={0} style={{ overflowX: "auto", maxWidth: "100%" }}>
        <svg viewBox="0 0 640 200" width="100%" height="200" style={{ display: "block", minWidth: 440 }} role="img" aria-label={`${METRIC_LABELS[metric]} observations in selected-company order. Exact values and sources are in the full table.`}>
          {plot.rows.map((row, index) => { const x = 80 + index * (480 / Math.max(columns.length - 1, 1)); return <g key={row.column.company.cik}>
            {row.value === null ? <text x={x} y="115" textAnchor="middle" fill="currentColor">No value</text> : <circle cx={x} cy={y(row.value)} r="7" fill="#0f766e" />}
            <text x={x} y="190" textAnchor="middle" fill="currentColor">{row.column.company.ticker}</text>
          </g>; })}
        </svg>
      </div>}
      {!plot.reason && <p className="small muted">Vertical scale: {lowPoint && formatMetric(lowPoint)} to {highPoint && formatMetric(highPoint)}. This scale has no zero baseline; points are not joined.</p>}
      <ul>{plot.rows.map(({column, point}) => <li key={column.company.cik} className="small">{column.company.ticker} · {column.result ? periodLabel(column.result.period) : "Reporting period not verified"} · {point ? formatMetric(point) : "Financial evidence not verified"}{point?.reason ? ` · ${point.reason}` : column.error ? ` · ${column.error}` : ""}</li>)}</ul>
    </>}
  </div></details>;
}
