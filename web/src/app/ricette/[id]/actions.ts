"use server";

import { refresh } from "next/cache";
import { ApiError, api } from "@/lib/api/server";

// Local-only for now (see burp/api.py): when the app goes online, every action must check
// who is calling before touching the library.

export type ActionResult = { ok: true } | { ok: false; error: string };

async function run(change: () => Promise<unknown>): Promise<ActionResult> {
  try {
    await change();
  } catch (error) {
    return { ok: false, error: error instanceof ApiError ? error.message : "Errore imprevisto." };
  }
  refresh();
  return { ok: true };
}

/** "Li scrivo io": save a quantity the post did not give. */
export async function writeQuantity(
  recipeId: number,
  index: number,
  quantity: number,
  unit: string | null,
): Promise<ActionResult> {
  if (!Number.isFinite(quantity) || quantity <= 0) {
    return { ok: false, error: "Scrivi un numero maggiore di zero." };
  }
  return run(() => api.setQuantity(recipeId, index, quantity, unit?.trim() || null));
}

/** Undo a quantity written by hand. */
export async function clearQuantity(recipeId: number, index: number): Promise<ActionResult> {
  return run(() => api.clearEdit(recipeId, index));
}

/** "Sì, a occhio": these quantities stay unknown, and that is fine. */
export async function acceptByEye(recipeId: number, indices: number[]): Promise<ActionResult> {
  return run(() => api.markByEye(recipeId, indices));
}
