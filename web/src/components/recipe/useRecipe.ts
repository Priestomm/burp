"use client";

import { useRef, useState, useTransition } from "react";
import {
  acceptByEye,
  clearAIFill,
  clearQuantity,
  fillWithAI,
  markCooked,
  writeQuantity,
} from "@/app/ricette/[id]/actions";
import type { IngredientView, RecipeDetail } from "@/lib/api/server";
import { missingNotice } from "@/lib/italian";

/** "claude-haiku-5-5" -> "Haiku 5.5" */
export function modelName(id: string): string {
  const match = /^claude-([a-z]+)-(\d+)(?:-(\d+))?/.exec(id);
  if (!match) return id;
  const [, family, major, minor] = match;
  return `${family[0].toUpperCase()}${family.slice(1)} ${minor ? `${major}.${minor}` : major}`;
}

/**
 * Everything a recipe page does, whatever it looks like: portions, filling in quantities,
 * "a occhio", the AI completion, "l'ho cucinata". Each theme only draws it.
 */
export function useRecipe(recipe: RecipeDetail) {
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

  const missing = recipe.ingredients.filter((i) => i.status === "missing");
  const notice = missingNotice(missing.map((i) => i.name));
  const servings = recipe.servings;

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


  return {
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
  };
}

export type RecipeState = ReturnType<typeof useRecipe>;
