import { describe, expect, it } from "vitest";
import { howMuch, list, missingNotice } from "./italian";

describe("howMuch", () => {
  it.each([
    ["cipollotto", "quanto cipollotto"],
    ["semi di sesamo", "quanti semi di sesamo"],
    ["farina", "quanta farina"],
    ["erbe aromatiche", "quante erbe aromatiche"],
    ["noce moscata", "quanta noce moscata"],
    ["tuorlo", "quanti tuorli"],
    ["uovo", "quante uova"],
    ["burro", "quanto burro"],
    ["sale", "quanto sale"],
    ["mela", "quante mele"],
  ])("%s -> %s", (name, expected) => {
    expect(howMuch(name)).toBe(expected);
  });
});

describe("missingNotice", () => {
  it("names up to three ingredients", () => {
    expect(missingNotice(["cipollotto", "semi di sesamo"])).toBe(
      "Nel reel non dicono quanto cipollotto e quanti semi di sesamo. Va bene a occhio?",
    );
  });

  it("counts them when there are more", () => {
    expect(missingNotice(["a", "b", "c", "d"])).toBe(
      "Nel reel non dicono le quantità di 4 ingredienti. Va bene a occhio?",
    );
  });

  it("is empty when nothing is missing", () => {
    expect(missingNotice([])).toBe("");
    expect(list(["a", "b", "c"])).toBe("a, b e c");
  });
});
