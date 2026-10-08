import { Big_Shoulders, Bricolage_Grotesque, Gloock } from "next/font/google";

/** Titles, navigation and ingredient names: condensed, heavy, uppercase. */
export const cond = Big_Shoulders({
  subsets: ["latin", "latin-ext"],
  weight: "variable",
  axes: ["opsz"],
  variable: "--font-cond",
  display: "swap",
  // Next has no metrics for this face to tune a fallback; use a narrow system face instead.
  adjustFontFallback: false,
  fallback: ["Arial Narrow", "sans-serif"],
});

/** Serif details: title adjectives, quantities, the logo. */
export const serif = Gloock({
  subsets: ["latin", "latin-ext"],
  weight: "400",
  variable: "--font-serif",
  display: "swap",
});

/** Running text. */
export const body = Bricolage_Grotesque({
  subsets: ["latin", "latin-ext"],
  weight: "variable",
  axes: ["opsz", "wdth"],
  variable: "--font-body",
  display: "swap",
});
