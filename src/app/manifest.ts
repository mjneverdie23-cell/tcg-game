import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "World Atlas — Interactive Encyclopedia of Every Country",
    short_name: "World Atlas",
    description: "Explore every country on an interactive world map, with rich encyclopedia pages.",
    start_url: "/",
    display: "standalone",
    background_color: "#0d0d0d",
    theme_color: "#2a78d6",
    icons: [{ src: "/icons/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
