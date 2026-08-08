import { describe, it, expect } from "vitest";
import { scoreCountry, rankCountries, type Searchable } from "./search";

const FR: Searchable = { slug: "france", name: "France", officialName: "French Republic", cca2: "FR", cca3: "FRA", capital: ["Paris"], altSpellings: ["FR", "République française"] };
const DE: Searchable = { slug: "germany", name: "Germany", officialName: "Federal Republic of Germany", cca2: "DE", cca3: "DEU", capital: ["Berlin"] };
const list = [FR, DE];

describe("scoreCountry", () => {
  it("ranks exact name highest", () => {
    expect(scoreCountry("France", FR)).toBe(100);
  });
  it("scores name prefix above substring", () => {
    expect(scoreCountry("Fra", FR)).toBeGreaterThan(scoreCountry("ance", FR));
  });
  it("matches ISO codes", () => {
    expect(scoreCountry("FRA", FR)).toBeGreaterThan(0);
    expect(scoreCountry("DE", DE)).toBeGreaterThan(0);
  });
  it("matches capitals", () => {
    expect(scoreCountry("Paris", FR)).toBeGreaterThan(0);
  });
  it("returns 0 for no match and empty query", () => {
    expect(scoreCountry("xyz", FR)).toBe(0);
    expect(scoreCountry("", FR)).toBe(0);
  });
});

describe("rankCountries", () => {
  it("orders by score then alphabetically", () => {
    const res = rankCountries("ge", list, 10);
    expect(res[0].slug).toBe("germany");
  });
  it("respects the limit", () => {
    expect(rankCountries("a", list, 1).length).toBeLessThanOrEqual(1);
  });
  it("filters out non-matches", () => {
    expect(rankCountries("zzzz", list)).toHaveLength(0);
  });
});
