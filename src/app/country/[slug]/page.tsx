import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CountryView } from "@/components/country/country-view";
import { getAllSlugs, getCountryDetail } from "@/lib/countries";
import { formatArea, formatCompact } from "@/lib/format";

export const revalidate = 3600;
export const dynamicParams = true;

/** Pre-render every country page at build time (SSG). */
export async function generateStaticParams() {
  const slugs = await getAllSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const country = await getCountryDetail(slug);
  if (!country) return { title: "Country not found" };
  const desc = `${country.name} (${country.officialName}): capital ${country.capital[0] ?? "—"}, ${formatCompact(country.population)} people, ${formatArea(country.area)}. Explore history, geography, culture, famous destinations, cuisine and more.`;
  return {
    title: country.name,
    description: desc,
    openGraph: {
      title: `${country.name} — World Atlas`,
      description: desc,
      images: country.heroImage ? [{ url: country.heroImage }] : undefined,
    },
    alternates: { canonical: `/country/${slug}` },
  };
}

export default async function CountryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const country = await getCountryDetail(slug);
  if (!country) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Country",
    name: country.name,
    alternateName: country.officialName,
    description: `${country.name}, a country in ${country.subregion ?? country.region}.`,
    ...(country.capital.length ? { containsPlace: country.capital.map((c) => ({ "@type": "City", name: c })) } : {}),
    additionalProperty: [
      { "@type": "PropertyValue", name: "Population", value: country.population },
      { "@type": "PropertyValue", name: "Area (km²)", value: country.area },
      { "@type": "PropertyValue", name: "ISO 3166-1 alpha-3", value: country.cca3 },
    ],
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <CountryView country={country} />
    </>
  );
}
