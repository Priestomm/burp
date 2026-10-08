"use client";

import { useId } from "react";
import { Mascot } from "@/components/stickers/Mascot";
import { BurpStamp, CookedFace, DietStar, ServingsBadge } from "@/components/stickers/named";
import type { RecipeDetail } from "@/lib/api/server";
import { scale } from "@/lib/dose";
import styles from "./recipe.module.css";
import { modelName, useRecipe } from "./useRecipe";

const PEOPLE = [1, 2, 3, 4];
const DIET = { vegan: "VEGANA", vegetarian: "VEGETARIANA", neither: null } as const;
const UNITS = ["g", "ml", "cucchiaio", "cucchiaino", "pezzo", "spicchio", "pizzico"];

// Fixed zone: the page is rendered on the server and in the browser, and both must agree.
const DAY = new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long", timeZone: "Europe/Rome" });

/** Size step for the second title line, so long names still fit in the notch. */
function notchSize(text: string): "l" | "m" | "s" | "xs" {
  if (text.length <= 10) return "l";
  if (text.length <= 18) return "m";
  if (text.length <= 30) return "s";
  return "xs";
}

export function AdesiviRecipe({ recipe }: { recipe: RecipeDetail }) {
  const {
    people,
    setPeople,
    editing,
    startEditing,
    status,
    pending,
    inputs,
    slap,
    filling,
    asInReel,
    setAsInReel,
    cooked,
    missing,
    notice,
    servings,
    forWhom,
    steps,
    byEye,
    fill,
    unfill,
    cook,
    save,
    undo,
  } = useRecipe(recipe);
  const labelId = useId();
  const diet = DIET[recipe.tags.diet];
  const starLines = [diet ? recipe.tags.course : null, recipe.tags.cuisine].filter(
    (line): line is string => Boolean(line),
  );

  return (
    <article className={styles.page} aria-busy={pending}>
      <h1 className="sr-only">{recipe.title}</h1>

      <div className={styles.aibar}>
        {recipe.filled_by ? (
          <>
            <span className={styles.aiNote}>
              Stime e passaggi riscritti da {modelName(recipe.filled_by)}
            </span>
            <button type="button" className={`${styles.aiOff} cond`} onClick={unfill} disabled={pending}>
              Togli le stime
            </button>
            <button
              type="button"
              className={styles.regen}
              onClick={() => fill(true)}
              disabled={pending}
              title="Chiede una stima nuova al modello (costa una chiamata)"
            >
              {filling ? "rigenero…" : "rigenera"}
            </button>
          </>
        ) : (
          <button type="button" className={`${styles.ai} cond`} onClick={() => fill()} disabled={pending}>
            {filling ? "Sto completando…" : recipe.fill_saved ? "✦ Rimetti le stime" : "✦ Completa con l'AI"}
          </button>
        )}
      </div>

      <div className={styles.hero}>
        <div className={styles.l1} aria-hidden="true">
          <span className={`${styles.giant} cond`}>{recipe.nome_riga_1}</span>
          {recipe.descrittore && (
            <span className={styles.say}>
              <span className="serif">{recipe.descrittore}</span>
              <Mascot className={styles.mascot} />
            </span>
          )}
        </div>

        <div className={styles.shot}>
          <div className={styles.frame}>
          {/* Without a good photo: only paper and stickers, never a generated image. */}
          <div className={styles.photo}>
            {recipe.photo ? (
              // A plain img: the image optimizer would resample and blur the halftone dots.
              // eslint-disable-next-line @next/next/no-img-element
              <img src={recipe.photo.src} alt={recipe.photo.alt} />
            ) : recipe.photo_pending ? (
              <p className={styles.pending} role="status">
                Sto preparando la foto del piatto…
              </p>
            ) : null}
          </div>
          {recipe.nome_riga_2 && (
            <div className={styles.notch} aria-hidden="true">
              <span className={`${styles.giant} cond`} data-size={notchSize(recipe.nome_riga_2)}>
                {recipe.nome_riga_2}
              </span>
            </div>
          )}
          <div className={styles.per}>
            <ServingsBadge n={people} />
          </div>
          {cooked.last && (
            <div key={slap} className={`${styles.stamp} ${slap ? styles.slap : ""}`}>
              <BurpStamp date={DAY.format(new Date(cooked.last))} />
            </div>
          )}
          <div className={styles.burst}>
            <DietStar diet={diet ?? (recipe.tags.course ?? "ricetta").toUpperCase()} lines={starLines} />
          </div>
          </div>
          {missing.length > 0 && (
            <section className={styles.toast} aria-label="Quantità mancanti">
              <p>{notice}</p>
              <div className={styles.btns}>
                <button type="button" className="cond" onClick={() => startEditing()} disabled={pending}>
                  Li scrivo io
                </button>
                <button type="button" className={`${styles.dark} cond`} onClick={byEye} disabled={pending}>
                  Sì, a occhio
                </button>
                {!recipe.filled_by && (
                  <button type="button" className={`${styles.aiSmall} cond`} onClick={() => fill()} disabled={pending}>
                    {filling ? "Stimo…" : recipe.fill_saved ? "Rimetti le stime" : "Stimale con l'AI"}
                  </button>
                )}
              </div>
            </section>
          )}
        </div>

        {(recipe.author_handle || recipe.source_url) && (
          <p className={styles.credit}>
            {recipe.photo ? "Ricetta e foto" : "Ricetta"}{" "}
            {recipe.source_url ? (
              <a href={recipe.source_url} target="_blank" rel="noreferrer">
                dal reel
              </a>
            ) : (
              "dal reel"
            )}
            {recipe.author_handle && <> di @{recipe.author_handle}</>}
          </p>
        )}
      </div>

      <div className={styles.ctrl}>
        <div className={`${styles.portions} cond`}>
          <span id={labelId}>Per quante persone?</span>
          <div className={styles.seg} role="group" aria-labelledby={labelId}>
            {PEOPLE.map((n) => (
              <button
                key={n}
                type="button"
                className="cond"
                aria-pressed={people === n}
                onClick={() => setPeople(n)}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
        <button
          type="button"
          className={styles.cooked}
          onClick={cook}
          disabled={pending}
          aria-label={`L'ho cucinata. ${cooked.count === 0 ? "Mai cucinata finora" : `Cucinata ${cooked.count === 1 ? "1 volta" : `${cooked.count} volte`}`}`}
        >
          <CookedFace count={cooked.count} />
        </button>
      </div>

      <p className="sr-only" aria-live="polite">
        {status}
      </p>

      <section className={styles.menu} aria-labelledby="ingredienti">
        <h2 className="cond" id="ingredienti">
          Ingredienti <small className="serif">{forWhom}</small>
        </h2>
        <ul>
          {recipe.ingredients.map((item) => {
            const line = scale(item, people, servings);
            const askHere = item.status === "missing";
            return (
              <li key={item.index}>
                <span className={`${styles.name} cond`}>{item.name}</span>
                {askHere && editing ? (
                  <form
                    className={styles.edit}
                    onSubmit={(event) => {
                      event.preventDefault();
                      save(item, event.currentTarget);
                    }}
                  >
                    <label className="sr-only" htmlFor={`q-${item.index}`}>
                      Quantità di {item.name} per {servings ?? "le persone del reel"}
                    </label>
                    <input
                      id={`q-${item.index}`}
                      name="quantity"
                      inputMode="decimal"
                      placeholder="?"
                      required
                      ref={(el) => {
                        if (el) inputs.current.set(item.index, el);
                        else inputs.current.delete(item.index);
                      }}
                    />
                    <label className="sr-only" htmlFor={`u-${item.index}`}>
                      Unità
                    </label>
                    <input id={`u-${item.index}`} name="unit" list="burp-units" placeholder="g" />
                    <button type="submit" className="cond" disabled={pending}>
                      Salva
                    </button>
                  </form>
                ) : askHere ? (
                  <button type="button" className={`${styles.ask} cond`} onClick={() => startEditing(item.index)}>
                    Quanto?
                  </button>
                ) : (
                  <span className={`${styles.q} serif`}>
                    {item.status === "estimated" && <span className={`${styles.estTag} cond`}>stima</span>}
                    {line.value}
                    {line.note && <small>{line.note}</small>}
                    {item.edited && (
                      <button type="button" className={styles.undo} onClick={() => undo(item)} disabled={pending}>
                        annulla
                      </button>
                    )}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        <datalist id="burp-units">
          {UNITS.map((u) => (
            <option key={u} value={u} />
          ))}
        </datalist>
        {editing && servings !== null && (
          <p className={styles.hint}>Scrivi le quantità per {servings}, come nel reel: le ricalcolo io.</p>
        )}
      </section>

      <section className={styles.method} aria-labelledby="procedimento">
        <h2 className="cond" id="procedimento">
          Procedimento{" "}
          {recipe.time_minutes && (
            <small className="serif">
              {recipe.time_minutes} minuti{recipe.time_estimated ? ", stima" : ""}
            </small>
          )}
        </h2>
        {recipe.steps_rewritten && (
          <div className={styles.stepsBar}>
            <div className={styles.seg} role="group" aria-label="Versione del procedimento">
              <button type="button" className="cond" aria-pressed={!asInReel} onClick={() => setAsInReel(false)}>
                Riscritto
              </button>
              <button type="button" className="cond" aria-pressed={asInReel} onClick={() => setAsInReel(true)}>
                Come nel reel
              </button>
            </div>
            {!asInReel && recipe.steps_note && <p className={styles.stepsNote}>Nota dell&apos;AI: {recipe.steps_note}</p>}
          </div>
        )}
        {steps.length > 0 ? (
          <ol className={styles.steps}>
            {steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        ) : (
          <p>Il reel non spiega i passaggi{recipe.filled_by ? "" : ": prova «Completa con l'AI»"}.</p>
        )}
      </section>
    </article>
  );
}
