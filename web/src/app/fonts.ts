import { Big_Shoulders, Bricolage_Grotesque, Erica_One, Gloock, Work_Sans } from "next/font/google";

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

// Zine theme. Not preloaded: only pages in that theme use them.

/** Recipe titles, issue numbers, the giant "burp!" at the bottom. */
export const wide = Erica_One({
  subsets: ["latin", "latin-ext"],
  weight: "400",
  variable: "--font-wide",
  display: "swap",
  preload: false,
});

/** Everything else in the Zine: menu in 400, captions and tables in 700. */
export const grot = Work_Sans({
  subsets: ["latin", "latin-ext"],
  weight: "variable",
  variable: "--font-grot",
  display: "swap",
  preload: false,
});
