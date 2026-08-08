import Link from "next/link";
import { Earth, Heart, LibraryBig } from "lucide-react";
import { SearchCommand } from "@/components/search/search-command";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";

export function Header() {
  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/65">
      <div className="container flex h-14 items-center gap-2">
        <Link href="/" className="flex items-center gap-2 mr-2 shrink-0" aria-label="World Atlas home">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Earth className="h-5 w-5" />
          </span>
          <span className="hidden font-semibold tracking-tight sm:inline-block">World Atlas</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm" aria-label="Primary">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/browse">
              <LibraryBig className="h-4 w-4" />
              <span className="hidden md:inline">Browse</span>
            </Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/favorites">
              <Heart className="h-4 w-4" />
              <span className="hidden md:inline">Favorites</span>
            </Link>
          </Button>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <SearchCommand />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
