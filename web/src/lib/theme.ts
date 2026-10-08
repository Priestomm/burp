import { cookies } from "next/headers";

export const THEMES = ["adesivi", "zine"] as const;
export type Theme = (typeof THEMES)[number];
export const THEME_COOKIE = "burp-theme";

export function isTheme(value: unknown): value is Theme {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

/** The chosen look: the cookie, else BURP_THEME, else Adesivi. Call it inside Suspense. */
export async function getTheme(): Promise<Theme> {
  const value = (await cookies()).get(THEME_COOKIE)?.value;
  if (isTheme(value)) return value;
  return isTheme(process.env.BURP_THEME) ? process.env.BURP_THEME : "adesivi";
}
