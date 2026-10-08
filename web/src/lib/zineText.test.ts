import { describe, expect, it } from "vitest";
import { coursePlural, subtitle } from "./zineText";

describe("subtitle", () => {
  it("agrees the cuisine and the diet with the course", () => {
    expect(subtitle("gommosi e glassati", "antipasto", "giapponese", "vegan")).toBe(
      "gommosi e glassati. Antipasto giapponese, vegano.",
    );
    expect(subtitle("definitivi", "primo", "italiana", "neither")).toBe("definitivi. Primo italiano.");
    expect(subtitle(null, "colazione", "americana", "vegetarian")).toBe(
      "Colazione americana, vegetariana.",
    );
  });

  it("skips what is unknown", () => {
    expect(subtitle(null, null, null, "neither")).toBe("");
    expect(subtitle("croccante", null, "indiana", "vegetarian")).toBe("croccante. Indiano, vegetariano.");
  });
});

describe("coursePlural", () => {
  it.each([
    ["primo", "primi"],
    ["antipasto", "antipasti"],
    ["piatto unico", "piatti unici"],
    ["colazione", "colazioni"],
    ["dolce", "dolci"],
  ])("%s -> %s", (course, plural) => {
    expect(coursePlural(course)).toBe(plural);
  });
});
