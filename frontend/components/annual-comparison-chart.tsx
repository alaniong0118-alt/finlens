"use client";

import { useEffect, useRef, useState } from "react";
import { COMPARISON_METRICS, metricComparability } from "@/lib/company-comparison";
import { annualRowWarnings, type AnnualPeriodColumn } from "@/lib/annual-period-comparison";
import { formatMetric, METRIC_LABELS, periodLabel } from "@/lib/research";

type Metric = typeof COMPARISON_METRICS[number];

// Projection only: the server's values and periods remain authoritative.
export function annualChartProjection(metric: Metric, columns: AnnualPeriodColumn[]) {
  const rows = columns.map(column => {
    const point = column.result?.metrics[metric];
    const value = point?.status === "available" && point.value !== null ? Number(point.value) : null;
    const nonzeroUnderflow = value === 0 && point?.value != null && /[1-9]/.test(point.value.split(/[eE]/)[0]);
    return { column, point, value, invalid: value !== null && (!Number.isFinite(value) || nonzeroUnderflow) };
  });
  const available = rows.filter(row => row.value !== null);
  const units = new Set(available.map(row => row.point!.unit));
  const conflictingBases = metricComparability(metric, columns.map(column => column.result)).basesDiffer;
  const reason = rows.some(row => row.invalid) ? "A value cannot be represented safely for plotting. Inspect the exact values in the table."
    : units.size > 1 ? "Units differ, so these values cannot share a chart axis. Inspect the table."
    : conflictingBases ? "Revenue bases differ, so these values are not plotted on a shared axis. Inspect the table."
    : available.length === 0 ? "No available observations can be plotted for this metric. Inspect the reasons in the table."
    : null;
  return { rows, available, reason };
}

export default function AnnualComparisonChart({ columns }: { columns: AnnualPeriodColumn[] }) {
  const [metric, setMetric] = useState<Metric | "">("");
  const projection = metric ? annualChartProjection(metric, columns) : null;
  const warnings = metric ? annualRowWarnings(metric, columns) : [];
  const svg = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(800);
  const plotVisible = !!metric && !!projection && !projection.reason;
  useEffect(() => {
    const node = svg.current;
    if (!plotVisible || !node) return;
    const measure = () => {
      const measured = node.getBoundingClientRect().width;
      if (Number.isFinite(measured) && measured > 0) setWidth(measured);
    };
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(node);
    window.addEventListener("resize", measure);
    return () => { observer?.disconnect(); window.removeEventListener("resize", measure); };
  }, [plotVisible]);
  const values = projection?.available.map(row => row.value!) ?? [];
  // Divide before subtracting to avoid overflow for large opposite-signed values.
  const magnitude = Math.max(...values.map(Math.abs), 1);
  const scaled = values.map(value => value / magnitude);
  const low = Math.min(...scaled), high = Math.max(...scaled);
  const lowPoint = projection?.available[scaled.indexOf(low)]?.point;
  const highPoint = projection?.available[scaled.indexOf(high)]?.point;
  const y = (value: number) => high === low ? 100 : 170 - 140 * ((value / magnitude - low) / (high - low));
  const x = (index: number) => 40 + index * ((width - 80) / Math.max(columns.length - 1, 1));

  return <section aria-labelledby="annual-chart-title">
    <h3 id="annual-chart-title">Visualize a selected metric</h3>
    <p className="small muted">Optional view of the selected annual periods. Dots are separate observations, not an interpolated trend; the table below retains exact values and sources.</p>
    <label htmlFor="annual-chart-metric">Metric to visualize</label>{" "}
    <select id="annual-chart-metric" value={metric} onChange={event => setMetric(event.target.value as Metric | "")}>
      <option value="">Choose a metric</option>
      {COMPARISON_METRICS.map(name => <option key={name} value={name}>{METRIC_LABELS[name]}</option>)}
    </select>
    {!metric && <p className="small">Choose a metric to display its available observations. This does not load more data.</p>}
    {metric && projection && <>
      <p className="small">{METRIC_LABELS[metric]} · {projection.available[0]?.point?.unit ?? "unit unavailable"} · Values are as filed; a shared display does not establish equivalent accounting scope.</p>
      {warnings.map(warning => <p className="small" key={warning}>{warning}</p>)}
      {projection.reason ? <p role="status">{projection.reason}</p> : <>
        <div role="region" aria-label="Annual observation chart" tabIndex={0} style={{ overflowX: "auto" }}>
          <svg ref={svg} viewBox={`0 0 ${width} 220`} width="100%" height="220" style={{ display: "block", minWidth: 240 }} role="img" aria-label={`${METRIC_LABELS[metric]} observations. Exact values, dates and sources follow in the annual comparison table.`}>
            {projection.rows.map((row, index) => row.value === null
              ? <text key={row.column.year} x={x(index)} y="195" textAnchor="middle" fill="currentColor">No value</text>
              : <circle key={row.column.year} cx={x(index)} cy={y(row.value)} r="7" fill="#0f766e" />)}
            {projection.rows.map((row, index) => <text key={row.column.year} x={x(index)} y="215" textAnchor="middle" fill="currentColor">FY{row.column.year}</text>)}
          </svg>
        </div>
        <p className="small muted">Vertical scale: {lowPoint && formatMetric(lowPoint)} to {highPoint && formatMetric(highPoint)}. Dots are not joined; this scale has no zero baseline. See the table for exact values and source details.</p>
      </>}
      <ul>{projection.rows.map(({ column, point }) => <li key={column.year} className="small">
        FY{column.year} · {column.result ? periodLabel(column.result.period) : "Reporting period not verified"} · {point ? formatMetric(point) : "Financial evidence not verified"}
        {point?.reason ? ` · ${point.reason}` : column.error ? ` · ${column.error}` : ""}
      </li>)}</ul>
    </>}
  </section>;
}
