import { describe, expect, it } from "vitest";
import type { IngredientView } from "@/lib/api/server";
import { doseTable } from "./doseTable";

function item(over: Partial<IngredientView>): IngredientView {
  return {
    index: 0,
    name: "x",
    original_text: "",
    quantity: null,
    unit: null,
    status: "given",
    base_unit: null,
    base_quantity: null,
    edited: false,
    estimate_reason: null,
    ...over,
  };
}

const ingredients = [
  item({ index: 0, name: "cipollotto", status: "missing" }),
  item({ index: 1, name: "tofu", quantity: 400, unit: "g", base_unit: "g", base_quantity: 400 }),
  item({ index: 2, name: "olio di sesamo", quantity: 3, unit: "cucchiai", base_unit: "tsp", base_quantity: 9 }),
  item({ index: 3, name: "limone", status: "to_taste", unit: "q.b." }),
];

describe("doseTable", () => {
  it("has a column per person, up to the post's servings and at least 3", () => {
    expect(doseTable(ingredients, 3).columns).toEqual([1, 2, 3]);
    expect(doseTable(ingredients, 2).columns).toEqual([1, 2, 3]);
    expect(doseTable(ingredients, null).columns).toEqual([1, 2, 3]);
    expect(doseTable(ingredients, 4).columns).toEqual([1, 2, 3, 4]);
    expect(doseTable(ingredients, 20).columns).toHaveLength(8);
  });

  it("uses the same scaling as the Adesivi page", () => {
    const rows = doseTable(ingredients, 3).rows;
    expect(rows.find((r) => r.name === "tofu")?.cells).toEqual(["135 g", "265 g", "400 g"]);
    expect(rows.find((r) => r.name === "olio di sesamo")?.cells).toEqual([
      "1 cucchiaio",
      "2 cucchiai",
      "3 cucchiai",
    ]);
    expect(rows.find((r) => r.name === "limone")?.cells).toEqual(["q.b.", "q.b.", "q.b."]);
  });

  it("puts unknown quantities together at the bottom, with a question mark", () => {
    const rows = doseTable(ingredients, 3).rows;
    expect(rows.map((r) => r.name)).toEqual(["tofu", "olio di sesamo", "limone", "cipollotto"]);
    expect(rows.at(-1)).toMatchObject({ missing: true, cells: ["?", "?", "?"] });
  });
});
