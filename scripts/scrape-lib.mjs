/**
 * Pure parsing/transformation helpers for the creature scraper.
 * No IO here — everything is unit-tested in scrape-lib.test.mjs.
 */

/** The four dinosaur classes of the game (= JW:TG land-park classes). */
const CLASS_ALIASES = new Map([
  ['carnivore', 'carnivore'],
  ['carnivores', 'carnivore'],
  ['herbivore', 'herbivore'],
  ['herbivores', 'herbivore'],
  ['pterosaur', 'pterosaur'],
  ['pterosaurs', 'pterosaur'],
  ['amphibian', 'amphibian'],
  ['amphibians', 'amphibian'],
]);

/** Wiki rarity → game rarity. Special wiki tiers (VIP/Tournament/Boss) become mythic. */
const RARITY_MAP = new Map([
  ['common', 'common'],
  ['rare', 'rare'],
  ['super rare', 'epic'],
  ['super-rare', 'epic'],
  ['legendary', 'legendary'],
  ['tournament', 'mythic'],
  ['tournament legendary', 'mythic'],
  ['vip', 'mythic'],
  ['boss', 'mythic'],
]);

/** Normalize a class-ish string ("Herbivores", "[[Carnivore]]") to a game class, or null. */
export function normalizeClass(raw) {
  if (typeof raw !== 'string') return null;
  const cleaned = stripMarkup(raw).toLowerCase().trim();
  return CLASS_ALIASES.get(cleaned) ?? null;
}

/** Map a wiki rarity string to a game rarity, or null if unrecognized. */
export function mapRarity(raw) {
  if (typeof raw !== 'string') return null;
  const cleaned = stripMarkup(raw).toLowerCase().trim();
  return RARITY_MAP.get(cleaned) ?? null;
}

/** "Tyrannosaurus rex" → "tyrannosaurus-rex" (stable creature/card id). */
export function slugify(name) {
  return name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** Remove common wiki markup from a field value: links, templates, refs, bold/italics. */
export function stripMarkup(value) {
  return value
    .replace(/\{\{[^{}]*\}\}/g, '') // templates (innermost; run twice for one nesting level)
    .replace(/\{\{[^{}]*\}\}/g, '')
    .replace(/\[\[(?:[^[\]|]*\|)?([^[\]]*)\]\]/g, '$1') // [[a|b]] → b, [[a]] → a
    .replace(/<ref[^>]*\/>/gi, '')
    .replace(/<ref[^>]*>[\s\S]*?<\/ref>/gi, '')
    .replace(/<[^>]+>/g, '')
    .replace(/'{2,}/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Parse the first infobox-like template of a wikitext page into a
 * lowercase-keyed map of stripped string values. Tolerant of nested
 * templates/links inside values and of unknown template names.
 */
export function parseInfobox(wikitext) {
  const start = wikitext.indexOf('{{');
  if (start === -1) return new Map();

  // Find the matching closing braces of the first template.
  let depth = 0;
  let end = -1;
  for (let i = start; i < wikitext.length - 1; i++) {
    const pair = wikitext.slice(i, i + 2);
    if (pair === '{{') {
      depth += 1;
      i += 1;
    } else if (pair === '}}') {
      depth -= 1;
      i += 1;
      if (depth === 0) {
        end = i + 1;
        break;
      }
    }
  }
  if (end === -1) return new Map();

  const body = wikitext.slice(start + 2, end - 2);

  // Split on top-level pipes only (ignore pipes inside [[...]] and {{...}}).
  const parts = [];
  let braces = 0;
  let brackets = 0;
  let current = '';
  for (let i = 0; i < body.length; i++) {
    const pair = body.slice(i, i + 2);
    if (pair === '{{') {
      braces += 1;
      current += pair;
      i += 1;
    } else if (pair === '}}') {
      braces -= 1;
      current += pair;
      i += 1;
    } else if (pair === '[[') {
      brackets += 1;
      current += pair;
      i += 1;
    } else if (pair === ']]') {
      brackets -= 1;
      current += pair;
      i += 1;
    } else if (body[i] === '|' && braces === 0 && brackets === 0) {
      parts.push(current);
      current = '';
    } else {
      current += body[i];
    }
  }
  parts.push(current);

  const fields = new Map();
  for (const part of parts.slice(1)) {
    // skip template name
    const eq = part.indexOf('=');
    if (eq === -1) continue;
    const key = part.slice(0, eq).trim().toLowerCase();
    const value = stripMarkup(part.slice(eq + 1));
    if (key !== '' && value !== '') fields.set(key, value);
  }
  return fields;
}

/** First value among `keys` present in an infobox field map, or null. */
export function pickField(fields, keys) {
  for (const key of keys) {
    const value = fields.get(key);
    if (value !== undefined && value !== '') return value;
  }
  return null;
}

/**
 * Extract page links grouped by their section heading from wikitext.
 * Returns [{ section, title }] in document order, excluding File:/Category:/
 * Template: links and self-anchors. Used on the List_of_All_Creatures page.
 */
export function extractSectionLinks(wikitext) {
  const links = [];
  let section = '';
  for (const line of wikitext.split('\n')) {
    const heading = /^=+\s*(.*?)\s*=+\s*$/.exec(line);
    if (heading !== null) {
      section = stripMarkup(heading[1]);
      continue;
    }
    for (const match of line.matchAll(/\[\[([^[\]|#]+)(?:\|[^[\]]*)?\]\]/g)) {
      const title = match[1].trim();
      if (title === '' || /^(file|image|category|template|user|help):/i.test(title)) continue;
      links.push({ section, title });
    }
  }
  return links;
}

/**
 * Turn section-grouped links into a deduplicated roster. The section heading
 * supplies the creature class when it names one ("Herbivores"); pages under
 * other headings still enter the roster but must resolve their class from
 * their own infobox.
 */
export function buildRoster(sectionLinks) {
  const roster = new Map();
  for (const { section, title } of sectionLinks) {
    if (!roster.has(title)) {
      roster.set(title, { title, sectionClass: normalizeClass(section) });
    }
  }
  return [...roster.values()];
}

/**
 * Best-effort generation number: an explicit infobox field wins, then a
 * "Gen 2"-style suffix in the name, else generation 1.
 */
export function deriveGeneration(fields, name) {
  const explicit = pickField(fields, ['generation', 'gen']);
  if (explicit !== null) {
    const n = Number.parseInt(explicit, 10);
    if (Number.isFinite(n) && n > 0) return n;
  }
  const suffix = /gen(?:eration)?\s*(\d+)/i.exec(name);
  if (suffix !== null) return Number.parseInt(suffix[1], 10);
  return 1;
}

/**
 * Best-effort evolution tier: explicit tier/stage field wins; hybrids
 * (created by fusing two creatures) count as tier 2; everything else tier 1.
 */
export function deriveEvolutionTier(fields) {
  const explicit = pickField(fields, ['tier', 'evolution tier', 'stage']);
  if (explicit !== null) {
    const n = Number.parseInt(explicit, 10);
    if (Number.isFinite(n) && n > 0) return n;
  }
  const hybridHint = pickField(fields, ['hybrid', 'created by', 'fusion', 'dna1', 'ingredients']);
  return hybridHint !== null ? 2 : 1;
}

/** Trim an API plaintext extract to a card-friendly description (~280 chars). */
export function tidyDescription(extract, maxLength = 280) {
  const text = (extract ?? '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  const cut = text.slice(0, maxLength);
  const sentenceEnd = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf('! '), cut.lastIndexOf('? '));
  if (sentenceEnd > maxLength * 0.4) return cut.slice(0, sentenceEnd + 1);
  return `${cut.slice(0, cut.lastIndexOf(' '))}…`;
}
