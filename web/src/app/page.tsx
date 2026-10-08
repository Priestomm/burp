import Form from "next/form";
import { Suspense } from "react";
import { SiteHeader } from "@/components/SiteHeader";
import { StickerSheet } from "@/components/library/StickerSheet";
import { ApiError, type LibraryItem, api } from "@/lib/api/server";
import styles from "./page.module.css";

export default function LibraryPage(props: PageProps<"/">) {
  return (
    <>
      <SiteHeader />
      <main className={styles.page}>
        <h1 className="cond">La tua libreria</h1>
        <Form action="/" className={styles.search} role="search">
          <label htmlFor="q" className="sr-only">
            Cerca per titolo, tag o ingrediente
          </label>
          <input id="q" name="q" type="search" placeholder="cerca: «vegana ceci», «zucca»…" />
          <button type="submit" className="cond">
            Cerca
          </button>
        </Form>
        <Suspense fallback={<p>Carico la libreria…</p>}>
          <Library searchParams={props.searchParams} />
        </Suspense>
      </main>
    </>
  );
}

async function Library({ searchParams }: { searchParams: PageProps<"/">["searchParams"] }) {
  const { q } = await searchParams;
  const query = typeof q === "string" ? q.trim() : "";
  let items: LibraryItem[];
  try {
    items = await api.listRecipes(query || undefined);
  } catch (error) {
    return <p role="alert">{error instanceof ApiError ? error.message : "Errore imprevisto."}</p>;
  }
  if (items.length === 0) {
    return (
      <p>
        {query
          ? `Nessuna ricetta per «${query}».`
          : "Ancora nessuna ricetta: inoltra un reel al bot Telegram per cominciare."}
      </p>
    );
  }
  return (
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
  );
}
