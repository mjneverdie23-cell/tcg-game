/**
 * Convert Prisma rows (with JSON-string columns) into typed DTOs used by the
 * UI and API routes. All JSON parsing is centralized here with safe fallbacks
 * so a malformed row degrades gracefully instead of crashing a page.
 */

import type { Country, City, Section } from "@prisma/client";
import type { CountrySummary, CountryDetail, SectionDto, CityDto, ContentBlock } from "./types";

function parseJson<T>(raw: string | null | undefined, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function toSummary(c: Country): CountrySummary {
  return {
    slug: c.slug,
    cca2: c.cca2,
    cca3: c.cca3,
    name: c.name,
    officialName: c.officialName,
    flagEmoji: c.flagEmoji,
    region: c.region,
    subregion: c.subregion,
    capital: parseJson<string[]>(c.capital, []),
    population: c.population,
    area: c.area,
    latitude: c.latitude,
    longitude: c.longitude,
    labelLat: c.labelLat,
    labelLng: c.labelLng,
    unMember: c.unMember,
  };
}

export function toCityDto(c: City): CityDto {
  return {
    name: c.name,
    lat: c.lat,
    lng: c.lng,
    population: c.population,
    isCapital: c.isCapital,
    rank: c.rank,
  };
}

export function toSectionDto(s: Section): SectionDto {
  return {
    key: s.key,
    title: s.title,
    order: s.order,
    blocks: parseJson<ContentBlock[]>(s.blocks, []),
  };
}

export function toDetail(
  c: Country & { cities: City[]; sections: Section[] },
  neighbors: Country[],
): CountryDetail {
  return {
    ...toSummary(c),
    ccn3: c.ccn3,
    nativeNames: parseJson(c.nativeNames, {}),
    altSpellings: parseJson<string[]>(c.altSpellings, []),
    capitalLat: c.capitalLat,
    capitalLng: c.capitalLng,
    continents: parseJson<string[]>(c.continents, []),
    populationDensity: c.populationDensity,
    bbox: parseJson<[number, number, number, number] | null>(c.bbox, null),
    landlocked: c.landlocked,
    borders: parseJson<string[]>(c.borders, []),
    languages: parseJson(c.languages, {}),
    currencies: parseJson(c.currencies, {}),
    timezones: parseJson<string[]>(c.timezones, []),
    tld: parseJson<string[]>(c.tld, []),
    callingCodes: parseJson<string[]>(c.callingCodes, []),
    demonyms: parseJson(c.demonyms, null),
    coatOfArmsUrl: c.coatOfArmsUrl,
    independent: c.independent,
    status: c.status,
    gini: parseJson(c.gini, null),
    carSide: c.carSide,
    startOfWeek: c.startOfWeek,
    fifa: c.fifa,
    maps: parseJson(c.maps, null),
    governmentType: c.governmentType,
    religion: c.religion,
    nationalDish: c.nationalDish,
    nationalSymbol: c.nationalSymbol,
    independenceDate: c.independenceDate,
    lifeExpectancy: c.lifeExpectancy,
    avgTemperature: c.avgTemperature,
    elevation: c.elevation,
    heroImage: c.heroImage,
    cities: c.cities
      .slice()
      .sort((a, b) => (b.isCapital ? 1 : 0) - (a.isCapital ? 1 : 0) || a.rank - b.rank)
      .map(toCityDto),
    neighbors: neighbors.map(toSummary),
    sections: c.sections.map(toSectionDto).sort((a, b) => a.order - b.order),
  };
}
