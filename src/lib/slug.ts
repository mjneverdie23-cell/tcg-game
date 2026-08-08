/**
 * URL slug generation for country pages (/country/[slug]).
 *
 * Slugs are derived from the common English name: lowercase ASCII with
 * hyphens. Diacritics are stripped (São Tomé → sao-tome) and non-alphanumeric
 * runs collapse into a single hyphen so the same input always yields the same
 * stable, readable slug.
 */
export function slugify(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // strip combining diacritics
    .replace(/[ʻ'’ʼ`´]/g, "") // apostrophe-like marks (Côte d'Ivoire)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
