// Unpublished metadata-only pilot. No filing contents or retrieval.
export const wynnMacauReferences = {
  disclosure: "https://www.hkexnews.hk/listedco/listconews/sehk/2026/0424/2026042401631_c.pdf",
  regulator: "https://www.dicj.gov.mo/web/EN/information/contacts_casino/content.html",
  documentDate: "2026-04-27",
} as const;

export function supportsWynnMacauNoticeQuestion(text: string): boolean {
  const normalized = text.trim().replace(/\s+/g, " ");
  return /^can (?:a|this) wynn macau(?:,? limited)?(?: \(hkex:? 1128\))? (?:announcement|notice) (?:tell me who holds|confirm who holds) (?:the|a) gaming (?:concession|licen[cs]e)\??$/iu.test(normalized);
}

export function catalogMayContainWynnMacau(companies: readonly { ticker: string; name: string }[]): boolean {
  return companies.some(({ ticker, name }) => (
    /^(?:HKEX:\s*)?0*1128(?:\.HK)?$/i.test(ticker.trim()) || /\bWynn\s+Macau\b/iu.test(name) || /永利澳[門门]/u.test(name)
  ));
}
