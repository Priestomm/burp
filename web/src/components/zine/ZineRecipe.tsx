"use client";

import Link from "next/link";
import { useRef } from "react";
import { ARROW, BURP, DIGITS, IO, LOOP, QUANTI, RING, SQUIGGLE } from "@/components/marker/paths";
import { Marker, digitsDrawing } from "@/components/marker/Marker";
import { modelName, useRecipe } from "@/components/recipe/useRecipe";
import type { LibraryItem, RecipeDetail } from "@/lib/api/server";
import { markTimes } from "@/lib/annotate";
import { scale } from "@/lib/dose";
import { doseTable } from "@/lib/doseTable";
import { coursePlural, subtitle } from "@/lib/zineText";
import { DrawingLayer, useDrawing } from "./Drawing";
import { Hand } from "./Hand";
import styles from "./zine.module.css";

const UNITS = ["g", "ml", "cucchiaio", "cucchiaino", "pezzo", "spicchio", "pizzico"];

// Fixed zone, so the server and the browser write the same date.
const DATE = new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "numeric", timeZone: "Europe/Rome" });

/** "Gnocchi" + "di tofu", shorter type the longer the name. */
function titleSize(title: string): "l" | "m" | "s" {
  if (title.length <= 18) return "l";
  if (title.length <= 34) return "m";
  return "s";
}

export function ZineRecipe({ recipe, library }: { recipe: RecipeDetail; library: LibraryItem[] }) {
  const state = useRecipe(recipe);
  const { editing, startEditing, status, pending, inputs, slap, filling, asInReel, setAsInReel } =
    state;
  const { cooked, missing, notice, servings, steps, byEye, fill, unfill, cook, save, undo } = state;
  const sheet = useRef<HTMLElement>(null);
  const drawing = useDrawing(recipe.id, recipe.drawing ?? [], sheet);
  // The rewritten steps and the reel's are different texts: strokes on one stay off the other.
  const stepAnchor = recipe.steps_rewritten && !asInReel ? "rewrite" : "step";

  const title = [recipe.nome_riga_1, recipe.nome_riga_2].filter(Boolean).join(" ");
  const table = doseTable(recipe.ingredients, servings);
  const missingRows = table.rows.filter((row) => row.missing);
  const givenRows = table.rows.filter((row) => !row.missing);
  const position = library.findIndex((item) => item.id === recipe.id);
  const others = library.filter((item) => item.id !== recipe.id);
  const courses = [...new Set(library.map((item) => item.course).filter(Boolean))] as string[];
  // "8.10": day and month without leading zeros, as written by hand.
  const cookedOn = cooked.last
    ? DATE.formatToParts(new Date(cooked.last))
        .filter((part) => part.type === "day" || part.type === "month")
        .map((part) => Number(part.value))
        .join(".")
    : null;

  return (
    <article ref={sheet} className={styles.sheet} aria-busy={pending} data-anchor="sheet">
      <div className={styles.top}>
        <div className={styles.copy} data-anchor="photo">
          {recipe.photo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={recipe.photo.photocopy_src ?? recipe.photo.original_src}
              alt={recipe.photo.alt}
              className={recipe.photo.photocopy_src ? styles.printed : styles.rough}
            />
          ) : (
            <div className={styles.blank} role="img" aria-label={`Nessuna foto del piatto: ${title}`}>
              <span>{title}</span>
            </div>
          )}
          <span className={`${styles.tape} ${styles.t1}`} aria-hidden="true" />
          <span className={`${styles.tape} ${styles.t2}`} aria-hidden="true" />
          <Marker drawing={BURP} width={13} className={styles.scrawl} />
          {recipe.photo?.cutout_src && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={recipe.photo.cutout_src} alt="" className={styles.lift} />
          )}
        </div>

        <nav className={styles.znav} aria-label="Menu" data-anchor="menu">
          <ul>
            <li>
              <Link href="/">libreria</Link>
            </li>
            <li>
              <Link href="/?da-cucinare=1">da cucinare</Link>
            </li>
            <li className={styles.soon}>
              spesa
              <span className="sr-only"> (non ancora disponibile)</span>
            </li>
            <li className={styles.soon}>
              incolla un link
              <span className="sr-only"> (non ancora disponibile)</span>
            </li>
            <li>
              <Link href="/impostazioni">impostazioni</Link>
            </li>
          </ul>
          <ul aria-label="Portate">
            {courses.map((course) => {
              const current = course === recipe.tags.course;
              return (
                <li key={course} className={current ? styles.cur : undefined}>
                  {current && <Hand />}
                  <Link href={`/?q=${encodeURIComponent(course)}`} aria-current={current ? "true" : undefined}>
                    {coursePlural(course)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      <div className={styles.tagline}>
        <span>visto su instagram</span>
        <span>fatto in cucina</span>
      </div>

      <div className={styles.tools}>
        <span className={styles.pen}>
          <button type="button" aria-pressed={drawing.active} onClick={drawing.toggle}>
            {drawing.active ? "fatto" : "pennarello"}
          </button>
          {drawing.active && (
            <>
              <button type="button" onClick={drawing.undo} disabled={drawing.strokes.length === 0}>
                annulla
              </button>
              <button type="button" onClick={drawing.clear} disabled={drawing.strokes.length === 0}>
                cancella tutto
              </button>
              <span>disegna sulla pagina · Esc per uscire</span>
            </>
          )}
          {drawing.problem && (
            <span className={styles.penNote} role="alert">
              {drawing.problem}
            </span>
          )}
        </span>
        {recipe.filled_by ? (
          <>
            <span>Stime e passaggi riscritti da {modelName(recipe.filled_by)}.</span>
            <button type="button" onClick={unfill} disabled={pending}>
              togli le stime
            </button>
            <button type="button" onClick={() => fill(true)} disabled={pending}>
              {filling ? "rigenero…" : "rigenera"}
            </button>
          </>
        ) : (
          <button type="button" onClick={() => fill()} disabled={pending}>
            {filling ? "sto completando…" : recipe.fill_saved ? "rimetti le stime" : "completa con l'AI"}
          </button>
        )}
      </div>

      <div className={styles.spread}>
        <div className={styles.left}>
          <div className={styles.title} data-anchor="title">
            <div>
              <p className={styles.no}>
                ricetta N° {recipe.id}
                {position >= 0 ? ` di ${library.length}` : ""}, salvata da un reel
                {recipe.author_handle ? ` di @${recipe.author_handle}` : ""}
              </p>
              <h1 data-size={titleSize(title)}>{title}</h1>
              <p className={styles.sub}>
                {subtitle(
                  recipe.descrittore,
                  recipe.tags.course ?? null,
                  recipe.tags.cuisine ?? null,
                  recipe.tags.diet,
                )}
              </p>
            </div>
            {recipe.native_word && (
              <p className={styles.tate} lang={recipe.native_word.lang}>
                {recipe.native_word.word}
                <small lang="it">{recipe.native_word.meaning}</small>
              </p>
            )}
          </div>

          <div className={styles.cuts}>
            {recipe.ingredients.map((item) => {
              const line = scale(item, servings ?? 1, servings);
              const amount =
                item.status === "missing"
                  ? "non si sa quanto"
                  : item.status === "estimated"
                    ? `circa ${line.value} (stima)`
                    : line.value;
              return (
                <figure key={item.index} className={styles.cut} data-anchor={`ing-${item.index}`}>
                  {item.image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={item.image.src}
                      alt={item.image.alt}
                      style={{ clipPath: item.image.clip }}
                      className={styles.cutImage}
                    />
                  ) : (
                    <span className={styles.ticket} aria-hidden="true">
                      {item.name}
                    </span>
                  )}
                  <figcaption>
                    {/* A paper slip already shows the name: then the caption is the amount. */}
                    {item.image ? item.name : <span className="sr-only">{item.name}: </span>}
                    <span>{amount}</span>
                  </figcaption>
                </figure>
              );
            })}
          </div>
        </div>

        <div className={styles.right}>
          <div className={styles.dosewrap} data-anchor="dose">
            <table className={styles.dose}>
              <caption>Dosi per persone</caption>
              <thead>
                <tr>
                  <th scope="col">ingrediente</th>
                  {table.columns.map((n) => (
                    <th scope="col" key={n}>
                      {n === 1 ? (
                        <span className={styles.one}>
                          1
                          <Marker drawing={RING} width={3} stretch className={styles.ring} />
                          <Marker drawing={IO} width={5} className={styles.io} />
                          <span className="sr-only"> (io)</span>
                        </span>
                      ) : (
                        n
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {givenRows.map((row) => (
                  <tr key={row.index}>
                    <th scope="row">
                      {row.name}
                      {row.estimated && <span className={styles.est}> †</span>}
                    </th>
                    {row.cells.map((cell, i) => (
                      <td key={i}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
              {missingRows.length > 0 && (
                <tbody className={styles.missing}>
                  {missingRows.map((row, r) => (
                    <tr key={row.index}>
                      <th scope="row">
                        <button
                          type="button"
                          className={styles.ask}
                          onClick={() => startEditing(row.index)}
                        >
                          {row.name}
                          <span className="sr-only">: quantità mancante, scrivila</span>
                        </button>
                      </th>
                      {row.cells.map((cell, i) => (
                        <td key={i} aria-label="quantità mancante">
                          {cell}
                        </td>
                      ))}
                      {r === missingRows.length - 1 && (
                        <td className={styles.annot} aria-hidden="true">
                          <Marker drawing={LOOP} width={3} stretch className={styles.loop} />
                          <Marker drawing={ARROW} width={5} className={styles.arrow} />
                          <Marker drawing={QUANTI} width={6} className={styles.quanti} />
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              )}
            </table>
            {table.rows.some((row) => row.estimated) && (
              <p className={styles.legend}>† stima dell&apos;AI, non detta nel reel</p>
            )}
          </div>

          {missing.length > 0 && (
            <section className={styles.notice} aria-label="Quantità mancanti">
              <p>{notice}</p>
              <div>
                <button type="button" onClick={() => startEditing()} disabled={pending}>
                  li scrivo io
                </button>
                <button type="button" onClick={byEye} disabled={pending}>
                  sì, a occhio
                </button>
              </div>
            </section>
          )}

          {editing && missing.length > 0 && (
            <div className={styles.edit}>
              {missing.map((item) => (
                <form
                  key={item.index}
                  onSubmit={(event) => {
                    event.preventDefault();
                    save(item, event.currentTarget);
                  }}
                >
                  <label htmlFor={`zq-${item.index}`}>{item.name}</label>
                  <input
                    id={`zq-${item.index}`}
                    name="quantity"
                    inputMode="decimal"
                    placeholder="?"
                    required
                    ref={(el) => {
                      if (el) inputs.current.set(item.index, el);
                      else inputs.current.delete(item.index);
                    }}
                  />
                  <input name="unit" list="zine-units" placeholder="g" aria-label={`Unità per ${item.name}`} />
                  <button type="submit" disabled={pending}>
                    salva
                  </button>
                </form>
              ))}
              <datalist id="zine-units">
                {UNITS.map((u) => (
                  <option key={u} value={u} />
                ))}
              </datalist>
              {servings !== null && <p className={styles.legend}>Per {servings}, come nel reel.</p>}
            </div>
          )}

          {recipe.ingredients.some((item) => item.edited) && (
            <p className={styles.legend}>
              Scritte da te:{" "}
              {recipe.ingredients
                .filter((item) => item.edited)
                .map((item) => (
                  <button key={item.index} type="button" className={styles.undo} onClick={() => undo(item)}>
                    {item.name} (annulla)
                  </button>
                ))}
            </p>
          )}

          {recipe.steps_rewritten && (
            <p className={styles.switch}>
              <button type="button" aria-pressed={!asInReel} onClick={() => setAsInReel(false)}>
                riscritto
              </button>{" "}
              /{" "}
              <button type="button" aria-pressed={asInReel} onClick={() => setAsInReel(true)}>
                come nel reel
              </button>
            </p>
          )}
          {steps.length > 0 ? (
            <ol className={styles.steps}>
              {steps.map((step, i) => (
                <li key={i} data-anchor={`${stepAnchor}-${i}`}>
                  <span>
                    {markTimes(step).map((segment, j) =>
                      segment.mark ? (
                        <span key={j} className={styles.u}>
                          {segment.text}
                          <Marker drawing={SQUIGGLE} width={2.6} stretch className={styles.squiggle} />
                        </span>
                      ) : (
                        segment.text
                      ),
                    )}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className={styles.legend}>Il reel non spiega i passaggi.</p>
          )}

          <div className={styles.cookedRow} data-anchor="cooked">
            <button type="button" className={styles.cooked} onClick={cook} disabled={pending}>
              l&apos;ho cucinata
              <span>
                {cooked.count === 0
                  ? "mai, finora"
                  : `${cooked.count} ${cooked.count === 1 ? "volta" : "volte"}`}
              </span>
            </button>
            {cookedOn && (
              <span className={styles.cookedMark} key={slap}>
                <Marker drawing={BURP} width={4} draw={slap > 0} className={styles.cookedBurp} />
                <Marker drawing={digitsDrawing(cookedOn, DIGITS)} width={3.5} draw={slap > 0} className={styles.cookedDate} />
                <span className="sr-only">Cucinata l&apos;ultima volta il {cookedOn}</span>
              </span>
            )}
          </div>
        </div>
      </div>

      <p className="sr-only" aria-live="polite">
        {status} {drawing.message}
      </p>

      {others.length > 0 && (
        <nav className={styles.issues} aria-label="Altri numeri in libreria" data-anchor="issues">
          <p className={styles.h}>Altri numeri in libreria</p>
          <ol>
            {others.map((item) => (
              <li key={item.id}>
                <Link href={`/ricette/${item.id}`}>
                  <span className={styles.n}>N°{item.id}</span>
                  <span>{item.title.toLowerCase()}</span>
                  <span className={styles.m}>
                    {item.to_clarify === 0 ? "tutto chiaro" : `${item.to_clarify} da chiarire`}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </nav>
      )}

      {(recipe.attributions ?? []).length > 0 && (
        <p className={styles.credits}>
          Immagini:{" "}
          {(recipe.attributions ?? []).map((credit, i) => (
            <span key={i}>
              {i > 0 && " · "}
              <a href={credit.url} target="_blank" rel="noreferrer">
                {credit.text}
              </a>
            </span>
          ))}
        </p>
      )}

      <p className={styles.foot} aria-hidden="true">
        burp!
      </p>

      <DrawingLayer drawing={drawing} sheet={sheet} />
    </article>
  );
}
