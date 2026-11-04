"use client";
import {useEffect, useRef, useState} from "react";
import {HypotheticalReplay} from "./hypothetical-replay";
import {requestStress, stressFormInputs, type StressReceipt, type StressOutcome} from "../lib/hypothetical-stress";

const inputStyle={width:"100%",minWidth:0,font:"inherit",padding:10,border:"1px solid var(--border)",borderRadius:8,background:"var(--card)",color:"var(--text)",minHeight:44};
function Contributions({outcome, label}: {outcome: StressOutcome; label: string}) {
  return <div role="region" aria-label={label} tabIndex={0} style={{overflowX:"auto",marginTop:12}}><table>
    <caption>{label}. Currency amounts; positive loss means loss. Zero shocks are explicit.</caption>
    <thead><tr><th scope="col">Exposure ID</th><th scope="col">Signed notional</th><th scope="col">Shock (%)</th><th scope="col">P&amp;L</th><th scope="col">Loss</th></tr></thead>
    <tbody>{outcome.contributions.map(c=><tr key={c.asset_id}><th scope="row">{c.asset_id}</th><td>{c.exposure.display}</td><td>{c.shock_percent.display}</td><td>{c.pnl.display}</td><td>{c.loss.display}</td></tr>)}</tbody>
    <tfoot><tr><th scope="row" colSpan={3}>Total</th><td>{outcome.total_pnl.display}</td><td>{outcome.total_loss.display}</td></tr></tfoot>
  </table></div>;
}
export function HypotheticalStress() {
  const form = useRef<HTMLFormElement | null>(null);
  const [revision, setRevision] = useState(0);
  const [receipt,setReceipt]=useState<StressReceipt|null>(null),[status,setStatus]=useState("Enter explicit hypothetical exposures and shocks."),[error,setError]=useState<string|null>(null),[busy,setBusy]=useState(false);
  const generation=useRef(0),controller=useRef<AbortController|null>(null),timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  function invalidate() {generation.current++;setRevision(generation.current);controller.current?.abort();controller.current=null;if(timer.current)clearTimeout(timer.current);timer.current=null;}
  useEffect(()=>()=>{generation.current++;controller.current?.abort();if(timer.current)clearTimeout(timer.current);},[]);
  function edit() {invalidate();setReceipt(null);setError(null);setBusy(false);setStatus("Inputs changed. Calculate again for a current result.");}
  function cancel() {invalidate();setReceipt(null);setError(null);setBusy(false);setStatus("Calculation cancelled. Submit explicitly to retry.");}
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();invalidate();setReceipt(null);setError(null);setBusy(false);
    try {
      const inputs=stressFormInputs(event.currentTarget),id=generation.current,active=new AbortController();controller.current=active;setBusy(true);setStatus("Calculating conditional hypothetical P&L…");
      timer.current=setTimeout(()=>{if(id!==generation.current)return;invalidate();setBusy(false);setStatus("");setError("Calculation timed out. Submit explicitly to retry.");},10000);
      try {const result=await requestStress(inputs,active.signal);if(id!==generation.current||active.signal.aborted)return;setReceipt(result);setStatus("Hypothetical stress calculation complete. Review contributions and assumptions.");}
      catch(reason) {if(id!==generation.current||active.signal.aborted)return;setError(reason instanceof Error?reason.message:"Calculation failed. Retry explicitly.");setStatus("");}
      finally {if(id===generation.current){if(timer.current)clearTimeout(timer.current);timer.current=null;controller.current=null;setBusy(false);}}
    } catch(reason) {setError(reason instanceof Error?reason.message:"Check your inputs.");setStatus("");}
  }
  const r=receipt?.result;
  return <main className="workspace" style={{maxWidth:1100}}>
    <header className="hero"><p className="eyebrow">FinLens · Risk Lab development candidate</p><h1>Hypothetical linear price stress</h1><p>User-entered assumptions for an educational conditional calculation. These scenarios are not observed market data, probabilities, forecasts, recommendations or financial advice.</p></header>
    <section className="panel" aria-labelledby="stress-assumptions"><h2 id="stress-assumptions">Supported model and limits</h2>
      <p>Only fixed, signed linear price notionals in one explicitly declared currency. Positive amounts are long; negative amounts are short. P&amp;L = signed notional × shock percentage ÷ 100; loss = −P&amp;L. A shock of −10 means a 10% price decline. Enter 0 explicitly for no change.</p>
      <p>No options, derivatives, bond duration, FX, share counts, causal mappings, fees, financing or rebalancing. Currency codes and exposure dates are user assertions. Asset labels do not verify a real instrument. Offsetting common shocks do not prove absence of risk.</p>
      <p>1–8 assets, 1–12 named scenarios and 1–21 distinct common shocks. Every asset needs a shock in every named scenario, including zero exposures. Shocks: −100% to +1000% inclusive; the upper limit is an application bound, not a suggested scenario. Exact ordinary decimal strings, at most 24 digits and 12 decimal places; no exponent notation. Request 128 KiB, response 1 MiB.</p>
      <p>One worker slot is shared with historical Risk Lab. Cancel stops display and transport; already running bounded work may finish. No automatic retry or browser-stored inputs. Local receipt files remain under your control.</p>
    </section>
    <form ref={form} className="panel" style={{marginTop:20}} onSubmit={submit} onInput={edit} onChange={edit}>
      <h2>Explicit hypothetical inputs</h2><div className="comparison-values">
        <label>Reporting currency<input name="currency" required defaultValue="USD" maxLength={3} pattern="[A-Z]{3}" style={inputStyle}/></label>
        <label>Exposure date<input name="date" type="date" required style={inputStyle}/></label>
        <div><p className="small">Exposure type</p><p>Linear price notional only</p></div>
      </div>
      <label htmlFor="stress-exposures">Signed exposures</label><p id="stress-exposure-help" className="small muted">One line: exposure_id signed_notional. All use the reporting currency and the linear price model. IDs are 1–64 ASCII token characters; use no spaces in an ID.</p>
      <textarea id="stress-exposures" name="exposures" required rows={4} maxLength={1200} spellCheck={false} aria-describedby="stress-exposure-help"/>
      <label htmlFor="stress-scenarios" style={{marginTop:16}}>Named scenario shocks (%)</label><p id="stress-scenario-help" className="small muted">One line: scenario_id shock_for_first_exposure shock_for_second_exposure … Follow the exposure order above. Every shock is explicit. Names are distinct token IDs, not probabilities.</p>
      <textarea id="stress-scenarios" name="scenarios" required rows={5} maxLength={6000} spellCheck={false} aria-describedby="stress-scenario-help"/>
      <label htmlFor="stress-common" style={{marginTop:16}}>Common shock sensitivity (%)</label><p id="stress-common-help" className="small muted">Enter 1–21 distinct percentages separated by spaces or newlines. Each is applied equally to every exposure, independently of named scenarios. Common shocks are not added to named shocks.</p>
      <textarea id="stress-common" name="common" required rows={3} maxLength={800} spellCheck={false} aria-describedby="stress-common-help"/>
      <div className="risk-comparison-actions"><button className="primary-button" type="submit">{busy?"Restart stress calculation":"Calculate hypothetical stress"}</button><button className="secondary-button" style={{marginTop:0}} type="button" disabled={!busy} onClick={cancel}>Cancel calculation</button></div>
    </form>
    <HypotheticalReplay method="stress" receipt={receipt} busy={busy} form={form} generation={generation} revision={revision} restored={()=>{edit();setStatus("Imported hypothetical assumptions. Review inputs and calculate explicitly for a fresh result.");}}/>
    <p role="status" aria-live="polite" style={{margin:"16px 0"}}>{status}</p>{error&&<p role="alert">{error}</p>}
    {r&&<section className="panel" aria-labelledby="stress-results"><h2 id="stress-results">Conditional stress results</h2>
      <p className="wrap-anywhere">{r.reporting_currency} · exposure date {r.exposure_date} · net {r.net_exposure.display} · gross {r.gross_exposure.display}.</p>
      <p className="small muted">On narrow screens, tables scroll horizontally. Focus a table and use the Left/Right arrow keys, or swipe to inspect all columns.</p>
      <p>Positive P&amp;L means gain; positive loss means loss. Negative values retain their signs. All displayed numbers round to 18 decimal places, HALF_EVEN; exact fractions remain in the receipt.</p>
      {r.scenarios.map(s=><section key={s.scenario_id} style={{marginTop:20}} aria-label={`Named scenario ${s.scenario_id}`}><h3 className="wrap-anywhere">{s.scenario_id}</h3><Contributions outcome={s} label={`Contribution audit ${s.scenario_id}`}/></section>)}
      <section aria-labelledby="common-sensitivity" style={{marginTop:24}}><h3 id="common-sensitivity">Common-shock sensitivity</h3>
        <p className="wrap-anywhere">Each +1 percentage point common shock changes P&amp;L by {r.common_shock_pnl_per_percentage_point.display} {r.reporting_currency}. These shocks are independent of named scenarios; zero net exposure may offset this common move without removing other risks.</p>
        <div role="region" aria-label="Common shock totals" tabIndex={0} style={{overflowX:"auto"}}><table><caption>Explicit common percentage applied equally to all positions; sorted by exact shock.</caption><thead><tr><th scope="col">Shock (%)</th><th scope="col">Total P&amp;L</th><th scope="col">Total loss</th></tr></thead><tbody>{r.common_shock_sensitivity.map(s=><tr key={`${s.shock_percent.numerator}/${s.shock_percent.denominator}`}><th scope="row">{s.shock_percent.display}</th><td>{s.total_pnl.display}</td><td>{s.total_loss.display}</td></tr>)}</tbody></table></div>
        <details><summary>Common-shock contribution audits</summary>{r.common_shock_sensitivity.map((s,i)=><Contributions key={i} outcome={s} label={`Common shock ${s.shock_percent.display}%`}/>)}</details>
      </section>
      <p className="small wrap-anywhere" style={{marginTop:16}}>Method: {r.method_id}. No probability, forecast, historical calibration or advice is implied.</p>
      <details><summary>Exact stress replay receipt</summary><pre aria-label="Exact stress receipt" tabIndex={0} style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:600,overflow:"auto"}}>{JSON.stringify(receipt,null,2)}</pre></details>
    </section>}
  </main>;
}
