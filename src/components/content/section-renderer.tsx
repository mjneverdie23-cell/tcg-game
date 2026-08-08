"use client";

/**
 * Renders an array of typed ContentBlocks (see src/lib/types.ts). This is the
 * single place block types map to UI — pipeline output and rendering stay in
 * lockstep through the ContentBlock union.
 */

import * as React from "react";
import { ExternalLink } from "lucide-react";
import type { ContentBlock, TimelineEvent } from "@/lib/types";
import { RichText, InlineMarkdown } from "./rich-text";
import { ChartBlock } from "./chart-block";
import { SmartImage } from "./smart-image";
import { Icon } from "./icon";
import { Badge } from "@/components/ui/badge";

function Stats({ items }: { items: Extract<ContentBlock, { type: "stats" }>["items"] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map((s, i) => (
        <div key={i} className="rounded-lg border bg-card p-3">
          <div className="text-xs text-muted-foreground">{s.label}</div>
          <div className="mt-0.5 font-semibold leading-tight">{s.value}</div>
          {s.hint && <div className="mt-0.5 text-[11px] text-muted-foreground">{s.hint}</div>}
        </div>
      ))}
    </div>
  );
}

function DataTable({ block }: { block: Extract<ContentBlock, { type: "table" }> }) {
  return (
    <figure className="overflow-x-auto scrollbar-thin rounded-lg border">
      <table className="w-full text-sm">
        {block.caption && <caption className="bg-muted/50 px-3 py-2 text-left text-xs font-medium text-muted-foreground">{block.caption}</caption>}
        <thead>
          <tr className="border-b bg-muted/30 text-left">
            {block.headers.map((h, i) => (
              <th key={i} className="px-3 py-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, r) => (
            <tr key={r} className="border-b border-border/50 last:border-0">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 align-top"><InlineMarkdown text={cell} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="relative ml-3 space-y-4 border-l-2 border-border pl-6">
      {events.map((e, i) => (
        <li key={i} className="relative">
          <span className="absolute -left-[1.9rem] top-1 grid h-4 w-4 place-items-center rounded-full border-2 border-primary bg-background">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          </span>
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-mono text-xs font-semibold text-primary">{e.when}</span>
            {e.era && <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">{e.era}</Badge>}
            <span className="font-semibold">{e.title}</span>
          </div>
          {e.description && <p className="mt-0.5 text-sm text-muted-foreground"><InlineMarkdown text={e.description} /></p>}
        </li>
      ))}
    </ol>
  );
}

function Facts({ cards }: { cards: Extract<ContentBlock, { type: "facts" }>["cards"] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {cards.map((card, i) => (
        <div key={i} className="flex gap-3 rounded-lg border bg-card p-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-accent text-accent-foreground">
            <Icon name={card.icon} className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold">{card.title}</div>
            <div className="text-sm text-muted-foreground"><InlineMarkdown text={card.body} /></div>
          </div>
        </div>
      ))}
    </div>
  );
}

function FeatureCards({ block }: { block: Extract<ContentBlock, { type: "feature-cards" }> }) {
  return (
    <div className="space-y-3">
      {block.title && <h4 className="text-sm font-semibold text-muted-foreground">{block.title}</h4>}
      <div className="grid gap-4 sm:grid-cols-2">
        {block.cards.map((card, i) => (
          <div key={i} className="overflow-hidden rounded-lg border bg-card transition-shadow hover:shadow-md">
            {card.image && <SmartImage src={card.image} alt={card.name} caption={card.name} className="h-40 w-full object-cover" wrapperClassName="h-40 w-full" />}
            <div className="p-3">
              <div className="flex items-baseline justify-between gap-2">
                <div className="font-semibold">{card.name}</div>
                {card.meta && <span className="shrink-0 text-xs text-muted-foreground">{card.meta}</span>}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{card.blurb}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Links({ block }: { block: Extract<ContentBlock, { type: "links" | "references" }> }) {
  const isRef = block.type === "references";
  return (
    <div className="space-y-2">
      {"title" in block && block.title && <h4 className="text-sm font-semibold text-muted-foreground">{block.title}</h4>}
      <ul className={isRef ? "space-y-1.5" : "grid gap-2 sm:grid-cols-2"}>
        {block.items.map((item, i) => (
          <li key={i}>
            <a href={item.href} target="_blank" rel="noreferrer" className="group flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-sm transition-colors hover:bg-accent">
              <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="flex-1">{item.label}</span>
              {item.source && <Badge variant="outline" className="shrink-0 text-[10px]">{item.source}</Badge>}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Gallery({ images }: { images: Extract<ContentBlock, { type: "gallery" }>["images"] }) {
  if (images.length === 1) {
    const img = images[0];
    return (
      <figure className="overflow-hidden rounded-lg border">
        <SmartImage src={img.src} alt={img.alt} caption={img.caption} className="max-h-[420px] w-full object-cover" wrapperClassName="w-full" />
        {img.caption && <figcaption className="bg-card px-3 py-2 text-xs text-muted-foreground">{img.caption}{img.credit ? ` · ${img.credit}` : ""}</figcaption>}
      </figure>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {images.map((img, i) => (
        <figure key={i} className="overflow-hidden rounded-lg border bg-card">
          <SmartImage src={img.src} alt={img.alt} caption={img.caption} className="h-36 w-full object-cover" wrapperClassName="h-36 w-full" />
          {img.caption && <figcaption className="px-2 py-1.5 text-[11px] text-muted-foreground">{img.caption}</figcaption>}
        </figure>
      ))}
    </div>
  );
}

function Block({ block }: { block: ContentBlock }) {
  switch (block.type) {
    case "prose":
      return <RichText markdown={block.markdown} />;
    case "stats":
      return <Stats items={block.items} />;
    case "table":
      return <DataTable block={block} />;
    case "timeline":
      return <Timeline events={block.events} />;
    case "chart":
      return <ChartBlock chart={block.chart} title={block.title} unit={block.unit} data={block.data} note={block.note} />;
    case "facts":
      return <Facts cards={block.cards} />;
    case "feature-cards":
      return <FeatureCards block={block} />;
    case "links":
    case "references":
      return <Links block={block} />;
    case "gallery":
      return <Gallery images={block.images} />;
    case "quote":
      return (
        <blockquote className="border-l-4 border-primary pl-4 italic text-muted-foreground">
          “{block.text}”{block.attribution && <footer className="mt-1 text-sm not-italic">— {block.attribution}</footer>}
        </blockquote>
      );
    default:
      return null;
  }
}

export function SectionRenderer({ blocks }: { blocks: ContentBlock[] }) {
  return (
    <div className="space-y-5">
      {blocks.map((block, i) => (
        <Block key={i} block={block} />
      ))}
    </div>
  );
}
