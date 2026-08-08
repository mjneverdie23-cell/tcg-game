import Link from "next/link";
import { WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";

export const metadata = { title: "Offline" };

export default function OfflinePage() {
  return (
    <div className="container flex flex-1 flex-col items-center justify-center gap-4 py-20 text-center">
      <WifiOff className="h-12 w-12 text-muted-foreground" />
      <h1 className="text-2xl font-bold">You&apos;re offline</h1>
      <p className="max-w-md text-muted-foreground">
        This page isn&apos;t cached yet. Countries you&apos;ve already visited remain available offline — try one of those, or reconnect to explore the full atlas.
      </p>
      <Button asChild><Link href="/">Back to the map</Link></Button>
    </div>
  );
}
