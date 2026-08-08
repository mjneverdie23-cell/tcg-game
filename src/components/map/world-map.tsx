"use client";

/**
 * The interactive homepage world map.
 *
 * Renders the Natural Earth political layer from /data/world.geojson with:
 *  - region-tinted country fills (light/dark aware)
 *  - hover highlight, glow, animated dashed outline and a rich tooltip
 *  - flag + name labels placed at each country's pole of inaccessibility,
 *    revealed progressively by zoom level and country size
 *  - ocean labels, smooth zoom/pan, and click-through to /country/[slug]
 *
 * Uses Leaflet directly (no wrapper) so layer lifecycles are explicit.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { OCEANS } from "@/lib/continents";
import { formatArea, formatCompact } from "@/lib/format";
import { baseStyle, hoverStyle, type MapTheme } from "./region-style";

type WorldProps = {
  slug: string | null;
  name: string;
  cca2: string | null;
  cca3: string;
  flag: string;
  region: string | null;
  sovereign: boolean;
  labelLat: number;
  labelLng: number;
  area: number;
};

type IndexEntry = {
  slug: string;
  name: string;
  cca2: string;
  flagEmoji: string;
  region: string;
  capital: string[];
  population: number;
  area: number;
  latitude: number;
  longitude: number;
};

function areaThreshold(zoom: number): number {
  if (zoom <= 2) return 1_400_000;
  if (zoom === 3) return 500_000;
  if (zoom === 4) return 120_000;
  if (zoom === 5) return 25_000;
  return 0;
}

export type WorldMapHandle = { flyToRegion: (bounds: [[number, number], [number, number]]) => void };

export const WorldMap = React.forwardRef<WorldMapHandle, { className?: string; highlightRegion?: string | null }>(
  function WorldMap({ className, highlightRegion }, ref) {
    const router = useRouter();
    const { resolvedTheme } = useTheme();
    const theme: MapTheme = resolvedTheme === "dark" ? "dark" : "light";

    const containerRef = React.useRef<HTMLDivElement>(null);
    const mapRef = React.useRef<L.Map | null>(null);
    const geoLayerRef = React.useRef<L.GeoJSON | null>(null);
    const labelGroupRef = React.useRef<L.LayerGroup | null>(null);
    const dataRef = React.useRef<{ world: GeoJSON.FeatureCollection | null; index: IndexEntry[] }>({ world: null, index: [] });
    const themeRef = React.useRef(theme);
    themeRef.current = theme;
    const regionRef = React.useRef<string | null | undefined>(highlightRegion);
    regionRef.current = highlightRegion;
    const [ready, setReady] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);

    React.useImperativeHandle(ref, () => ({
      flyToRegion: (bounds) => {
        mapRef.current?.flyToBounds(bounds, { duration: 0.9, maxZoom: 4 });
      },
    }));

    const refreshLabels = React.useCallback(() => {
      const map = mapRef.current;
      const group = labelGroupRef.current;
      if (!map || !group) return;
      group.clearLayers();
      const zoom = map.getZoom();
      const threshold = areaThreshold(zoom);
      const viewBounds = map.getBounds().pad(0.3);

      for (const entry of dataRef.current.index) {
        if (entry.area < threshold) continue;
        const feature = dataRef.current.world?.features.find((f) => (f.properties as WorldProps).slug === entry.slug);
        const props = feature?.properties as WorldProps | undefined;
        const lat = props?.labelLat ?? entry.latitude;
        const lng = props?.labelLng ?? entry.longitude;
        if (!viewBounds.contains([lat, lng])) continue;

        const showName = zoom >= 3 || entry.area >= 2_500_000;
        const icon = L.divIcon({
          className: "country-label",
          html: `<div class="label-chip" role="link" aria-label="Open ${entry.name}">
              <img src="/flags/${entry.cca2.toLowerCase()}.svg" alt="" loading="lazy" width="22" height="15" />
              ${showName ? `<span class="label-name">${entry.name}</span>` : ""}
            </div>`,
          iconSize: [0, 0],
        });
        const marker = L.marker([lat, lng], { icon, keyboard: false, riseOnHover: true });
        marker.on("click", () => router.push(`/country/${entry.slug}`));
        marker.bindTooltip(
          `<div style="display:flex;align-items:center;gap:8px"><strong>${entry.flagEmoji} ${entry.name}</strong></div>
           <div style="font-size:11px;opacity:.8">${entry.capital[0] ?? ""} · ${formatCompact(entry.population)} people</div>`,
          { className: "atlas-tooltip", direction: "top", offset: [0, -12] },
        );
        group.addLayer(marker);
      }
    }, [router]);

    const restyle = React.useCallback(() => {
      const layer = geoLayerRef.current;
      if (!layer) return;
      const active = regionRef.current;
      layer.setStyle((feature) => {
        const p = feature?.properties as WorldProps;
        const style = baseStyle(p.region, p.sovereign, themeRef.current);
        if (active && p.region !== active) return { ...style, fillOpacity: 0.15, opacity: 0.4 };
        return style;
      });
    }, []);

    React.useEffect(() => {
      if (!containerRef.current || mapRef.current) return;

      const map = L.map(containerRef.current, {
        center: [24, 12],
        zoom: 3,
        minZoom: 2,
        maxZoom: 8,
        zoomSnap: 0.5,
        wheelPxPerZoomLevel: 90,
        worldCopyJump: true,
        maxBounds: [[-88, -220], [88, 220]],
        maxBoundsViscosity: 0.7,
        attributionControl: false,
        zoomControl: false,
      });
      L.control.zoom({ position: "bottomright" }).addTo(map);
      L.control.attribution({ position: "bottomleft", prefix: false }).addAttribution('Boundaries © <a href="https://www.naturalearthdata.com/">Natural Earth</a>').addTo(map);
      mapRef.current = map;
      labelGroupRef.current = L.layerGroup().addTo(map);

      for (const ocean of OCEANS) {
        L.marker([ocean.lat, ocean.lng], {
          icon: L.divIcon({ className: "ocean-label", html: `<span>${ocean.name}</span>`, iconSize: [0, 0] }),
          interactive: false,
          keyboard: false,
        }).addTo(map);
      }

      let cancelled = false;
      (async () => {
        try {
          const [worldRes, indexRes] = await Promise.all([fetch("/data/world.geojson"), fetch("/data/countries-index.json")]);
          if (!worldRes.ok || !indexRes.ok) throw new Error("Failed to load map data");
          const world = (await worldRes.json()) as GeoJSON.FeatureCollection;
          const index = (await indexRes.json()) as IndexEntry[];
          if (cancelled) return;
          dataRef.current = { world, index };

          const geoLayer = L.geoJSON(world, {
            style: (feature) => {
              const p = feature?.properties as WorldProps;
              return baseStyle(p.region, p.sovereign, themeRef.current);
            },
            onEachFeature: (feature, layer) => {
              const p = feature.properties as WorldProps;
              if (!p.sovereign || !p.slug) return;
              const path = layer as L.Path;
              path.bindTooltip(
                `<div style="display:flex;align-items:center;gap:8px">
                   <img src="/flags/${(p.cca2 ?? "").toLowerCase()}.svg" alt="" width="28" height="19" style="border-radius:3px;box-shadow:0 1px 3px rgba(0,0,0,.3)" />
                   <div><div style="font-weight:600">${p.name}</div><div style="font-size:11px;opacity:.75">${p.region ?? ""} · ${formatArea(p.area)}</div></div>
                 </div>
                 <div style="font-size:11px;opacity:.6;margin-top:4px">Click to explore →</div>`,
                { className: "atlas-tooltip", sticky: true, direction: "top", offset: [0, -8] },
              );
              path.on("mouseover", () => {
                path.setStyle(hoverStyle(themeRef.current));
                (path as unknown as { _path?: SVGPathElement })._path?.classList.add("country-hovered");
                path.bringToFront();
              });
              path.on("mouseout", () => {
                (path as unknown as { _path?: SVGPathElement })._path?.classList.remove("country-hovered");
                geoLayer.resetStyle(path as unknown as L.Layer);
                restyle();
              });
              path.on("click", () => router.push(`/country/${p.slug}`));
            },
          }).addTo(map);
          geoLayerRef.current = geoLayer;
          labelGroupRef.current?.remove();
          labelGroupRef.current = L.layerGroup().addTo(map);
          restyle();
          refreshLabels();
          setReady(true);
        } catch (err) {
          console.error(err);
          if (!cancelled) setError("The world map could not be loaded. Check your connection and reload.");
        }
      })();

      map.on("zoomend moveend", refreshLabels);

      return () => {
        cancelled = true;
        map.remove();
        mapRef.current = null;
        geoLayerRef.current = null;
        labelGroupRef.current = null;
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    React.useEffect(() => {
      restyle();
    }, [theme, highlightRegion, restyle]);

    return (
      <div className={className}>
        <div ref={containerRef} className="h-full w-full" role="application" aria-label="Interactive world map. Click a country to open its page." />
        {!ready && !error && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <div className="rounded-full bg-card/90 px-4 py-2 text-sm shadow-lg border animate-pulse">Loading world map…</div>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 grid place-items-center">
            <div className="rounded-lg border bg-card px-6 py-4 text-sm shadow-lg">{error}</div>
          </div>
        )}
      </div>
    );
  },
);
