"use client";

/**
 * Detailed per-country map for /country/[slug].
 *
 * Layers (all lazily fetched, all togglable):
 *  - country shape with coastline styling
 *  - first-level administrative boundaries (Natural Earth 10m, simplified)
 *  - neighboring countries, muted, clickable
 *  - major cities and the capital
 *  - rivers and lakes (Natural Earth physical)
 *  - optional OpenStreetMap streets/roads and OpenTopoMap terrain/relief
 *    raster basemaps (mountains and roads come from these)
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Layers } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { formatCompact } from "@/lib/format";
import { HOVER_COLOR, type MapTheme } from "./region-style";
import type { CityDto, CountrySummary } from "@/lib/types";

type Props = {
  slug: string;
  name: string;
  bbox: [number, number, number, number] | null;
  latitude: number;
  longitude: number;
  cities: CityDto[];
  neighbors: CountrySummary[];
  className?: string;
};

type LayerKey = "admin1" | "cities" | "rivers" | "lakes" | "neighbors" | "streets" | "terrain";

const LAYER_LABELS: Record<LayerKey, string> = {
  admin1: "Administrative divisions",
  cities: "Cities & capital",
  rivers: "Rivers",
  lakes: "Lakes",
  neighbors: "Neighboring countries",
  streets: "Streets & roads (OSM)",
  terrain: "Terrain & mountains (OpenTopoMap)",
};

const DEFAULTS: Record<LayerKey, boolean> = { admin1: true, cities: true, rivers: true, lakes: true, neighbors: true, streets: false, terrain: false };

const COUNTRY_STYLE: Record<MapTheme, L.PathOptions> = {
  light: { color: "#2a5b8f", weight: 2, fillColor: "#e9dfc8", fillOpacity: 0.75 },
  dark: { color: "#6ea8dd", weight: 2, fillColor: "#33415e", fillOpacity: 0.55 },
};
const ADMIN_STYLE: Record<MapTheme, L.PathOptions> = {
  light: { color: "#8a6d3b", weight: 1, dashArray: "4 3", fillOpacity: 0, opacity: 0.8 },
  dark: { color: "#c8a86a", weight: 1, dashArray: "4 3", fillOpacity: 0, opacity: 0.7 },
};
const NEIGHBOR_STYLE: Record<MapTheme, L.PathOptions> = {
  light: { color: "#9aa4ae", weight: 1, fillColor: "#d9dcd3", fillOpacity: 0.5 },
  dark: { color: "#4a5560", weight: 1, fillColor: "#232a30", fillOpacity: 0.5 },
};
const RIVER_STYLE: Record<MapTheme, L.PathOptions> = {
  light: { color: "#3d86c6", weight: 1.2, opacity: 0.8 },
  dark: { color: "#5da2dd", weight: 1.2, opacity: 0.7 },
};
const LAKE_STYLE: Record<MapTheme, L.PathOptions> = {
  light: { color: "#3d86c6", weight: 0.8, fillColor: "#a8cdec", fillOpacity: 0.85 },
  dark: { color: "#5da2dd", weight: 0.8, fillColor: "#1d3a57", fillOpacity: 0.85 },
};

async function fetchGeo(url: string): Promise<GeoJSON.FeatureCollection | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return (await res.json()) as GeoJSON.FeatureCollection;
  } catch {
    return null;
  }
}

export function CountryMap({ slug, name, bbox, latitude, longitude, cities, neighbors, className }: Props) {
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const theme: MapTheme = resolvedTheme === "dark" ? "dark" : "light";
  const themeRef = React.useRef(theme);
  themeRef.current = theme;

  const containerRef = React.useRef<HTMLDivElement>(null);
  const mapRef = React.useRef<L.Map | null>(null);
  const layersRef = React.useRef<Partial<Record<LayerKey, L.Layer>>>({});
  const countryLayerRef = React.useRef<L.GeoJSON | null>(null);
  const [visible, setVisible] = React.useState<Record<LayerKey, boolean>>(DEFAULTS);
  const [panelOpen, setPanelOpen] = React.useState(false);
  const [loadedCount, setLoadedCount] = React.useState(0);

  React.useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const bounds: L.LatLngBoundsExpression = bbox
      ? [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
      : [[latitude - 5, longitude - 5], [latitude + 5, longitude + 5]];

    const map = L.map(containerRef.current, { zoomSnap: 0.25, attributionControl: false, zoomControl: false, worldCopyJump: true });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.control.attribution({ position: "bottomleft", prefix: false }).addAttribution('© <a href="https://www.naturalearthdata.com/">Natural Earth</a>').addTo(map);
    map.fitBounds(bounds, { padding: [24, 24] });
    mapRef.current = map;

    layersRef.current.streets = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });
    layersRef.current.terrain = L.tileLayer("https://tile.opentopomap.org/{z}/{x}/{y}.png", {
      maxZoom: 15,
      attribution: '© OpenStreetMap contributors, SRTM · © <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
    });

    let cancelled = false;

    (async () => {
      const shape = await fetchGeo(`/data/countries/${slug}.json`);
      if (cancelled) return;
      if (shape) {
        const layer = L.geoJSON(shape, { style: COUNTRY_STYLE[themeRef.current] }).addTo(map);
        countryLayerRef.current = layer;
        map.fitBounds(layer.getBounds(), { padding: [24, 24] });
      }
      setLoadedCount((n) => n + 1);

      const admin = await fetchGeo(`/data/countries/${slug}.admin1.json`);
      if (cancelled) return;
      if (admin) {
        layersRef.current.admin1 = L.geoJSON(admin, {
          style: ADMIN_STYLE[themeRef.current],
          onEachFeature: (feature, l) => {
            const p = feature.properties as { name?: string; type_en?: string };
            if (p?.name) (l as L.Path).bindTooltip(`<strong>${p.name}</strong>${p.type_en ? `<div style="font-size:11px;opacity:.7">${p.type_en}</div>` : ""}`, { className: "atlas-tooltip", sticky: true });
          },
        });
      }
      setLoadedCount((n) => n + 1);

      const neighborLayers = await Promise.all(
        neighbors.map(async (n) => {
          const geo = await fetchGeo(`/data/countries/${n.slug}.json`);
          if (!geo) return null;
          return L.geoJSON(geo, {
            style: NEIGHBOR_STYLE[themeRef.current],
            onEachFeature: (_f, l) => {
              (l as L.Path).bindTooltip(`<strong>${n.flagEmoji} ${n.name}</strong><div style="font-size:11px;opacity:.7">Click to open</div>`, { className: "atlas-tooltip", sticky: true });
              l.on("click", () => router.push(`/country/${n.slug}`));
              l.on("mouseover", () => (l as L.Path).setStyle({ fillOpacity: 0.75 }));
              l.on("mouseout", () => (l as L.Path).setStyle(NEIGHBOR_STYLE[themeRef.current]));
            },
          });
        }),
      );
      if (cancelled) return;
      layersRef.current.neighbors = L.layerGroup(neighborLayers.filter((l): l is L.GeoJSON => Boolean(l)));
      setLoadedCount((n) => n + 1);

      const [rivers, lakes] = await Promise.all([fetchGeo("/data/physical/rivers.json"), fetchGeo("/data/physical/lakes.json")]);
      if (cancelled) return;
      if (rivers) {
        layersRef.current.rivers = L.geoJSON(rivers, {
          style: RIVER_STYLE[themeRef.current],
          onEachFeature: (feature, l) => {
            const riverName = (feature.properties as { name?: string })?.name;
            if (riverName) (l as L.Path).bindTooltip(`${riverName} River`, { className: "atlas-tooltip", sticky: true });
          },
        });
      }
      if (lakes) {
        layersRef.current.lakes = L.geoJSON(lakes, {
          style: LAKE_STYLE[themeRef.current],
          onEachFeature: (feature, l) => {
            const lakeName = (feature.properties as { name?: string })?.name;
            if (lakeName) (l as L.Path).bindTooltip(lakeName, { className: "atlas-tooltip", sticky: true });
          },
        });
      }
      setLoadedCount((n) => n + 1);

      const cityGroup = L.layerGroup(
        cities.slice(0, 25).map((city) => {
          if (city.isCapital) {
            const icon = L.divIcon({
              className: "city-marker",
              html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-50%)">
                  <span style="font-size:16px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.5))">★</span>
                  <span style="font-size:11px;font-weight:700;color:hsl(var(--foreground));text-shadow:0 0 4px hsl(var(--background)),0 0 8px hsl(var(--background))">${city.name}</span>
                </div>`,
              iconSize: [0, 0],
            });
            return L.marker([city.lat, city.lng], { icon }).bindTooltip(
              `<strong>★ ${city.name}</strong><div style="font-size:11px;opacity:.7">Capital${city.population ? ` · ${formatCompact(city.population)} people` : ""}</div>`,
              { className: "atlas-tooltip", direction: "top" },
            );
          }
          const radius = city.rank <= 2 ? 6 : city.rank <= 6 ? 5 : 4;
          return L.circleMarker([city.lat, city.lng], {
            radius,
            color: themeRef.current === "dark" ? "#e8eaed" : "#30363d",
            weight: 1.5,
            fillColor: HOVER_COLOR[themeRef.current],
            fillOpacity: 0.9,
          }).bindTooltip(`<strong>${city.name}</strong>${city.population ? `<div style="font-size:11px;opacity:.7">${formatCompact(city.population)} people</div>` : ""}`, { className: "atlas-tooltip", direction: "top" });
        }),
      );
      layersRef.current.cities = cityGroup;
      setLoadedCount((n) => n + 1);
    })();

    return () => {
      cancelled = true;
      map.remove();
      mapRef.current = null;
      layersRef.current = {};
      countryLayerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  React.useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    for (const key of Object.keys(LAYER_LABELS) as LayerKey[]) {
      const layer = layersRef.current[key];
      if (!layer) continue;
      const shouldShow = visible[key];
      const isShown = map.hasLayer(layer);
      if (shouldShow && !isShown) {
        layer.addTo(map);
        if (key === "streets" || key === "terrain") (layer as L.TileLayer).bringToBack();
        countryLayerRef.current?.bringToFront();
      } else if (!shouldShow && isShown) {
        map.removeLayer(layer);
      }
    }
  }, [visible, loadedCount]);

  React.useEffect(() => {
    countryLayerRef.current?.setStyle(COUNTRY_STYLE[theme]);
    (layersRef.current.admin1 as L.GeoJSON | undefined)?.setStyle(ADMIN_STYLE[theme]);
    (layersRef.current.rivers as L.GeoJSON | undefined)?.setStyle(RIVER_STYLE[theme]);
    (layersRef.current.lakes as L.GeoJSON | undefined)?.setStyle(LAKE_STYLE[theme]);
    (layersRef.current.neighbors as L.LayerGroup | undefined)?.eachLayer((l) => (l as L.GeoJSON).setStyle(NEIGHBOR_STYLE[theme]));
  }, [theme]);

  return (
    <div className={className}>
      <div ref={containerRef} className="h-full w-full" role="application" aria-label={`Detailed map of ${name}`} />
      <div className="absolute right-3 top-3 z-[1000]">
        <button
          onClick={() => setPanelOpen((o) => !o)}
          className="flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-sm font-medium shadow-md hover:bg-accent transition-colors"
          aria-expanded={panelOpen}
          aria-controls="map-layers-panel"
        >
          <Layers className="h-4 w-4" /> Layers
        </button>
        {panelOpen && (
          <div id="map-layers-panel" className="mt-2 w-64 rounded-lg border bg-card p-3 shadow-xl space-y-2.5">
            {(Object.keys(LAYER_LABELS) as LayerKey[]).map((key) => (
              <label key={key} className="flex items-center justify-between gap-2 text-sm cursor-pointer">
                <span>{LAYER_LABELS[key]}</span>
                <Switch
                  checked={visible[key]}
                  onCheckedChange={(checked) =>
                    setVisible((v) => ({
                      ...v,
                      [key]: checked,
                      ...(checked && key === "streets" ? { terrain: false } : {}),
                      ...(checked && key === "terrain" ? { streets: false } : {}),
                    }))
                  }
                  aria-label={LAYER_LABELS[key]}
                />
              </label>
            ))}
            <p className="pt-1 text-xs text-muted-foreground border-t">Street &amp; terrain basemaps stream from OSM/OpenTopoMap and need a network connection.</p>
          </div>
        )}
      </div>
    </div>
  );
}
