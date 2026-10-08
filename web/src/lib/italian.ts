/**
 * "quanto cipollotto e quanti semi di sesamo": the question in the missing-quantities notice.
 * Canonical names are singular, so the ending of the first word gives the gender (-a feminine,
 * anything else masculine: sale, latte, pane) and -i a plural. Exceptions cover feminine words
 * in -e and things counted one by one, where "quanti tuorli" sounds right and "quanto" does not.
 */
const EXCEPTIONS: Record<string, string> = {
  noce: "quanta noce",
  carne: "quanta carne",
  erbe: "quante erbe",
  uovo: "quante uova",
  uova: "quante uova",
  tuorlo: "quanti tuorli",
  albume: "quanti albumi",
  mela: "quante mele",
  spicchio: "quanti spicchi",
};

export function howMuch(name: string): string {
  const [head, ...rest] = name.trim().split(/\s+/);
  const exception = EXCEPTIONS[head.toLowerCase()];
  if (exception) return [exception, ...rest].join(" ");
  if (head.endsWith("i")) return `quanti ${name}`;
  if (head.endsWith("a")) return `quanta ${name}`;
  return `quanto ${name}`;
}

/** "a, b e c" */
export function list(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} e ${items.at(-1)}`;
}

export function missingNotice(names: string[]): string {
  if (names.length === 0) return "";
  if (names.length > 3) return `Nel reel non dicono le quantità di ${names.length} ingredienti. Va bene a occhio?`;
  return `Nel reel non dicono ${list(names.map(howMuch))}. Va bene a occhio?`;
}
