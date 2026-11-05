"use client";

import {useEffect, useRef, useState} from "react";
import {HypotheticalReplay} from "./hypothetical-replay";
import {formInputs, requestRisk, type RiskReceipt} from "../lib/hypothetical-risk";
import {requestStatistics, type StatisticsReceipt} from "../lib/hypothetical-panel-statistics";
import {HypotheticalPanelStatistics} from "./hypothetical-panel-statistics";

const unavailable: Record<string, string> = {insufficient_scenarios: "fewer than two complete scenarios", insufficient_tail_mass: "less than one observation of tail mass", portfolio_value_not_declared: "no declared portfolio value", nonpositive_portfolio_value: "declared portfolio value is not positive"};
const inputStyle = {width: "100%", minWidth: 0, font: "inherit", padding: 10, border: "1px solid var(--border)", borderRadius: 8, background: "var(--card)", color: "var(--text)", minHeight: 44};

export function HypotheticalRisk() {
  const form = useRef<HTMLFormElement | null>(null);
  const [revision, setRevision] = useState(0);
  const [receipt, setReceipt] = useState<RiskReceipt | null>(null);
  const [statistics, setStatistics] = useState<StatisticsReceipt | null>(null);
  const [status, setStatus] = useState("Enter your hypothetical inputs to calculate.");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0), controller = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  function invalidate() {
    generation.current++; setRevision(generation.current); controller.current?.abort(); controller.current = null;
    if (timer.current) clearTimeout(timer.current); timer.current = null;
  }
  useEffect(() => () => { generation.current++; controller.current?.abort(); if (timer.current) clearTimeout(timer.current); }, []);
  function cancel() { invalidate(); setBusy(false); setReceipt(null); setStatistics(null); setError(null); setStatus("Calculation cancelled. Submit explicitly to retry."); }
  function edit() {invalidate(); setReceipt(null); setStatistics(null); setError(null); setBusy(false); setStatus("Inputs changed. Calculate again to view a current result.");}
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); invalidate(); setReceipt(null); setStatistics(null); setError(null); setBusy(false);
    const assetStatistics = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "statistics";
    try {
      const inputs = formInputs(event.currentTarget), id = generation.current;
      const active = new AbortController(); controller.current = active; setBusy(true); setStatus(assetStatistics ? "Calculating hypothetical asset statistics…" : "Calculating hypothetical sample losses…");
      timer.current = setTimeout(() => {
        if (id !== generation.current) return;
        invalidate(); setBusy(false); setError("Calculation timed out. Submit explicitly to retry."); setStatus("");
      }, 10000);
      try {
        const result = assetStatistics ? await requestStatistics(inputs, active.signal) : await requestRisk(inputs, active.signal);
        if (id !== generation.current || active.signal.aborted) return;
        if (assetStatistics) setStatistics(result as StatisticsReceipt); else setReceipt(result as RiskReceipt);
        setStatus("Hypothetical calculation complete. Review sample limitations and the audit.");
      } catch (reason) {
        if (id !== generation.current || active.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Calculation failed. Retry explicitly."); setStatus("");
      } finally {
        if (id === generation.current) { if (timer.current) clearTimeout(timer.current); timer.current = null; controller.current = null; setBusy(false); }
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Check your inputs."); setStatus(""); }
  }
  const r = receipt?.result;
  return <main className="workspace" style={{maxWidth: 1100}}>
    <header className="hero"><p className="eyebrow">FinLens · Development candidate</p><h1>Hypothetical portfolio risk</h1>
      <p>Synthetic inputs entered by you. These results are educational sample calculations, not real market history, forecasts, recommendations or live-data acceptance.</p></header>
    <section className="panel" aria-labelledby="assumptions"><h2 id="assumptions">Assumptions and limits</h2>
      <p>Signed initial notional exposures stay fixed across all scenarios. Positive amounts are long; negative amounts are short. Every amount and factor uses the declared reporting currency; no FX conversion is performed. Asset IDs are user labels.</p>
      <p>Enter chronological intervals with each end equal to the next start and exactly one positive gross factor per asset. A factor of 1 means unchanged. Calendar completeness and economic inputs are unverified. No missing observation is dropped, filled or bridged. Dates describe supplied intervals, not verified trading sessions.</p>
      <p>Maximum 8 assets, 120 intervals, horizon 1–20 supplied intervals. Exact ordinary decimal strings: at most 24 digits, 12 fractional places; no exponent notation. Request 128 KiB; response 1 MiB. One calculation per backend process. No fees, financing or rebalancing. Cancellation stops display and transport; bounded server work may finish.</p>
    </section>
    <form ref={form} className="panel" style={{marginTop: 20}} aria-busy={busy} onSubmit={submit} onInput={edit} onChange={edit}>
      <h2>Hypothetical inputs</h2>
      <div className="comparison-values">
        <label>Reporting currency<input style={inputStyle} className="block" name="currency" required defaultValue="USD" maxLength={3} pattern="[A-Z]{3}" /></label>
        <label>Exposure date<input style={inputStyle} className="block" name="date" type="date" required /></label>
        <label>Confidence (0 &lt; α &lt; 1)<input style={inputStyle} className="block" name="confidence" required defaultValue="0.95" maxLength={26} inputMode="decimal" /></label>
        <label>Horizon (supplied intervals)<input style={inputStyle} className="block" name="horizon" required defaultValue="1" maxLength={2} inputMode="numeric" /></label>
        <label>Declared portfolio value (optional)<input style={inputStyle} className="block" name="value" maxLength={26} inputMode="decimal" /></label>
      </div>
      <label htmlFor="risk-exposures">Signed exposures</label><p id="exposure-help" className="small muted">One line per asset: asset_id signed_amount. Amounts are notionals, not shares. All amounts are in the reporting currency.</p>
      <textarea id="risk-exposures" name="exposures" required rows={4} maxLength={1200} aria-describedby="exposure-help" spellCheck={false} />
      <label htmlFor="risk-sessions" style={{marginTop: 16}}>Exact gross-return factors</label><p id="session-help" className="small muted">One line per interval: interval_id YYYY-MM-DD YYYY-MM-DD factor_for_first_asset factor_for_second_asset … Use the exposure order above. Empty inventory is allowed and returns insufficient scenarios.</p>
      <textarea id="risk-sessions" name="sessions" rows={8} maxLength={50000} aria-describedby="session-help" spellCheck={false} />
      <p id="asset-statistics-help">Asset statistics use every supplied interval without exposure weighting or annualization. Their separate results are not included in v1 Risk Lab receipt replay.</p>
      <div className="risk-comparison-actions"><button className="primary-button" type="submit">{busy ? "Restart calculation" : "Calculate hypothetical risk"}</button><button className="secondary-button" style={{marginTop:0}} type="submit" name="calculation" value="statistics" aria-describedby="asset-statistics-help">Calculate asset statistics</button><button className="secondary-button" style={{marginTop: 0}} type="button" onClick={cancel} disabled={!busy}>Cancel calculation</button></div>
    </form>
    <HypotheticalReplay method="risk" receipt={receipt} busy={busy} form={form} generation={generation} revision={revision} restored={()=>{edit();setStatus("Imported hypothetical assumptions. Review inputs and calculate explicitly for a fresh result.");}}/>
    <p role="status" aria-live="polite" style={{margin: "16px 0"}}>{status}</p>{error && <p role="alert">{error}</p>}
    {statistics && <HypotheticalPanelStatistics receipt={statistics}/>}
    {r && <section className="panel" aria-labelledby="risk-result"><h2 id="risk-result">Hypothetical sample results</h2>
      <p>{r.scenario_count} scenarios · horizon {r.horizon} supplied intervals · confidence {receipt.inputs.confidence} · {r.reporting_currency}</p>
      <p>{r.overlapping ? `Overlapping windows share ${r.horizon - 1} intervals with adjacent chronological windows. They are not independent observations.` : "No overlapping scenario windows."} These computational minima do not establish statistical adequacy or future coverage.</p>
      <p>Positive values mean losses; negative values remain gains. VaR uses the empirical nearest rank. ES uses fractional tail mass with equal mass across exact threshold ties.</p>
      <dl className="comparison-values" style={{gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 210px), 1fr))"}}>{([["VaR", r.var], ["Expected Shortfall", r.es], ["VaR (%)", r.var_percent], ["Expected Shortfall (%)", r.es_percent]] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd className="wrap-anywhere">{value.exact ? value.exact.display : `Unavailable: ${unavailable[value.reason ?? ""] ?? "unverified result"}`}</dd></div>)}</dl>
      <p className="wrap-anywhere">Net exposure {r.net_exposure.display} · gross exposure {r.gross_exposure.display}. Percentages require a separately declared positive portfolio value.</p>
      <p className="wrap-anywhere">Rank {r.rank ?? "unavailable"} · tail mass {r.tail_mass.display} · strict tail count {r.strict_tail_count} · threshold tie count {r.threshold_tie_count}.</p>
      <p>Display rounds to 18 decimal places, HALF_EVEN. Exact fractions and full normalized inputs are retained below.</p>
      <details><summary>Complete loss and tail audit</summary>
        <div role="region" aria-label="Scenario loss audit" tabIndex={0} style={{overflowX: "auto"}}><table><caption>Sorted by exact loss, then scenario ID. Tail mass is observation mass, not probability.</caption><thead><tr><th scope="col">Intervals (start inclusive, stop exclusive)</th><th scope="col">Scenario ID</th><th scope="col">Loss (exact)</th><th scope="col">Tail mass (exact)</th></tr></thead><tbody>{r.scenarios.map(s => <tr key={s.start_index}><td>{s.start_index}–{s.stop_index}</td><td>{s.scenario_id.join(" / ")}</td><td>{s.loss.numerator}/{s.loss.denominator}</td><td>{s.tail_mass ? `${s.tail_mass.numerator}/${s.tail_mass.denominator}` : "Unavailable"}</td></tr>)}</tbody></table></div>
        <details><summary>Full replay receipt and normalized inputs</summary><pre tabIndex={0} aria-label="Exact replay receipt" style={{whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxHeight: 600, overflow: "auto"}}>{JSON.stringify(receipt, null, 2)}</pre></details>
      </details>
    </section>}
  </main>;
}
