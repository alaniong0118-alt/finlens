"use client";
import { useId, useState, type FormEvent } from "react";
import type { FilingContext } from "@/lib/finlens-api";
import { evidencePassages, formatDate } from "@/lib/research";
import { comparePassageText, type PassageDiff } from "@/lib/passage-diff";

/** Receives only the owning, settled, validated two-filing snapshot. */
export default function FilingPassageComparison({ results }: { results: [FilingContext, FilingContext] }) {
  const id = useId();
  const passages = results.map(evidencePassages);
  const [selection, setSelection] = useState<[string, string]>(["", ""]);
  const [diff, setDiff] = useState<PassageDiff | null>(null);
  const chosen = passages.map((items, index) => items.find(item => item.citation.citation_id === selection[index]));
  const ready = chosen.every(Boolean);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (chosen[0] && chosen[1]) setDiff(comparePassageText(chosen[0].text, chosen[1].text));
  }
  return <section className="filing-passage-comparison" aria-labelledby={`${id}-title`}>
    <h4 id={`${id}-title`}>Inspect wording across two excerpts</h4>
    <p id={`${id}-help`} className="small muted">Choose one returned excerpt from each filing, then compare their exact wording locally. Excerpts are not paired automatically: matching retrieval ranks do not establish equivalent disclosures. A and B follow your filing selection, not chronology.</p>
    <p className="small muted">This is an alignment of stored cleaned excerpts, not a complete-filing redline or proof of a business change, contradiction, cause, risk level or amendment. Reporting periods and substantive comparability remain unverified. No AI or new search is used.</p>
    <form onSubmit={submit} aria-describedby={`${id}-help`}>
      <div className="dual-filing-controls">{passages.map((items, index) => <label key={index}>Excerpt from filing {index === 0 ? "A" : "B"}<select value={selection[index]} disabled={!items.length}
        onChange={event => { const next: [string, string] = [...selection]; next[index] = event.target.value; setSelection(next); setDiff(null); }}>
        <option value="">Select an excerpt explicitly</option>
        {items.map(item => <option key={item.citation.citation_id} value={item.citation.citation_id}>Excerpt {item.rank} · {item.citation.chunk_id}</option>)}
      </select></label>)}</div>
      {!passages.every(items => items.length > 0) && <p className="notice">Both filings need a qualifying returned excerpt to compare wording. Missing search evidence does not establish absence from a filing.</p>}
      <button className="secondary-button" disabled={!ready}>Compare selected wording</button>
    </form>
    <p className="small" role="status" aria-live="polite">{diff?.status === "unavailable" ? diff.reason
      : diff?.status === "compared" ? diff.identical ? "The two selected excerpts have identical wording, including whitespace. This does not establish that the filings are identical."
        : "Exact wording alignment ready. A-only and B-only refer only to this selected pair; different text is not a verified substantive change."
        : "Select an excerpt on each side and compare. Selecting an excerpt clears the previous alignment."}</p>
    {ready && <div className="dual-filing-columns passage-comparison-columns">{chosen.map((item, index) => item && <section key={index} className="passage-comparison-side" aria-labelledby={`${id}-side-${index}`}>
      <h5 id={`${id}-side-${index}`}>Selected excerpt · Filing {index === 0 ? "A" : "B"} · Excerpt {item.rank}</h5>
      <p className="small wrap-anywhere">{item.citation.form} · Filed {formatDate(item.citation.filed)} · {item.citation.accession_number}/{item.citation.citation_id}</p>
      {diff?.status === "compared" && <div className="passage-alignment" aria-label={`Exact wording alignment for filing ${index === 0 ? "A" : "B"}`}>
        <p className="small">Bracket labels identify text only in {index === 0 ? "A" : "B"} in this alignment. Unlabelled text is shared.</p>
        <div className="excerpt passage-alignment-text">{diff.spans.filter(span => span.kind !== (index === 0 ? "b_only" : "a_only")).map((span, position) => span.kind === "shared" ? <span key={position} data-wording="shared">{span.text}</span>
          : <span key={position} className={`passage-wording-${index === 0 ? "a" : "b"}`} data-wording={span.kind}><span className="passage-wording-label">[{index === 0 ? "A" : "B"}-only: </span><span data-wording-text>{span.text}</span><span className="passage-wording-label">]</span></span>)}</div>
      </div>}
      <details className="provenance"><summary>Full original excerpt and source · Filing {index === 0 ? "A" : "B"}</summary><div className="details-body wrap-anywhere">
        <p className="excerpt passage-original">{item.text}</p>
        <p className="small">{results[index].ticker} · {results[index].company_name} · {item.citation.accession_number}/{item.citation.citation_id}</p>
        <p className="small">{item.citation.chunk_id} · {item.citation.filename} · Cleaned source offsets {item.citation.start_char}–{item.citation.end_char}. These are source metadata, not character offsets in the alignment.</p>
        <a className="source-link" href={item.citation.sec_url} target="_blank" rel="noopener noreferrer">Open official SEC source ↗</a>
      </div></details>
    </section>)}</div>}
  </section>;
}
