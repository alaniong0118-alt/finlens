import { COMPARISON_METRICS } from "./company-comparison";
import type { NormalizedMetric, StoredFinancialCoverage } from "./finlens-api";

export type CoverageMetricFilter = "all" | typeof COMPARISON_METRICS[number];
export type CoverageStatusFilter = "all" | NormalizedMetric["status"];

// Presentation only: callers must supply the result of validateCoverage.
export function presentCoverage(data: StoredFinancialCoverage, metricFilter: CoverageMetricFilter, statusFilter: CoverageStatusFilter) {
  const totals = { available: 0, unavailable: 0, not_applicable: 0 };
  for (const column of data.columns) for (const metric of COMPARISON_METRICS) totals[column.metrics[metric].status]++;
  const metrics = COMPARISON_METRICS.filter(metric => metricFilter === "all" || metric === metricFilter);
  let visibleCount = 0;
  const columns = data.columns.filter(column => {
    const matches = metrics.filter(metric => statusFilter === "all" || column.metrics[metric].status === statusFilter).length;
    visibleCount += matches;
    return matches > 0;
  });
  return { totals, metrics, columns, visibleCount };
}
