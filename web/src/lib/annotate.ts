/**
 * What the marker underlines in the steps: times and temperatures, the things not to get
 * wrong. Found in the text, so every recipe gets its notes without writing them by hand.
 */

const NUMBER = String.raw`\d+(?:[.,]\d+)?`;
const RANGE = String.raw`${NUMBER}(?:\s*(?:-|–|a|o)\s*${NUMBER})?`;
const TIME_UNIT = String.raw`(?:minut[oi]|min|or[ae]|h|second[oi]|sec|giorn[oi])\b`;

export const TIME_OR_TEMPERATURE = new RegExp(
  [
    String.raw`${RANGE}\s*${TIME_UNIT}`, // 7-8 minuti, 1 ora, 30 sec
    String.raw`${RANGE}\s*(?:°(?:\s*C\b)?|gradi\b)`, // 180°, 180 °C, 200 gradi
    String.raw`\b(?:un'?\s?ora|mezz'?\s?ora|un quarto d'ora|una notte|un minuto)\b`,
  ].join("|"),
  "gi",
);

export type Segment = { text: string; mark: boolean };

/** The step split into plain text and the parts to underline. */
export function markTimes(step: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of step.matchAll(TIME_OR_TEMPERATURE)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ text: step.slice(last, start), mark: false });
    segments.push({ text: match[0], mark: true });
    last = start + match[0].length;
  }
  if (last < step.length) segments.push({ text: step.slice(last), mark: false });
  return segments;
}
