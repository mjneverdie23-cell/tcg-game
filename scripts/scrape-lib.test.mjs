import { describe, expect, it } from 'vitest';
import {
  buildRoster,
  deriveEvolutionTier,
  deriveGeneration,
  extractSectionLinks,
  mapRarity,
  normalizeClass,
  parseInfobox,
  pickField,
  slugify,
  stripMarkup,
  tidyDescription,
} from './scrape-lib.mjs';

describe('normalizeClass', () => {
  it('maps singular, plural and linked forms', () => {
    expect(normalizeClass('Herbivores')).toBe('herbivore');
    expect(normalizeClass('carnivore')).toBe('carnivore');
    expect(normalizeClass('[[Pterosaur]]')).toBe('pterosaur');
    expect(normalizeClass(' Amphibians ')).toBe('amphibian');
  });

  it('rejects everything else', () => {
    expect(normalizeClass('Aquatic')).toBeNull();
    expect(normalizeClass('Hybrids')).toBeNull();
    expect(normalizeClass(undefined)).toBeNull();
  });
});

describe('mapRarity', () => {
  it('maps the wiki rarity ladder onto game rarities', () => {
    expect(mapRarity('Common')).toBe('common');
    expect(mapRarity('Rare')).toBe('rare');
    expect(mapRarity('Super Rare')).toBe('epic');
    expect(mapRarity('Legendary')).toBe('legendary');
    expect(mapRarity('VIP')).toBe('mythic');
    expect(mapRarity('Tournament')).toBe('mythic');
  });

  it('returns null for unknown rarities', () => {
    expect(mapRarity('Ultra Mega')).toBeNull();
  });
});

describe('slugify', () => {
  it('produces stable ids', () => {
    expect(slugify('Tyrannosaurus rex')).toBe('tyrannosaurus-rex');
    expect(slugify('Segnosuchus (Hybrid)')).toBe('segnosuchus-hybrid');
    expect(slugify('Métriorhynchus')).toBe('metriorhynchus');
  });
});

describe('stripMarkup', () => {
  it('unwraps links, removes templates, refs and formatting', () => {
    expect(stripMarkup("[[Legendary|'''Legendary''']] {{icon|leg}}")).toBe('Legendary');
    expect(stripMarkup('Rare<ref name="a">src</ref>')).toBe('Rare');
    expect(stripMarkup('<b>Common</b>')).toBe('Common');
  });
});

describe('parseInfobox', () => {
  const page = `{{Infobox creature
| name = Tyrannosaurus rex
| class = [[Carnivore]]
| rarity = {{RarityIcon|type=sr}} Super Rare
| generation = 1
| cost = {{Coins|4500}}
}}
'''Tyrannosaurus rex''' is a carnivore in the game.`;

  it('extracts stripped key/value pairs from the first template', () => {
    const fields = parseInfobox(page);
    expect(fields.get('name')).toBe('Tyrannosaurus rex');
    expect(fields.get('class')).toBe('Carnivore');
    expect(fields.get('rarity')).toBe('Super Rare');
    expect(fields.get('generation')).toBe('1');
  });

  it('does not split on pipes inside links or nested templates', () => {
    const fields = parseInfobox('{{Box|rarity=[[Rare|rare creature]]|class={{a|b}}carnivore}}');
    expect(fields.get('rarity')).toBe('rare creature');
    expect(fields.get('class')).toBe('carnivore');
  });

  it('returns an empty map when there is no template', () => {
    expect(parseInfobox('Just text').size).toBe(0);
    expect(parseInfobox('{{Unclosed').size).toBe(0);
  });
});

describe('pickField', () => {
  it('returns the first present key', () => {
    const fields = new Map([['type', 'Herbivore']]);
    expect(pickField(fields, ['class', 'type'])).toBe('Herbivore');
    expect(pickField(fields, ['rarity'])).toBeNull();
  });
});

describe('extractSectionLinks + buildRoster', () => {
  const listPage = `Intro with a [[Jurassic World]] link.
== Herbivores ==
{| class="wikitable"
| [[Triceratops]] || [[File:Tric.png|thumb]] || Common
| [[Stegosaurus|Stego]] || Rare
|}
== Carnivores ==
* [[Tyrannosaurus rex]]
* [[Velociraptor]] and again [[Velociraptor]]
== Trivia ==
See [[Category:Creatures]] and [[Template:Nav]].`;

  it('groups links under their section and skips files/categories/templates', () => {
    const links = extractSectionLinks(listPage);
    expect(links).toContainEqual({ section: 'Herbivores', title: 'Triceratops' });
    expect(links).toContainEqual({ section: 'Herbivores', title: 'Stegosaurus' });
    expect(links).toContainEqual({ section: 'Carnivores', title: 'Tyrannosaurus rex' });
    expect(links.some((l) => l.title.startsWith('File:'))).toBe(false);
    expect(links.some((l) => l.title.startsWith('Category:'))).toBe(false);
  });

  it('builds a deduplicated roster with section-derived classes', () => {
    const roster = buildRoster(extractSectionLinks(listPage));
    const byTitle = new Map(roster.map((entry) => [entry.title, entry]));
    expect(byTitle.get('Triceratops')?.sectionClass).toBe('herbivore');
    expect(byTitle.get('Velociraptor')?.sectionClass).toBe('carnivore');
    // "Jurassic World" sits before any heading — roster keeps it, class unknown.
    expect(byTitle.get('Jurassic World')?.sectionClass).toBeNull();
    expect(roster.filter((entry) => entry.title === 'Velociraptor')).toHaveLength(1);
  });
});

describe('deriveGeneration', () => {
  it('prefers the infobox field, then the name suffix, then defaults to 1', () => {
    expect(deriveGeneration(new Map([['generation', '2']]), 'Rex')).toBe(2);
    expect(deriveGeneration(new Map(), 'Velociraptor Gen 2')).toBe(2);
    expect(deriveGeneration(new Map(), 'Velociraptor')).toBe(1);
  });
});

describe('deriveEvolutionTier', () => {
  it('uses explicit tier, marks hybrids as tier 2, defaults to 1', () => {
    expect(deriveEvolutionTier(new Map([['tier', '3']]))).toBe(3);
    expect(deriveEvolutionTier(new Map([['created by', 'Rex + Raptor']]))).toBe(2);
    expect(deriveEvolutionTier(new Map())).toBe(1);
  });
});

describe('tidyDescription', () => {
  it('collapses whitespace and keeps short text as-is', () => {
    expect(tidyDescription('  A  mighty\n  hunter. ')).toBe('A mighty hunter.');
  });

  it('cuts long text at a sentence boundary', () => {
    const long = `${'The apex predator ruled the land. '.repeat(20)}`;
    const tidied = tidyDescription(long);
    expect(tidied.length).toBeLessThanOrEqual(280);
    expect(tidied.endsWith('.')).toBe(true);
  });

  it('falls back to a word boundary with ellipsis', () => {
    const oneSentence = `A ${'very '.repeat(80)}long unbroken description`;
    const tidied = tidyDescription(oneSentence);
    expect(tidied.length).toBeLessThanOrEqual(280);
    expect(tidied.endsWith('…')).toBe(true);
  });
});
