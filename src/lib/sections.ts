/**
 * Canonical registry of country-page sections.
 *
 * The pipeline generates content for every key listed here; the country page
 * renders tabs in this order. Icons are lucide-react icon names resolved by
 * the tab component.
 */

export type SectionDef = {
  key: string;
  title: string;
  icon: string;
  group: "essentials" | "society" | "economy-science" | "life" | "reference";
};

export const SECTION_DEFS: SectionDef[] = [
  { key: "overview", title: "Overview", icon: "Globe2", group: "essentials" },
  { key: "history", title: "History", icon: "Landmark", group: "essentials" },
  { key: "geography", title: "Geography", icon: "Mountain", group: "essentials" },
  { key: "politics", title: "Politics", icon: "Scale", group: "society" },
  { key: "government", title: "Government", icon: "Building2", group: "society" },
  { key: "economy", title: "Economy", icon: "TrendingUp", group: "economy-science" },
  { key: "culture", title: "Culture", icon: "Palette", group: "life" },
  { key: "religion", title: "Religion", icon: "Church", group: "society" },
  { key: "languages", title: "Languages", icon: "MessageSquare", group: "society" },
  { key: "population", title: "Population", icon: "Users", group: "society" },
  { key: "education", title: "Education", icon: "GraduationCap", group: "society" },
  { key: "military", title: "Military", icon: "Shield", group: "society" },
  { key: "tourism", title: "Tourism", icon: "Plane", group: "life" },
  { key: "cuisine", title: "Cuisine", icon: "UtensilsCrossed", group: "life" },
  { key: "wildlife", title: "Wildlife", icon: "Bird", group: "life" },
  { key: "climate", title: "Climate", icon: "CloudSun", group: "essentials" },
  { key: "infrastructure", title: "Infrastructure", icon: "Route", group: "economy-science" },
  { key: "famous-people", title: "Famous People", icon: "Star", group: "life" },
  { key: "inventions", title: "Inventions", icon: "Lightbulb", group: "economy-science" },
  { key: "science-technology", title: "Science & Technology", icon: "FlaskConical", group: "economy-science" },
  { key: "sports", title: "Sports", icon: "Trophy", group: "life" },
  { key: "national-symbols", title: "National Symbols", icon: "Flag", group: "reference" },
  { key: "holidays", title: "Holidays & Festivals", icon: "CalendarDays", group: "life" },
  { key: "current-situation", title: "Current Situation", icon: "Newspaper", group: "reference" },
  { key: "international-relations", title: "International Relations", icon: "Handshake", group: "society" },
  { key: "timeline", title: "Timeline", icon: "History", group: "reference" },
  { key: "interesting-facts", title: "Interesting Facts", icon: "Sparkles", group: "reference" },
  { key: "photo-gallery", title: "Photo Gallery", icon: "Image", group: "reference" },
  { key: "references", title: "References", icon: "BookOpen", group: "reference" },
];

export const SECTION_ORDER: Record<string, number> = Object.fromEntries(
  SECTION_DEFS.map((s, i) => [s.key, i]),
);

export function sectionDef(key: string): SectionDef | undefined {
  return SECTION_DEFS.find((s) => s.key === key);
}
