const publicationDate = "(?:5 november 2026|november 5,? 2026|2026-11-05)";
const reportQuestion = new RegExp(
  `^what did nintendo report (?:on ${publicationDate}|in its (?:six[- ]month earnings release(?: (?:of|dated) ${publicationDate})?|${publicationDate} earnings release))\\?$`,
  "i",
);
const operatingProfitQuestion = /^why did nintendo['’]s operating profit (?:rise|increase)(?: in the six months ended september 30,? 2026)?\?$/i;

// A closed set of phrasings for the editorial link, separate from issuer or catalog lookup.
export function matchesNintendoIrQuestion(question: string): boolean {
  const normalized = question.trim().replace(/\s+/g, " ");
  return reportQuestion.test(normalized) || operatingProfitQuestion.test(normalized);
}

// These known names and listing identifiers only withhold the editorial guide.
// A match never selects a company or establishes an issuer identity.
export function catalogMayContainNintendo(companies: readonly { name: string; ticker: string }[]): boolean {
  return companies.some(({ name, ticker }) => /nintendo|任天堂/i.test(name.normalize("NFKC"))
    || /(?:^|[^a-z0-9])(?:nintendo|7974|ntdoy|ntdof|jp3756600007)(?:$|[^a-z0-9])/i.test(ticker.normalize("NFKC")));
}
