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

export function getCompanies(): Promise<Company[]> {
  return requestJson<Company[]>("/companies");
}

export function getFilingSources(ticker: string): Promise<FilingSource[]> {
  return requestJson<FilingSource[]>(
    `/companies/${encodeURIComponent(ticker)}/sources`,
  );
}

export function getAnswer(
  ticker: string,
  accessionNumber: string,
  question: string,
  limit = 5,
): Promise<FilingAnswer> {
  return requestJson<FilingAnswer>(
    `/companies/${encodeURIComponent(ticker)}/filings/${encodeURIComponent(accessionNumber)}/answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, limit }),
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
    return "The answer service is not configured yet. Set OPENAI_API_KEY in the backend environment.";
  }
  if (error.code === "LLM_TIMEOUT") {
    return "The answer service timed out. Please try again.";
  }
  if (error.code === "MALFORMED_MODEL_OUTPUT") {
    return "The model response did not pass citation checks. No answer was shown.";
  }
  if (error.code === "UPSTREAM_FAILURE") {
    return "The answer provider is unavailable. Please try again later.";
  }
  return error.message;
}
