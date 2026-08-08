import { describe, it, expect } from "vitest";
import { bboxOf, labelPoint, neIsoA3, neProp, type Geometry } from "./geo";

const square: Geometry = {
  type: "Polygon",
  coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
};

describe("bboxOf", () => {
  it("computes bounds of a polygon", () => {
    expect(bboxOf(square)).toEqual([0, 0, 10, 10]);
  });
  it("handles multipolygons", () => {
    const mp: Geometry = { type: "MultiPolygon", coordinates: [[[[0, 0], [2, 0], [2, 2], [0, 0]]], [[[5, 5], [8, 5], [8, 8], [5, 5]]]] };
    expect(bboxOf(mp)).toEqual([0, 0, 8, 8]);
  });
});

describe("labelPoint", () => {
  it("returns an interior point of the polygon", () => {
    const p = labelPoint(square);
    expect(p).not.toBeNull();
    expect(p![0]).toBeGreaterThan(0);
    expect(p![0]).toBeLessThan(10);
    expect(p![1]).toBeGreaterThan(0);
    expect(p![1]).toBeLessThan(10);
  });
});

describe("neIsoA3", () => {
  it("prefers ISO_A3 and skips -99 sentinels", () => {
    expect(neIsoA3({ ISO_A3: "FRA" })).toBe("FRA");
    expect(neIsoA3({ ISO_A3: "-99", ISO_A3_EH: "FRA" })).toBe("FRA");
    expect(neIsoA3({ foo: "bar" })).toBeNull();
  });
});

describe("neProp", () => {
  it("reads case-variant keys", () => {
    expect(neProp({ name: "X" }, "NAME")).toBe("X");
    expect(neProp({ POP_MAX: 100 }, "pop_max")).toBe(100);
  });
});
