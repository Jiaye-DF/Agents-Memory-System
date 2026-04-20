export interface ParsedSearch {
  text: string;
  authors: string[];
}

export function parseSearch(query: string): ParsedSearch {
  const tokens = query.trim().split(/\s+/).filter(Boolean);
  const authors: string[] = [];
  const words: string[] = [];
  for (const token of tokens) {
    if (token.startsWith("@") && token.length > 1) {
      authors.push(token.slice(1).toLowerCase());
    } else {
      words.push(token);
    }
  }
  return { text: words.join(" ").toLowerCase(), authors };
}

export function matchByTextAndAuthor(
  name: string,
  description: string | null,
  author: string | null,
  parsed: ParsedSearch
): boolean {
  if (parsed.authors.length > 0) {
    const authorLower = (author ?? "").toLowerCase();
    if (!parsed.authors.includes(authorLower)) return false;
  }
  if (!parsed.text) return true;
  const haystack = `${name} ${description ?? ""}`.toLowerCase();
  return haystack.includes(parsed.text);
}

export function toggleAuthorInQuery(query: string, author: string): string {
  const tokens = query.trim().split(/\s+/).filter(Boolean);
  const target = `@${author}`.toLowerCase();
  const idx = tokens.findIndex((t) => t.toLowerCase() === target);
  if (idx >= 0) {
    tokens.splice(idx, 1);
  } else {
    tokens.push(`@${author}`);
  }
  return tokens.join(" ");
}
