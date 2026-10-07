const API_PREFIX = "/api/finlens";

export type Company = {
  id: number;
  ticker: string;
  name: string;
  cik: string;
  exchange: string;
  has_indexed_filing: boolean;
  indexed_filing_count: number;
};

export function firstReadyCompany(companies: Company[]): Company | undefined {
  return companies.find((company) => company.has_indexed_filing) ?? companies[0];
}

export function readyCompanyCount(companies: Company[]): number {
  return companies.filter((company) => company.has_indexed_filing).length;
}

export type FilingSource = {
  accession_number: string;
  form: string | null;
  filed: string | null;
  period_start: string | null;
  period_end: string | null;
  metrics: string[];
  sec_url: string;
  has_filing_chunks: boolean;
};

export type Citation = {
  citation_id: string;
  chunk_id: string;
  accession_number: string;
  form: string;
  filed: string | null;
  filename: string;
  start_char: number;
  end_char: number;
  sec_url: string;
  similarity: number;
  semantic_similarity: number;
  lexical_score: number;
  hybrid_score: number;
  evidence_reason: string;
};

export type AnswerClaim = {
  text: string;
  citation_ids: string[];
};

export type FilingAnswer = {
  ticker: string;
  company_name: string;
  accession_number: string;
  question: string;
  answer: string;
  claims: AnswerClaim[];
  citations: Citation[];
  evidence_status: "sufficient" | "insufficient";
  insufficient_evidence: boolean;
  model: string;
};

export class FinLensApiError extends Error {
  public readonly status: number;
  public readonly code: string | null;

  constructor(
    message: string,
    status: number,
    code: string | null,
  ) {
    super(message);
    this.name = "FinLensApiError";
    this.status = status;
    this.code = code;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      cache: "no-store",
      ...init,
    });
  } catch {
    if (init?.signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
    throw new FinLensApiError(
      "Cannot reach the FinLens backend. Check that it is running.",
      0,
      "NETWORK_ERROR",
    );
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : null;
    const message = typeof detail === "string"
      ? detail
      : `FinLens returned HTTP ${response.status}.`;
    throw new FinLensApiError(
      message,
      response.status,
      response.headers.get("X-FinLens-Error-Code"),
    );
  }
  if (payload === null) {
    throw new FinLensApiError("FinLens returned an empty response.", 502, "INVALID_RESPONSE");
  }
  return payload as T;
}

export function getCompanies(signal?: AbortSignal): Promise<Company[]> {
  return requestJson<Company[]>("/companies", { signal });
}

export function getFilingSources(ticker: string, signal?: AbortSignal): Promise<FilingSource[]> {
  return requestJson<FilingSource[]>(
    `/companies/${encodeURIComponent(ticker)}/sources`,
    { signal },
  );
}

export function getAnswer(
  ticker: string,
  accessionNumber: string,
  question: string,
  limit = 5,
  signal?: AbortSignal,
): Promise<FilingAnswer> {
  return requestJson<FilingAnswer>(
    `/companies/${encodeURIComponent(ticker)}/filings/${encodeURIComponent(accessionNumber)}/answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, limit }),
      signal,
    },
  );
}

export function searchableFilings(filings: FilingSource[]): FilingSource[] {
  return filings.filter((filing) => filing.has_filing_chunks);
}

export function citationForClaim(
  citationId: string,
  citations: Citation[],
): Citation | undefined {
  return citations.find((citation) => citation.citation_id === citationId);
}

export function describeApiError(error: unknown): string {
  if (!(error instanceof FinLensApiError)) {
    return "Something went wrong while loading FinLens. Please try again.";
  }
  if (error.code === "LLM_UNAVAILABLE") {
    return "AI analysis is currently unavailable. Your SEC evidence remains available in Research Mode.";
  }
  if (error.code === "LLM_TIMEOUT") {
    return "AI analysis timed out. Your SEC evidence remains available in Research Mode.";
  }
  if (error.code === "MALFORMED_MODEL_OUTPUT") {
    return "The model response did not pass citation checks. No answer was shown.";
  }
  if (error.code === "UPSTREAM_FAILURE") {
    return "AI analysis is currently unavailable. Your SEC evidence remains available in Research Mode.";
  }
  return error.message;
}

export type Capabilities = { research_mode: boolean; ai_analysis_configured: boolean };
export type PeriodKind = "quarter" | "half_year" | "nine_months" | "annual" | "instant";
export type FinancialPeriod = {
  kind: PeriodKind; start: string | null; end: string;
  fiscal_year: number | null; fiscal_period: string | null; fiscal_label_basis: string;
};
export type FactProvenance = {
  fact_id: number; original_concept: string; value: string; unit: string;
  period_start: string | null; period_end: string; form: string; filed: string;
  accession_number: string; sec_url: string; company_cik: string;
  source_fiscal_year: number | null; source_fiscal_period: string | null;
};
export type NormalizedMetric = {
  metric: string; unit: string; status: "available" | "unavailable" | "not_applicable";
  value: string | null; reason: string | null; period: FinancialPeriod | null;
  formula: string | null; revenue_basis?: string;
  provenance: FactProvenance[]; alternatives: FactProvenance[];
  inputs: { role: string; metric: string; value: string; unit: string; fact_ids: number[]; revenue_basis?: string }[];
};
export type FinancialSummary = {
  ticker: string; company_name: string; company_cik: string;
  requested_period: PeriodKind; period: FinancialPeriod | null;
  metrics: Record<string, NormalizedMetric>; selection_policy: string;
};
export type MetricHistory = {
  ticker: string; company_cik: string; metric: string; unit: string; requested_period: PeriodKind;
  status: NormalizedMetric["status"]; reason: string | null; history: NormalizedMetric[];
  comparability?: { value_basis: "reported_as_filed"; status: "unverified"; reason: string };
};
export type FilingContext = {
  ticker: string; company_name: string; accession_number: string; query: string;
  context: string; citations: Citation[]; evidence_status: "sufficient" | "insufficient";
};

export type ResearchAnswer = {
  ticker: string; company_name: string; question: string; matched: boolean;
  status: "available" | "unavailable" | "not_applicable" | "not_matched" | "company_mismatch";
  metric: string | null; metric_label: string | null;
  period_intent: "quarter" | "annual" | "latest_available" | null;
  formatted_value: string | null; answer_text: string | null; explanation: string | null;
  observation: NormalizedMetric | null; comparability: MetricHistory["comparability"] | null;
  selection_policy: string;
};

export function getResearchAnswer(ticker: string, question: string, signal?: AbortSignal): Promise<ResearchAnswer> {
  return requestJson(`/companies/${encodeURIComponent(ticker)}/research-answer`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }), signal,
  });
}

export function getCapabilities(signal?: AbortSignal): Promise<Capabilities> {
  return requestJson("/capabilities", { signal });
}
export function getFinancialSummary(ticker: string, period: PeriodKind, signal?: AbortSignal): Promise<FinancialSummary> {
  return requestJson(`/companies/${encodeURIComponent(ticker)}/financials/summary?period=${period}`, { signal });
}
export function getMetricHistory(ticker: string, metric: string, period: PeriodKind, signal?: AbortSignal): Promise<MetricHistory> {
  return requestJson(`/companies/${encodeURIComponent(ticker)}/financials/metrics/${encodeURIComponent(metric)}?period=${period}&limit=12`, { signal });
}
export function getFilingContext(ticker: string, accession: string, query: string, signal?: AbortSignal): Promise<FilingContext> {
  const params = new URLSearchParams({ q: query, limit: "5" });
  return requestJson(`/companies/${encodeURIComponent(ticker)}/filings/${encodeURIComponent(accession)}/context?${params}`, { signal });
}
