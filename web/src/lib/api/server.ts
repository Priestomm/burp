/**
 * The Python API, called from Server Components and Server Actions only: the browser never
 * talks to it directly. Types come from its OpenAPI schema (`pnpm gen:api`).
 */
import type { components } from "./schema";

export type LibraryItem = components["schemas"]["LibraryItem"];
export type RecipeDetail = components["schemas"]["RecipeDetail"];
export type IngredientView = components["schemas"]["IngredientView"];
export type Cooked = components["schemas"]["CookedOut"];
export type Stroke = components["schemas"]["Stroke"];

const BASE = process.env.BURP_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method: init?.method ?? "GET",
      headers: init?.body === undefined ? undefined : { "content-type": "application/json" },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(503, "L'API di burp! non risponde: avviala con `uv run burp serve`.");
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const message = typeof detail?.detail === "string" ? detail.detail : response.statusText;
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRecipes: (q?: string) =>
    call<LibraryItem[]>(`/api/recipes${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getRecipe: (id: number) => call<RecipeDetail>(`/api/recipes/${id}`),
  setQuantity: (id: number, index: number, quantity: number, unit: string | null) =>
    call<RecipeDetail>(`/api/recipes/${id}/ingredients/${index}`, {
      method: "PUT",
      body: { quantity, unit },
    }),
  clearEdit: (id: number, index: number) =>
    call<RecipeDetail>(`/api/recipes/${id}/ingredients/${index}/edit`, { method: "DELETE" }),
  markByEye: (id: number, indices: number[]) =>
    call<RecipeDetail>(`/api/recipes/${id}/by-eye`, { method: "POST", body: { indices } }),
  markCooked: (id: number) => call<Cooked>(`/api/recipes/${id}/cooked`, { method: "POST" }),
  fillRecipe: (id: number, regenerate = false) =>
    call<RecipeDetail>(`/api/recipes/${id}/fill${regenerate ? "?regenerate=true" : ""}`, {
      method: "POST",
    }),
  clearFill: (id: number) => call<RecipeDetail>(`/api/recipes/${id}/fill`, { method: "DELETE" }),
  setDrawing: (id: number, strokes: Stroke[]) =>
    call<{ strokes: Stroke[] }>(`/api/recipes/${id}/drawing`, { method: "PUT", body: { strokes } }),
  clearDrawing: (id: number) =>
    call<{ strokes: Stroke[] }>(`/api/recipes/${id}/drawing`, { method: "DELETE" }),
};
