import type {StatisticsReceipt} from "../lib/hypothetical-panel-statistics";

const reasons: Record<string, string> = {
  insufficient_observations: "insufficient supplied intervals",
  arithmetic_resource_limit: "exact arithmetic limit reached",
};
const missing = (reason: string | null) => `Unavailable: ${reasons[reason ?? ""] ?? "unverified result"}`;
const wrap = {overflowWrap: "anywhere" as const, minWidth: 0};

export function HypotheticalPanelStatistics({receipt}: {receipt: StatisticsReceipt}) {
  const r = receipt.result;
  return <section className="panel" aria-labelledby="asset-statistics-result" style={{marginTop:20, minWidth:0}}>
    <h2 id="asset-statistics-result">Hypothetical asset statistics</h2>
    <p>Synthetic user-entered factors only · {r.sample_count} supplied intervals. These are asset-factor statistics, not portfolio wealth or short-position returns.</p>
    <p>Every interval has equal observation weight. Sample volatility and covariance use N−1 = {r.sample_denominator ?? "unavailable"} and need at least two intervals. Cumulative return and drawdown need at least one. No annualization, probabilities, forecasts or investment recommendations.</p>
    {r.equal_interval_lengths === false && <p>Unequal supplied interval lengths: {r.interval_days.join(", ")} calendar days. Observations keep equal weight; no calendar or trading-frequency adjustment is made.</p>}
    <p>Values are return ratios, not percentages or currency amounts. A return ratio of 0.01 means 1%. Signed exposures, declared portfolio value, confidence and risk horizon do not weight these statistics. All supplied intervals are used; calendar completeness and statistical adequacy are unverified.</p>
    <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(min(100%, 290px), 1fr))", gap:16, minWidth:0}}>
      {r.assets.map((asset, i) => <section key={asset.asset_id} aria-labelledby={`asset-statistics-${i}`} style={wrap}>
        <h3 id={`asset-statistics-${i}`} style={wrap}>{asset.asset_id}</h3>
        <dl>
          <dt>Cumulative return · all supplied intervals</dt><dd style={wrap}>{asset.cumulative_return.exact?.display ?? missing(asset.cumulative_return.reason)}</dd>
          <dt>Maximum drawdown · decline ratio</dt><dd style={wrap}>{asset.maximum_drawdown.exact?.display ?? missing(asset.maximum_drawdown.reason)}</dd>
          <dt>Sample volatility · per supplied interval</dt><dd style={wrap}>{asset.sample_volatility.display ?? missing(asset.sample_volatility.reason)}</dd>
        </dl>
        <p>Drawdown boundaries: {asset.peak_boundary === null ? "unavailable" : `peak ${asset.peak_boundary}, trough ${asset.trough_boundary}`}.</p>
      </section>)}
    </div>
    <p>Drawdown starts from a normalized asset index of 1 before the first interval. Boundary 0 precedes interval 0; boundary k follows interval k−1. Ties retain the first peak/trough witness. Positive drawdown means decline.</p>
    <div role="region" aria-label="Hypothetical sample covariance" tabIndex={0} style={{overflowX:"auto", maxWidth:"100%"}}>
      <table style={{width:"100%"}}><caption>Sample covariance per supplied interval · return ratio squared. Row and column asset order match. Negative off-diagonal values are valid.</caption>
        <thead><tr><th scope="col">Asset</th>{r.asset_ids.map(id => <th key={id} scope="col" style={wrap}>{id}</th>)}</tr></thead>
        <tbody>{r.covariance.map((row, i) => <tr key={r.asset_ids[i]}><th scope="row" style={wrap}>{r.asset_ids[i]}</th>{row.map((cell, j) => <td key={r.asset_ids[j]} style={wrap}>{cell.exact?.display ?? missing(cell.reason)}</td>)}</tr>)}</tbody>
      </table>
    </div>
    {!r.covariance_complete && <p>Covariance is incomplete. Unavailable cells remain unavailable; none are replaced by zero.</p>}
    <p>Displays round to 18 decimal places, HALF_EVEN. A displayed zero may retain a nonzero exact value. Volatility is the square root of its exact variance radicand; its rounded display is not an exact fraction.</p>
    <details><summary>Exact asset statistics and supplied-factor audit</summary>
      <p>The receipt retains exact fractions, mean/variance operands, volatility radicands, drawdown boundaries and every normalized supplied factor. It is a separate method: existing v1 Risk/Stress downloads and imports do not accept this statistics receipt.</p>
      <pre tabIndex={0} aria-label="Exact hypothetical asset statistics receipt" style={{whiteSpace:"pre-wrap", overflowWrap:"anywhere", maxHeight:600, overflow:"auto"}}>{JSON.stringify(receipt, null, 2)}</pre>
    </details>
  </section>;
}
