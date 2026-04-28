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

// selectedAuthors 是 chip 點選的作者（chip 不寫回 query 字串, 避免含空格 username 被 \s+ 切壞）
// 與 parsed.authors（手打 @author）取聯集
export function matchByTextAndAuthor(
  name: string,
  description: string | null,
  author: string | null,
  parsed: ParsedSearch,
  selectedAuthors: string[] = []
): boolean {
  const authorFilters = [
    ...parsed.authors,
    ...selectedAuthors.map((a) => a.toLowerCase()),
  ];
  if (authorFilters.length > 0) {
    const authorLower = (author ?? "").toLowerCase();
    if (!authorFilters.includes(authorLower)) return false;
  }
  if (!parsed.text) return true;
  const haystack = `${name} ${description ?? ""}`.toLowerCase();
  return haystack.includes(parsed.text);
}

export function toggleAuthorChip(
  selected: string[],
  author: string
): string[] {
  const lower = author.toLowerCase();
  const idx = selected.findIndex((a) => a.toLowerCase() === lower);
  if (idx >= 0) {
    const next = [...selected];
    next.splice(idx, 1);
    return next;
  }
  return [...selected, author];
}
