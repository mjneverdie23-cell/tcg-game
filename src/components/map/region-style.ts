/**
 * Political-map coloring: each UN region gets a muted fill from the atlas
 * palette, tuned separately for light and dark themes so the map reads like a
 * printed political atlas in both modes.
 */

export type MapTheme = "light" | "dark";

const REGION_FILLS: Record<MapTheme, Record<string, string>> = {
  light: { Africa: "#e8c983", Americas: "#a9d6b4", Asia: "#e7b1a2", Europe: "#a8c6e8", Oceania: "#c9b8e8", Antarctic: "#e6e8ea", territory: "#d3d6cf" },
  dark: { Africa: "#5c4a22", Americas: "#274a30", Asia: "#54322a", Europe: "#24405e", Oceania: "#3c3158", Antarctic: "#2c3238", territory: "#272b26" },
};

const BORDER: Record<MapTheme, string> = { light: "#7c8894", dark: "#55606c" };
export const HOVER_COLOR: Record<MapTheme, string> = { light: "#2a78d6", dark: "#3987e5" };

export function regionFill(region: string | null, sovereign: boolean, theme: MapTheme): string {
  const fills = REGION_FILLS[theme];
  if (!sovereign) return fills.territory;
  return fills[region ?? ""] ?? fills.territory;
}

export function baseStyle(region: string | null, sovereign: boolean, theme: MapTheme) {
  return {
    fillColor: regionFill(region, sovereign, theme),
    fillOpacity: sovereign ? 0.85 : 0.55,
    color: BORDER[theme],
    weight: 0.7,
    opacity: 0.9,
  };
}

export function hoverStyle(theme: MapTheme) {
  return { fillColor: HOVER_COLOR[theme], fillOpacity: 0.45, color: HOVER_COLOR[theme], weight: 2, opacity: 1, dashArray: "6 4" };
}
