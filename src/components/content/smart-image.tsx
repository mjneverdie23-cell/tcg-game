"use client";

import * as React from "react";
import { ImageOff } from "lucide-react";

/**
 * Image that gracefully hides itself if the source fails to load.
 *
 * Curated photos are served from Wikimedia Commons (Special:FilePath), which
 * loads directly in the visitor's browser. If a file has moved or the visitor
 * is offline, we show an unobtrusive placeholder instead of a broken icon.
 * Plain <img> is used deliberately so the browser fetches the image client-side
 * (the Next image optimizer is not in the request path).
 */
export function SmartImage({
  src,
  alt,
  className,
  wrapperClassName,
  caption,
}: {
  src: string;
  alt: string;
  className?: string;
  wrapperClassName?: string;
  caption?: string;
}) {
  const [status, setStatus] = React.useState<"loading" | "ok" | "error">("loading");

  if (status === "error") {
    return (
      <div className={wrapperClassName}>
        <div className="flex h-full min-h-24 w-full flex-col items-center justify-center gap-1 rounded-md bg-muted text-muted-foreground">
          <ImageOff className="h-5 w-5" />
          <span className="px-2 text-center text-xs">{caption ?? alt}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={wrapperClassName}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        loading="lazy"
        onLoad={() => setStatus("ok")}
        onError={() => setStatus("error")}
        className={className}
        style={status === "loading" ? { background: "hsl(var(--muted))" } : undefined}
      />
    </div>
  );
}
