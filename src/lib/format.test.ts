import { describe, it, expect } from "vitest";
import { formatNumber, formatCompact, formatArea, formatDensity, joinNatural, formatCoords } from "./format";

describe("format helpers", () => {
  it("formats numbers with separators", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatNumber(null)).toBe("—");
  });
  it("formats compact", () => {
    expect(formatCompact(1500000)).toBe("1.5M");
    expect(formatCompact(2300)).toBe("2.3K");
  });
  it("formats area with unit", () => {
    expect(formatArea(1000)).toBe("1,000 km²");
  });
  it("formats density with one decimal for small values", () => {
    expect(formatDensity(3.14159)).toBe("3.1 /km²");
    expect(formatDensity(500)).toBe("500 /km²");
  });
  it("joins lists naturally", () => {
    expect(joinNatural(["a"])).toBe("a");
    expect(joinNatural(["a", "b"])).toBe("a and b");
    expect(joinNatural(["a", "b", "c"])).toBe("a, b and c");
  });
  it("formats coordinates with hemispheres", () => {
    expect(formatCoords(48.86, 2.35)).toBe("48.86° N, 2.35° E");
    expect(formatCoords(-33.87, -70.5)).toBe("33.87° S, 70.50° W");
  });
});
