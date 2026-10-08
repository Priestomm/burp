import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteHeader } from "@/components/SiteHeader";
import { getTheme } from "@/lib/theme";
import { chooseTheme } from "./actions";
import styles from "./page.module.css";

export const metadata: Metadata = { title: "Impostazioni" };

const OPTIONS = [
  {
    value: "adesivi",
    name: "Adesivi",
    text: "Poster da negozio: titolo enorme, foto a retino rosso e nero, i dati sugli adesivi.",
  },
  {
    value: "zine",
    name: "Zine",
    text: "Fanzine su carta gialla: fotocopie ritagliate a forbice, note a pennarello blu.",
  },
] as const;

export default function SettingsPage(props: PageProps<"/impostazioni">) {
  return (
    <>
      <SiteHeader />
      <main className={styles.page}>
        <h1 className="cond">Impostazioni</h1>
        <Suspense fallback={<p>Carico…</p>}>
          <ThemeForm searchParams={props.searchParams} />
        </Suspense>
      </main>
    </>
  );
}

async function ThemeForm({ searchParams }: { searchParams: PageProps<"/impostazioni">["searchParams"] }) {
  const [theme, { salvato }] = await Promise.all([getTheme(), searchParams]);
  return (
    <form action={chooseTheme} className={styles.form}>
      <fieldset>
        <legend>Tema</legend>
        <p className={styles.hint}>Le ricette e i dati sono gli stessi: cambia solo come le vedi.</p>
        {OPTIONS.map((option) => (
          <label key={option.value} className={styles.option}>
            <input type="radio" name="theme" value={option.value} defaultChecked={theme === option.value} />
            <span>
              <b>{option.name}</b>
              <span>{option.text}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <button type="submit" className="cond">
        Salva
      </button>
      {salvato && (
        <p role="status" className={styles.hint}>
          Salvato: tema {theme === "zine" ? "Zine" : "Adesivi"}.
        </p>
      )}
    </form>
  );
}
