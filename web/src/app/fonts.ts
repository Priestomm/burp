import { Erica_One, Work_Sans } from "next/font/google";

/** Recipe titles, issue numbers, the giant "burp!" at the bottom. */
export const wide = Erica_One({
  subsets: ["latin", "latin-ext"],
  weight: "400",
  variable: "--font-wide",
  display: "swap",
});

/** Everything else: menu in 400, captions and tables in 700. */
export const grot = Work_Sans({
  subsets: ["latin", "latin-ext"],
  weight: "variable",
  variable: "--font-grot",
  display: "swap",
});
