import type { MetadataRoute } from "next";
import { getAllSlugs } from "@/lib/countries";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://world-atlas.example.com";
  const slugs = await getAllSlugs();
  const staticRoutes = ["", "/browse", "/favorites", "/about"].map((r) => ({
    url: `${base}${r}`,
    lastModified: new Date(),
    changeFrequency: "weekly" as const,
    priority: r === "" ? 1 : 0.7,
  }));
  const countryRoutes = slugs.map((slug) => ({
    url: `${base}/country/${slug}`,
    lastModified: new Date(),
    changeFrequency: "monthly" as const,
    priority: 0.8,
  }));
  return [...staticRoutes, ...countryRoutes];
}
