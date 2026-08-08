"use client";

/**
 * Client-side user state: favorites, bookmarks, recently viewed countries and
 * per-country learning progress (which sections were read). Persisted to
 * localStorage so it survives reloads and works offline.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type RecentEntry = { slug: string; name: string; flagEmoji: string; at: number };
export type Bookmark = {
  slug: string;
  sectionKey: string;
  countryName: string;
  sectionTitle: string;
  at: number;
};

type AtlasState = {
  favorites: string[];
  recent: RecentEntry[];
  bookmarks: Bookmark[];
  progress: Record<string, string[]>; // slug → section keys read

  toggleFavorite: (slug: string) => void;
  isFavorite: (slug: string) => boolean;
  addRecent: (entry: Omit<RecentEntry, "at">) => void;
  toggleBookmark: (b: Omit<Bookmark, "at">) => void;
  isBookmarked: (slug: string, sectionKey: string) => boolean;
  markSectionRead: (slug: string, sectionKey: string) => void;
  progressFor: (slug: string, totalSections: number) => number;
};

const MAX_RECENT = 12;

export const useAtlasStore = create<AtlasState>()(
  persist(
    (set, get) => ({
      favorites: [],
      recent: [],
      bookmarks: [],
      progress: {},

      toggleFavorite: (slug) =>
        set((s) => ({
          favorites: s.favorites.includes(slug)
            ? s.favorites.filter((f) => f !== slug)
            : [...s.favorites, slug],
        })),

      isFavorite: (slug) => get().favorites.includes(slug),

      addRecent: (entry) =>
        set((s) => ({
          recent: [
            { ...entry, at: Date.now() },
            ...s.recent.filter((r) => r.slug !== entry.slug),
          ].slice(0, MAX_RECENT),
        })),

      toggleBookmark: (b) =>
        set((s) => {
          const exists = s.bookmarks.some(
            (x) => x.slug === b.slug && x.sectionKey === b.sectionKey,
          );
          return {
            bookmarks: exists
              ? s.bookmarks.filter((x) => !(x.slug === b.slug && x.sectionKey === b.sectionKey))
              : [{ ...b, at: Date.now() }, ...s.bookmarks],
          };
        }),

      isBookmarked: (slug, sectionKey) =>
        get().bookmarks.some((x) => x.slug === slug && x.sectionKey === sectionKey),

      markSectionRead: (slug, sectionKey) =>
        set((s) => {
          const read = s.progress[slug] ?? [];
          if (read.includes(sectionKey)) return s;
          return { progress: { ...s.progress, [slug]: [...read, sectionKey] } };
        }),

      progressFor: (slug, totalSections) => {
        const read = get().progress[slug]?.length ?? 0;
        return totalSections > 0 ? Math.min(100, Math.round((read / totalSections) * 100)) : 0;
      },
    }),
    { name: "world-atlas-user" },
  ),
);
