import Form from "next/form";
import Link from "next/link";
import type { LibraryItem } from "@/lib/api/server";
import styles from "./zine.module.css";

/** The library as the index of a fanzine: issue number, title, what is left to clarify. */
export function ZineLibrary({ items, query, heading }: { items: LibraryItem[]; query: string; heading: string }) {
  return (
    <div className={styles.library}>
      <header className={styles.libraryHead}>
        <p className={styles.h}>
          burp! · <Link href="/impostazioni">impostazioni</Link>
        </p>
        <h1>{heading}</h1>
        <Form action="/" className={styles.search} role="search">
          <label htmlFor="zq" className="sr-only">
            Cerca per titolo, tag o ingrediente
          </label>
          <input id="zq" name="q" type="search" defaultValue={query} placeholder="vegana ceci, zucca…" />
          <button type="submit">cerca</button>
        </Form>
      </header>
      <nav className={styles.issues} aria-label="Ricette">
        <p className={styles.h}>
          {items.length === 0
            ? query
              ? `Nessuna ricetta per «${query}».`
              : "Ancora nessun numero: inoltra un reel al bot per cominciare."
            : `${items.length} ${items.length === 1 ? "numero" : "numeri"}`}
        </p>
        <ol>
          {items.map((item) => (
            <li key={item.id}>
              <Link href={`/ricette/${item.id}`}>
                <span className={styles.n}>N°{item.id}</span>
                <span>{item.title.toLowerCase()}</span>
                <span className={styles.m}>
                  {item.to_clarify === 0 ? "tutto chiaro" : `${item.to_clarify} da chiarire`}
                  {item.cooked.count > 0 ? " · burp!" : ""}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </nav>
      <p className={styles.foot} aria-hidden="true">
        burp!
      </p>
    </div>
  );
}
