"use client";

import { useEffect, useState } from "react";
import { Command, Moon, Sun } from "lucide-react";
import { IntentSource, IntentStats, LeadStats } from "@/lib/types";

export type Lens = "requests" | "businesses" | "sources";

export const LENSES: { key: Lens; verb: string; noun: string; hotkey: string }[] = [
  { key: "requests", verb: "Read the", noun: "requests", hotkey: "1" },
  { key: "businesses", verb: "Work the", noun: "businesses", hotkey: "2" },
  { key: "sources", verb: "Tune the", noun: "sources", hotkey: "3" },
];

interface MastheadProps {
  lens: Lens;
  onLens: (lens: Lens) => void;
  intentStats: IntentStats | null;
  leadStats: LeadStats | null;
  sources: IntentSource[];
  onOpenPalette: () => void;
}

function Num({ children }: { children: React.ReactNode }) {
  return <span className="text-signal tabular-nums">{children}</span>;
}

function Headline({ lens, intentStats, leadStats, sources }: Omit<MastheadProps, "onLens" | "onOpenPalette">) {
  if (lens === "requests") {
    if (!intentStats || intentStats.total === 0) {
      return <>No requests yet. The radar is listening.</>;
    }
    const fresh = intentStats.new_last_24h;
    return (
      <>
        <Num>{fresh}</Num> {fresh === 1 ? "person" : "people"} asked for help today.{" "}
        <span className="italic text-muted">
          <Num>{intentStats.hot}</Num> {intentStats.hot === 1 ? "is" : "are"} worth your morning.
        </span>
      </>
    );
  }
  if (lens === "businesses") {
    if (!leadStats || leadStats.total === 0) return <>No businesses audited yet. Run a scan.</>;
    const ghosts = leadStats.by_category.DIGITAL_GHOST ?? 0;
    return (
      <>
        <Num>{leadStats.total.toLocaleString()}</Num> businesses audited.{" "}
        <span className="italic text-muted">
          <Num>{ghosts.toLocaleString()}</Num> still have no website.
        </span>
      </>
    );
  }
  const live = sources.filter((s) => s.configured && s.state !== "error" && s.state !== "backing_off").length;
  const troubled = sources.filter((s) => s.state === "error" || s.state === "backing_off").length;
  return (
    <>
      <Num>{live}</Num> of {sources.length || 5} sources are listening.{" "}
      <span className="italic text-muted">
        {troubled ? (
          <>
            <Num>{troubled}</Num> need{troubled === 1 ? "s" : ""} a look.
          </>
        ) : (
          "All quiet on the wire."
        )}
      </span>
    </>
  );
}

function useToday(): string {
  const [today, setToday] = useState("");
  useEffect(() => {
    setToday(
      new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
    );
  }, []);
  return today;
}

function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);

  useEffect(() => {
    const explicit = document.documentElement.dataset.theme;
    setDark(explicit ? explicit === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    try {
      localStorage.setItem("klados-theme", next ? "dark" : "light");
    } catch {
      // private mode: the choice just won't persist
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle light and dark"
      className="grid h-8 w-8 place-items-center rounded-full border border-line text-muted transition hover:border-ink hover:text-ink"
    >
      {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
    </button>
  );
}

export function Masthead(props: MastheadProps) {
  const { lens, onLens, intentStats, leadStats, sources, onOpenPalette } = props;
  const today = useToday();
  const live = sources.filter((s) => s.configured && s.state === "ok").length;

  const counts: Record<Lens, number | null> = {
    requests: intentStats?.by_status.NEW ?? null,
    businesses: leadStats?.total ?? null,
    sources: sources.length ? live : null,
  };

  return (
    <header className="pt-6 sm:pt-8">
      {/* Dateline */}
      <div className="flex items-center justify-between gap-3 border-b border-ink pb-3">
        <div className="flex items-baseline gap-3">
          <span className="font-serif text-2xl italic leading-none">Klados</span>
          <span className="hidden text-xs text-muted sm:inline" suppressHydrationWarning>
            {today}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden items-center gap-2 rounded-full border border-line px-3 py-1 text-xs text-muted sm:inline-flex">
            <span className={`h-1.5 w-1.5 rounded-full ${live ? "breathe bg-ok" : "bg-faint"}`} />
            {live ? `radar on · ${live} live` : "radar idle"}
          </span>
          <button
            type="button"
            onClick={onOpenPalette}
            className="inline-flex h-8 items-center gap-1.5 rounded-full border border-line px-3 text-xs text-muted transition hover:border-ink hover:text-ink"
          >
            <Command className="h-3.5 w-3.5" />
            <span>K</span>
          </button>
          <ThemeToggle />
        </div>
      </div>

      {/* Headline */}
      <h1 className="mt-6 max-w-4xl font-serif text-[2.1rem] leading-[1.08] tracking-tight sm:mt-8 sm:text-5xl lg:text-6xl">
        <Headline lens={lens} intentStats={intentStats} leadStats={leadStats} sources={sources} />
      </h1>

      {/* Lens switch: a sentence, not a navbar */}
      <nav aria-label="Views" className="mt-6 flex flex-wrap items-baseline gap-x-6 gap-y-2 sm:mt-8">
        {LENSES.map((l, i) => {
          const active = l.key === lens;
          return (
            <span key={l.key} className="flex items-baseline gap-6">
              <button
                type="button"
                onClick={() => onLens(l.key)}
                aria-current={active ? "page" : undefined}
                className="group flex items-baseline gap-1.5 text-left"
              >
                <span className={`text-sm ${active ? "text-muted" : "text-faint"}`}>{l.verb}</span>
                <span
                  className={`relative font-serif text-2xl italic transition-colors sm:text-3xl ${
                    active ? "text-ink" : "text-faint group-hover:text-muted"
                  }`}
                >
                  {l.noun}
                  <span
                    className={`absolute -bottom-1 left-0 h-[3px] rounded-full bg-signal transition-all duration-300 ${
                      active ? "w-full" : "w-0 group-hover:w-1/3"
                    }`}
                  />
                </span>
                {counts[l.key] !== null && (
                  <sup className={`font-mono text-[11px] ${active ? "text-signal" : "text-faint"}`}>
                    {counts[l.key]}
                  </sup>
                )}
              </button>
              {i < LENSES.length - 1 && <span className="hidden text-faint sm:inline">·</span>}
            </span>
          );
        })}
      </nav>
    </header>
  );
}
