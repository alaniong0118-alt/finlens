"use client";
import {useEffect, useRef, useState, type RefObject} from "react";
import {downloadReplay, readReplay, receiptDownloadBytes, restoreReplay, type ReplayMethod, type ReplayReceipt} from "../lib/hypothetical-replay";

export function HypotheticalReplay({method, receipt, busy, form, generation, revision, restored}: {
  method: ReplayMethod; receipt: ReplayReceipt | null; busy: boolean;
  form: RefObject<HTMLFormElement | null>; generation: RefObject<number>; revision: number; restored: () => void;
}) {
  const [reading,setReading]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState<string|null>(null);
  const operation=useRef(0),dispose=useRef<(() => void)|null>(null);
  useEffect(()=>()=>{operation.current++;dispose.current?.();},[]);
  // Parent edits/submits/cancels invalidate file reads synchronously via the shared ref.
  useEffect(()=>{operation.current++;setReading(false);setMessage("");setError(null);},[revision]);
  async function select(event: React.ChangeEvent<HTMLInputElement>) {
    const file=event.currentTarget.files?.[0]; event.currentTarget.value=""; if (!file) return;
    const id=++operation.current, version=generation.current; setReading(true);setMessage("Reading local receipt…");setError(null);
    try {
      const inputs=await readReplay(method,file);
      if(id!==operation.current || version!==generation.current || !form.current) return;
      restoreReplay(form.current,method,inputs); restored();
      setMessage("Imported assumptions only. Supplied results were discarded. Calculate explicitly to obtain a fresh result.");
    } catch {if(id===operation.current && version===generation.current) {setError("Invalid local receipt for this lab. Use supported UTF-8 JSON, at most 1 MiB. Your draft is unchanged.");setMessage("");}}
    finally {if(id===operation.current) setReading(false);}
  }
  function download() {
    try {if(!receipt || busy || reading || !form.current) return; dispose.current?.(); dispose.current=downloadReplay(receiptDownloadBytes(method,receipt,form.current),method);setError(null);setMessage("Local JSON download requested. It contains hypothetical assumptions and derived outputs only.");}
    catch {setError("A current validated result is required for download. Calculate again explicitly.");setMessage("");}
  }
  return <section className="panel" aria-labelledby={`${method}-replay`} style={{marginTop:20,minWidth:0}}>
    <h2 id={`${method}-replay`}>Local receipt replay</h2>
    <p>Download a current result as JSON on your device. Import a receipt from this same lab to restore editable assumptions only. Imported outputs are untrusted and discarded; a fresh calculation needs your explicit submit. No file is uploaded or saved in browser storage.</p>
    <div className="risk-comparison-actions"><button type="button" className="secondary-button" style={{marginTop:0}} disabled={!receipt || busy || reading} onClick={download}>Download current receipt (JSON)</button></div>
    <label htmlFor={`${method}-replay-file`}>Import local {method === "risk" ? "Risk Lab" : "Stress Lab"} receipt (JSON, at most 1 MiB)</label>
    <input id={`${method}-replay-file`} type="file" accept=".json,application/json" aria-describedby={`${method}-replay-help`} onChange={select} style={{display:"block",width:"100%",minWidth:0,marginTop:8,minHeight:44}}/>
    <p id={`${method}-replay-help`} className="small muted">Choose an explicit local file. Other methods and versions reject. Invalid files preserve your draft. To replay, review the restored inputs and use Calculate.</p>
    {reading && <button type="button" className="secondary-button" onClick={()=>{operation.current++;setReading(false);setError(null);setMessage("Local import cancelled. Your draft is unchanged.");}}>Cancel local import</button>}
    <p role="status" aria-live="polite">{message}</p>{error && <p role="alert">{error}</p>}
  </section>;
}
