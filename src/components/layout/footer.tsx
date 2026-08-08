import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t py-6 text-sm text-muted-foreground">
      <div className="container flex flex-col items-center justify-between gap-3 sm:flex-row">
        <p>
          <span className="font-medium text-foreground">World Atlas</span> — an open-data encyclopedia of every country.
        </p>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>
            Data:{" "}
            <a className="underline underline-offset-2 hover:text-foreground" href="https://www.naturalearthdata.com/" target="_blank" rel="noreferrer">Natural Earth</a>,{" "}
            <a className="underline underline-offset-2 hover:text-foreground" href="https://restcountries.com/" target="_blank" rel="noreferrer">REST Countries</a>,{" "}
            <a className="underline underline-offset-2 hover:text-foreground" href="https://commons.wikimedia.org/" target="_blank" rel="noreferrer">Wikimedia</a>
          </span>
          <Link href="/about" className="underline underline-offset-2 hover:text-foreground">About &amp; sources</Link>
        </p>
      </div>
    </footer>
  );
}
