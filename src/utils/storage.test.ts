import { describe, expect, it } from 'vitest';
import { deleteValue, getValue, idbStateStorage, setValue } from './storage';

describe('storage', () => {
  it('round-trips structured values', async () => {
    await setValue('test:profile', { coins: 120, decks: ['starter'] });
    expect(await getValue('test:profile')).toEqual({ coins: 120, decks: ['starter'] });
  });

  it('returns undefined for missing keys', async () => {
    expect(await getValue('test:missing')).toBeUndefined();
  });

  it('overwrites existing values', async () => {
    await setValue('test:coins', 10);
    await setValue('test:coins', 25);
    expect(await getValue('test:coins')).toBe(25);
  });

  it('deletes values', async () => {
    await setValue('test:tmp', 'x');
    await deleteValue('test:tmp');
    expect(await getValue('test:tmp')).toBeUndefined();
  });

  describe('zustand adapter', () => {
    it('stores and retrieves strings', async () => {
      await idbStateStorage.setItem('test:state', '{"a":1}');
      expect(await idbStateStorage.getItem('test:state')).toBe('{"a":1}');
    });

    it('returns null (not undefined) for missing keys, as zustand expects', async () => {
      expect(await idbStateStorage.getItem('test:absent')).toBeNull();
    });

    it('removes items', async () => {
      await idbStateStorage.setItem('test:gone', 'v');
      await idbStateStorage.removeItem('test:gone');
      expect(await idbStateStorage.getItem('test:gone')).toBeNull();
    });
  });
});
