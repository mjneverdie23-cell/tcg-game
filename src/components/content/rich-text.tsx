import * as React from "react";
import Link from "next/link";

/**
 * Minimal, safe inline markdown renderer for pipeline-generated prose.
 * Supports **bold**, *italic*, and [label](href) links (internal via next/link,
 * external opening in a new tab). No raw HTML is ever interpreted, so content is
 * XSS-safe by construction.
 */

type Token = { type: "text" | "bold" | "italic"; value: string } | { type: "link"; label: string; href: string };

function tokenize(input: string): Token[] {
  const tokens: Token[] = [];
  const regex = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(input))) {
    if (m.index > last) tokens.push({ type: "text", value: input.slice(last, m.index) });
    if (m[1] !== undefined) tokens.push({ type: "link", label: m[1], href: m[2] });
    else if (m[3] !== undefined) tokens.push({ type: "bold", value: m[3] });
    else if (m[4] !== undefined) tokens.push({ type: "italic", value: m[4] });
    last = regex.lastIndex;
  }
  if (last < input.length) tokens.push({ type: "text", value: input.slice(last) });
  return tokens;
}

export function InlineMarkdown({ text }: { text: string }) {
  const tokens = tokenize(text);
  return (
    <>
      {tokens.map((t, i) => {
        if (t.type === "bold") return <strong key={i}>{t.value}</strong>;
        if (t.type === "italic") return <em key={i}>{t.value}</em>;
        if (t.type === "link") {
          const internal = t.href.startsWith("/");
          if (internal) return <Link key={i} href={t.href} className="text-primary underline underline-offset-2 hover:opacity-80">{t.label}</Link>;
          return <a key={i} href={t.href} target="_blank" rel="noreferrer" className="text-primary underline underline-offset-2 hover:opacity-80">{t.label}</a>;
        }
        return <React.Fragment key={i}>{t.value}</React.Fragment>;
      })}
    </>
  );
}

/** Render prose that may contain multiple paragraphs (split on blank lines). */
export function RichText({ markdown }: { markdown: string }) {
  const paragraphs = markdown.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
  return (
    <div className="space-y-3 leading-relaxed text-[0.95rem] text-foreground/90">
      {paragraphs.map((p, i) => (
        <p key={i}>
          <InlineMarkdown text={p} />
        </p>
      ))}
    </div>
  );
}
