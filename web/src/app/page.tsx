import Form from "next/form";
import { Suspense } from "react";
import { SiteHeader } from "@/components/SiteHeader";
import { StickerSheet } from "@/components/library/StickerSheet";
import { Loading } from "@/components/Loading";
import { ZineLibrary } from "@/components/zine/ZineLibrary";
import { ApiError, type LibraryItem, api } from "@/lib/api/server";
import { type Theme, getTheme } from "@/lib/theme";
import styles from "./page.module.css";

export default function LibraryPage(props: PageProps<"/">) {
  return (
    <Suspense fallback={null}>
      <Themed searchParams={props.searchParams} />
    </Suspense>
  );
}

async function Themed({ searchParams }: { searchParams: PageProps<"/">["searchParams"] }) {
  const theme = await getTheme();
  return (
    <Suspense fallback={<Loading theme={theme} label="apro la libreria…" />}>
      <Library searchParams={searchParams} theme={theme} />
    </Suspense>
  );
}

async function Library({
  searchParams,
  theme,
}: {
  searchParams: PageProps<"/">["searchParams"];
  theme: Theme;
}) {
  const params = await searchParams;
  const query = typeof params.q === "string" ? params.q.trim() : "";
  const toCook = params["da-cucinare"] === "1";
  let items: LibraryItem[];
  try {
    items = await api.listRecipes(query || undefined);
  } catch (error) {
    return <p role="alert" style={{ padding: 24 }}>{error instanceof ApiError ? error.message : "Errore imprevisto."}</p>;
  }
  if (toCook) items = items.filter((item) => item.cooked.count === 0);
  const heading = toCook ? "Da cucinare" : "La tua libreria";

  if (theme === "zine") return <ZineLibrary items={items} query={query} heading={heading} />;

  return (
    <>
      <SiteHeader />
      <main className={styles.page}>
        <h1 className="cond">{heading}</h1>
        <Form action="/" className={styles.search} role="search">
          <label htmlFor="q" className="sr-only">
            Cerca per titolo, tag o ingrediente
          </label>
          <input id="q" name="q" type="search" defaultValue={query} placeholder="cerca: «vegana ceci», «zucca»…" />
          <button type="submit" className="cond">
            Cerca
          </button>
        </Form>
        {items.length === 0 ? (
          <p>
            {query
              ? `Nessuna ricetta per «${query}».`
              : toCook
                ? "Le hai cucinate tutte. Burp!"
                : "Ancora nessuna ricetta: inoltra un reel al bot Telegram per cominciare."}
          </p>
        ) : (
          <>
            {query && (
              <p className={styles.found}>
                {items.length === 1 ? "1 ricetta" : `${items.length} ricette`} per «{query}»
              </p>
            )}
            <div>
              <StickerSheet items={items} layout="grid" />
            </div>
          </>
        )}
      </main>
    </>
  );
}
