import { describe, expect, it } from "vitest";
import { shorten, stickerLook } from "./named";

describe("stickerLook", () => {
  it("is stable for the same id", () => {
    expect(stickerLook(7)).toEqual(stickerLook(7));
  });

  it("gives five recipes saved in a row five shapes and five colours", () => {
    const looks = [1, 2, 3, 4, 5].map(stickerLook);
    expect(new Set(looks.map((l) => l.shape)).size).toBe(5);
    expect(new Set(looks.map((l) => l.fill)).size).toBe(5);
  });

  it("writes in cream only on ink stickers, where it is readable", () => {
    for (let id = 0; id < 20; id++) {
      const look = stickerLook(id);
      expect(look.ink).toBe(look.fill === "var(--ink)" ? "var(--cream)" : "var(--ink)");
    }
  });
});

describe("shorten", () => {
  it("cuts on a word boundary", () => {
    expect(shorten("di cardoncelli con crema di cannellini", 16)).toBe("di cardoncelli");
  });

  it("never ends on a bare preposition", () => {
    expect(shorten("di cardoncelli con crema di cannellini", 11)).toBe("di cardoncelli");
    expect(shorten("alla mela cotta nel forno", 6)).toBe("alla mela");
  });

  it("leaves short text alone", () => {
    expect(shorten("di tofu", 16)).toBe("di tofu");
  });

  it("cuts inside a word only when the first word is already too long", () => {
    expect(shorten("precipitevolissimevolmente", 10)).toBe("precipite…");
  });
});
