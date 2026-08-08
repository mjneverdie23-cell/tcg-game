import Link from "next/link";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="container flex flex-1 flex-col items-center justify-center gap-4 py-20 text-center">
      <Compass className="h-12 w-12 text-muted-foreground" />
      <h1 className="text-3xl font-bold">Off the map</h1>
      <p className="max-w-md text-muted-foreground">We couldn&apos;t find that page. It may have moved, or the country slug doesn&apos;t exist.</p>
      <div className="flex gap-2">
        <Button asChild><Link href="/">World map</Link></Button>
        <Button asChild variant="outline"><Link href="/browse">Browse countries</Link></Button>
      </div>
    </div>
  );
}
