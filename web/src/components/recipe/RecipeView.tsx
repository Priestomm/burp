"use client";

import { useId, useRef, useState, useTransition } from "react";
import {
  acceptByEye,
  clearAIFill,
  clearQuantity,
  fillWithAI,
  markCooked,
  writeQuantity,
} from "@/app/ricette/[id]/actions";
import { Mascot } from "@/components/stickers/Mascot";
import { BurpStamp, CookedFace, DietStar, ServingsBadge } from "@/components/stickers/named";
import type { IngredientView, RecipeDetail } from "@/lib/api/server";
import { scale } from "@/lib/dose";
import { missingNotice } from "@/lib/italian";
import styles from "./recipe.module.css";

const PEOPLE = [1, 2, 3, 4];
const DIET = { vegan: "VEGANA", vegetarian: "VEGETARIANA", neither: null } as const;
const UNITS = ["g", "ml", "cucchiaio", "cucchiaino", "pezzo", "spicchio", "pizzico"];

// Fixed zone: the page is rendered on the server and in the browser, and both must agree.
const DAY = new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long", timeZone: "Europe/Rome" });

/** "claude-haiku-4-5" -> "Haiku 4.5" */
function modelName(id: string): string {
  const match = /^claude-([a-z]+)-(\d+)(?:-(\d+))?/.exec(id);
  if (!match) return id;
  const [, family, major, minor] = match;
  return `${family[0].toUpperCase()}${family.slice(1)} ${minor ? `${major}.${minor}` : major}`;
}

/** Size step for the second title line, so long names still fit in the notch. */
function notchSize(text: string): "l" | "m" | "s" | "xs" {
  if (text.length <= 10) return "l";
  if (text.length <= 18) return "m";
  if (text.length <= 30) return "s";
  return "xs";
}

export function RecipeView({ recipe }: { recipe: RecipeDetail }) {
  // Built for people who live alone: one portion first.
  const [people, setPeople] = useState(1);
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState("");
  const [pending, startTransition] = useTransition();
  const inputs = useRef(new Map<number, HTMLInputElement>());
  // Bumped on every "L'ho cucinata" so the stamp's slap animation plays again.
  const [slap, setSlap] = useState(0);
  const [filling, setFilling] = useState(false);
  const [asInReel, setAsInReel] = useState(false);
  const cooked = recipe.cooked;
  const labelId = useId();

  const missing = recipe.ingredients.filter((i) => i.status === "missing");
  const notice = missingNotice(missing.map((i) => i.name));
  const servings = recipe.servings;
  const diet = DIET[recipe.tags.diet];
  const starLines = [diet ? recipe.tags.course : null, recipe.tags.cuisine].filter(
    (line): line is string => Boolean(line),
  );

  function startEditing(index?: number) {
    setEditing(true);
    const target = index ?? missing[0]?.index;
    // Focus after the inputs render.
    requestAnimationFrame(() => {
      if (target !== undefined) inputs.current.get(target)?.focus();
    });
  }

  function byEye() {
    const names = missing.map((i) => i.name);
    startTransition(async () => {
      const result = await acceptByEye(
        recipe.id,
        missing.map((i) => i.index),
      );
      setStatus(result.ok ? `Fatto: ${names.join(" e ")} a occhio.` : result.error);
      if (result.ok) setEditing(false);
    });
  }

  function fill(regenerate = false) {
    // A stored answer comes back instantly; only a new one takes a few seconds.
    setFilling(regenerate || !recipe.fill_saved);
    startTransition(async () => {
      const result = await fillWithAI(recipe.id, regenerate);
      setFilling(false);
      setEditing(false);
      setStatus(result.ok ? "Fatto: stime e passaggi riscritti, segnati come stima." : result.error);
    });
  }

  function unfill() {
    startTransition(async () => {
      const result = await clearAIFill(recipe.id);
      setAsInReel(false);
      setStatus(result.ok ? "Stime tolte: è tornata com'era nel reel." : result.error);
    });
  }

  function cook() {
    startTransition(async () => {
      const result = await markCooked(recipe.id);
      if (!result.ok) {
        setStatus(result.error);
        return;
      }
      setSlap((n) => n + 1);
      const times = result.cooked.count === 1 ? "1 volta" : `${result.cooked.count} volte`;
      setStatus(`Burp! Cucinata ${times}.`);
    });
  }

  function save(item: IngredientView, form: HTMLFormElement) {
    const data = new FormData(form);
    const quantity = Number(String(data.get("quantity")).replace(",", "."));
    const unit = String(data.get("unit") ?? "");
    startTransition(async () => {
      const result = await writeQuantity(recipe.id, item.index, quantity, unit);
      setStatus(result.ok ? `Salvato: ${item.name}.` : result.error);
    });
  }

  function undo(item: IngredientView) {
    startTransition(async () => {
      const result = await clearQuantity(recipe.id, item.index);
      setStatus(result.ok ? `Tolto il valore scritto per ${item.name}.` : result.error);
    });
  }

  const base = recipe.servings_estimated ? "stima" : "reel";
  const forWhom =
    servings === null
      ? "il reel non dice per quante persone"
      : people === servings
        ? `per ${people}, come ${recipe.servings_estimated ? "da stima" : "nel reel"}`
        : `per ${people}, dal${base === "reel" ? " reel" : "la stima"} per ${servings}`;
  const steps = asInReel ? recipe.original_steps : recipe.steps;

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
