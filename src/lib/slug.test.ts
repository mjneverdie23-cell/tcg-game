import { describe, it, expect } from "vitest";
import { slugify } from "./slug";

describe("slugify", () => {
  it("lowercases and hyphenates", () => {
    expect(slugify("United States")).toBe("united-states");
  });
  it("strips diacritics", () => {
    expect(slugify("São Tomé and Príncipe")).toBe("sao-tome-and-principe");
    expect(slugify("Åland")).toBe("aland");
  });
  it("removes apostrophe-like marks", () => {
    expect(slugify("Côte d'Ivoire")).toBe("cote-divoire");
  });
  it("collapses non-alphanumeric runs and trims", () => {
    expect(slugify("  Congo (Dem. Rep.)  ")).toBe("congo-dem-rep");
  });
  it("is idempotent", () => {
    const once = slugify("Timor-Leste");
    expect(slugify(once)).toBe(once);
  });
});
