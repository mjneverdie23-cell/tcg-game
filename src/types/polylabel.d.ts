declare module "polylabel" {
  /** Returns the pole of inaccessibility [x, y] for a GeoJSON-style polygon ring array. */
  export default function polylabel(polygon: number[][][], precision?: number): number[];
}
