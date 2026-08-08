"use client";

/**
 * Interactive chart renderer (Recharts) with an accessible table toggle.
 *
 * Follows the atlas data-viz system: one hue for magnitude (bar/line/area),
 * the categorical palette for pie slices, recessive gridlines, thin marks and
 * a tooltip. Every chart ships a table view so identity is never colour-alone.
 */

import * as React from "react";
import { useTheme } from "next-themes";
import { BarChart, Bar, PieChart, Pie, Cell, LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Table2, BarChart3 } from "lucide-react";
import { formatCompact } from "@/lib/format";
import type { ChartDatum } from "@/lib/types";

type Props = { chart: "bar" | "pie" | "line" | "area"; title: string; unit?: string; data: ChartDatum[]; note?: string };

const LIGHT = { ink: "#0b0b0b", ink2: "#52514e", grid: "#e1e0d9", axis: "#c3c2b7", surface: "#fcfcfb" };
const DARK = { ink: "#ffffff", ink2: "#c3c2b7", grid: "#2c2c2a", axis: "#383835", surface: "#1a1a19" };
const SERIES_LIGHT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"];
const SERIES_DARK = ["#3987e5", "#199e70", "#c98500", "#008300", "#9085e9", "#e66767", "#d55181", "#d95926"];

export function ChartBlock({ chart, title, unit, data, note }: Props) {
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  const c = dark ? DARK : LIGHT;
  const series = dark ? SERIES_DARK : SERIES_LIGHT;
  const [view, setView] = React.useState<"chart" | "table">("chart");

  const tooltipStyle = { background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 8, color: c.ink, fontSize: 12 };
  const fmt = (v: number) => formatCompact(v);

  return (
    <figure className="rounded-lg border bg-card p-4">
      <figcaption className="mb-3 flex items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">{title}</div>
          {unit && <div className="text-xs text-muted-foreground">{unit}</div>}
        </div>
        <button
          onClick={() => setView((v) => (v === "chart" ? "table" : "chart"))}
          className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs hover:bg-accent"
          aria-label={view === "chart" ? "Show data as table" : "Show chart"}
        >
          {view === "chart" ? <Table2 className="h-3.5 w-3.5" /> : <BarChart3 className="h-3.5 w-3.5" />}
          {view === "chart" ? "Table" : "Chart"}
        </button>
      </figcaption>

      {view === "table" ? (
        <div className="max-h-72 overflow-auto scrollbar-thin">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-1.5 pr-4 font-medium">Name</th>
                <th className="py-1.5 font-medium tabular-nums">Value{unit ? ` (${unit})` : ""}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.name} className="border-b border-border/50">
                  <td className="py-1.5 pr-4">{d.name}</td>
                  <td className="py-1.5 tabular-nums">{d.value.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            {chart === "bar" ? (
              <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <CartesianGrid horizontal={false} stroke={c.grid} />
                <XAxis type="number" tickFormatter={fmt} stroke={c.axis} tick={{ fill: c.ink2, fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={92} stroke={c.axis} tick={{ fill: c.ink2, fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => v.toLocaleString()} cursor={{ fill: dark ? "#ffffff10" : "#00000008" }} />
                <Bar dataKey="value" fill={series[0]} radius={[0, 4, 4, 0]} />
              </BarChart>
            ) : chart === "pie" ? (
              <PieChart>
                <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => v.toLocaleString()} />
                <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} innerRadius={45} paddingAngle={2} label={{ fill: c.ink2, fontSize: 11 }}>
                  {data.map((_, i) => (
                    <Cell key={i} fill={series[i % series.length]} stroke={c.surface} strokeWidth={2} />
                  ))}
                </Pie>
              </PieChart>
            ) : chart === "line" ? (
              <LineChart data={data} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <CartesianGrid stroke={c.grid} />
                <XAxis dataKey="name" stroke={c.axis} tick={{ fill: c.ink2, fontSize: 11 }} />
                <YAxis tickFormatter={fmt} stroke={c.axis} tick={{ fill: c.ink2, fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => v.toLocaleString()} />
                <Line type="monotone" dataKey="value" stroke={series[0]} strokeWidth={2} dot={{ r: 3, fill: series[0] }} />
              </LineChart>
            ) : (
              <AreaChart data={data} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <CartesianGrid stroke={c.grid} />
                <XAxis dataKey="name" stroke={c.axis} tick={{ fill: c.ink2, fontSize: 11 }} />
                <YAxis tickFormatter={fmt} stroke={c.axis} tick={{ fill: c.ink2, fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => v.toLocaleString()} />
                <Area type="monotone" dataKey="value" stroke={series[0]} fill={series[0]} fillOpacity={0.2} strokeWidth={2} />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
      {note && <p className="mt-2 text-xs text-muted-foreground">{note}</p>}
    </figure>
  );
}
