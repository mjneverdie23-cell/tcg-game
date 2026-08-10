import { describe, expect, it } from 'vitest';
import { createRng, hashString, mulberry32 } from './rng';

describe('hashString', () => {
  it('is stable and distinguishes inputs', () => {
    expect(hashString('tyrannosaurus-rex')).toBe(hashString('tyrannosaurus-rex'));
    expect(hashString('a')).not.toBe(hashString('b'));
  });
});

describe('mulberry32', () => {
  it('yields the same sequence for the same seed', () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it('stays within [0, 1)', () => {
    const next = mulberry32(7);
    for (let i = 0; i < 1000; i++) {
      const value = next();
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThan(1);
    }
  });
});

describe('createRng', () => {
  it('int() covers the inclusive range', () => {
    const rng = createRng('range-test');
    const seen = new Set<number>();
    for (let i = 0; i < 500; i++) seen.add(rng.int(1, 3));
    expect([...seen].sort()).toEqual([1, 2, 3]);
  });

  it('pick() is deterministic per seed and rejects empty arrays', () => {
    expect(createRng('s').pick(['x', 'y', 'z'])).toBe(createRng('s').pick(['x', 'y', 'z']));
    expect(() => createRng('s').pick([])).toThrow();
  });

  it('shuffle() permutes deterministically', () => {
    const a = createRng('shuffle').shuffle([1, 2, 3, 4, 5]);
    const b = createRng('shuffle').shuffle([1, 2, 3, 4, 5]);
    expect(a).toEqual(b);
    expect([...a].sort()).toEqual([1, 2, 3, 4, 5]);
  });
});
