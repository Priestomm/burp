import { describe, expect, it } from "vitest";
import type { IngredientView } from "@/lib/api/server";
import { metric, readable, scale, spoons } from "./dose";

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

const tofu = item({ quantity: 400, unit: "g", base_unit: "g", base_quantity: 400 });
const oil = item({ quantity: 3, unit: "cucchiai", base_unit: "tsp", base_quantity: 9 });
const gochujang = item({ quantity: 0.5, unit: "cucchiaino", base_unit: "tsp", base_quantity: 0.5 });

describe("the cases in the spec", () => {
  it("400 g for 1 out of 3 is 135 g", () => {
    expect(scale(tofu, 1, 3).value).toBe("135 g");
  });

  it("3 cucchiai for 1 out of 3 is 1 cucchiaio", () => {
    expect(scale(oil, 1, 3).value).toBe("1 cucchiaio");
  });

  it("½ cucchiaino for 1 out of 3 is un pizzico", () => {
    expect(scale(gochujang, 1, 3).value).toBe("un pizzico");
  });
});

describe("grams and millilitres", () => {
  it("round to 5 above 100 and to the unit below", () => {
    expect(metric(133.3)).toBe(135);
    expect(metric(101)).toBe(100);
    expect(metric(66.7)).toBe(67);
    expect(metric(0.2)).toBe(1);
  });

  it("say where the number comes from when scaled", () => {
    expect(scale(tofu, 1, 3).note).toBe("nel reel: 400 g");
    expect(scale(tofu, 3, 3)).toMatchObject({ value: "400 g", note: null });
  });

  it("translate small liquids into spoons too", () => {
    const soy = item({ quantity: 50, unit: "ml", base_unit: "ml", base_quantity: 50 });
    expect(scale(soy, 1, 3)).toMatchObject({
      value: "17 ml",
      note: "circa 1 cucchiaio · nel reel: 50 ml",
    });
    expect(scale(soy, 3, 3).note).toBeNull(); // 50 ml is not small
  });
});

describe("spoons", () => {
  it("shows cucchiai only for multiples of 3 teaspoons", () => {
    expect(spoons(3)).toBe("1 cucchiaio");
    expect(spoons(6)).toBe("2 cucchiai");
    expect(spoons(4.5)).toBe("4 ½ cucchiaini");
    expect(spoons(13.5)).toBe("4 ½ cucchiai"); // from two spoons up, halves too
    expect(spoons(7.5)).toBe("2 ½ cucchiai");
    expect(spoons(5)).toBe("5 cucchiaini"); // not a half spoon: stays in teaspoons
    expect(spoons(1)).toBe("1 cucchiaino");
    expect(spoons(2)).toBe("2 cucchiaini");
  });

  it("uses readable fractions under one teaspoon", () => {
    expect(spoons(0.5)).toBe("½ cucchiaino");
    expect(spoons(1 / 3)).toBe("⅓ di cucchiaino");
    expect(spoons(2 / 3)).toBe("⅔ di cucchiaino");
    expect(spoons(0.19)).toBe("un pizzico");
  });

  it("writes the unit from the post in agreement with its number", () => {
    const written = item({ quantity: 3, unit: "cucchiaio", base_unit: "tsp", base_quantity: 9 });
    expect(scale(written, 1, 3).note).toBe("nel reel: 3 cucchiai");
  });

  it("scales up as well as down", () => {
    expect(scale(oil, 4, 3).value).toBe("4 cucchiai");
  });
});

describe("other kinds of quantity", () => {
  it("keeps q.b. as it is", () => {
    expect(scale(item({ status: "to_taste", unit: "q.b." }), 1, 3).value).toBe("q.b.");
  });

  it("keeps unknown quantities unknown until filled in", () => {
    expect(scale(item({ status: "missing" }), 1, 3).value).toBeNull();
    expect(scale(item({ status: "by_eye" }), 1, 3).value).toBe("a occhio");
  });

  it("counts pieces in halves", () => {
    const onion = item({ quantity: 1, base_unit: "piece", base_quantity: 1 });
    expect(scale(onion, 1, 4).value).toBe("½");
    const garlic = item({ quantity: 5, unit: "spicchio", base_unit: "piece", base_quantity: 5 });
    expect(scale(garlic, 2, 4).value).toBe("2 ½ spicchi");
  });

  it("scales the count of units that are not measures", () => {
    const cans = item({ quantity: 2, unit: "lattina da 15 oz" });
    expect(scale(cans, 1, 4).value).toBe("½ lattina da 15 oz");
    expect(scale(cans, 4, 4).value).toBe("2 lattine da 15 oz");
  });

  it("does not scale when the post does not say for how many", () => {
    expect(scale(tofu, 1, null)).toMatchObject({ value: "400 g", note: null });
  });

  it("scales estimates and says they are estimates", () => {
    const spring = item({
      status: "estimated",
      quantity: 1,
      base_unit: "piece",
      base_quantity: 1,
      estimate_reason: "guarnizione per 3",
    });
    expect(scale(spring, 3, 3)).toMatchObject({ value: "1", note: "stima: guarnizione per 3" });
    expect(scale(spring, 6, 3).value).toBe("2");
  });

  it("marks quantities the user wrote", () => {
    const written = item({ ...tofu, edited: true });
    expect(scale(written, 3, 3).note).toBe("scritto da te");
  });
});

describe("readable", () => {
  it("rounds to the nearest of whole, ⅓, ½, ⅔", () => {
    expect(readable(0.5)).toBe("½");
    expect(readable(1.3)).toBe("1 ⅓");
    expect(readable(1.95)).toBe("2");
    expect(readable(2)).toBe("2");
  });
});
