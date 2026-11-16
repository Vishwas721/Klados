"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { IntentFit, IntentSource, IntentSourceKey, IntentStats, IntentStatus, LeadStats } from "@/lib/types";
import { fetchIntentSources, fetchIntentStats, fetchLeadStats, pollIntentSource } from "@/lib/api";
import { FIT_META, FIT_ORDER, STATUS_META, STATUS_ORDER } from "@/lib/intent";
import { useToast } from "@/lib/useToast";
import { LENSES, Lens, Masthead } from "@/components/Masthead";
import { CommandPalette, PaletteCommand } from "@/components/CommandPalette";
import { RequestsDesk } from "@/components/requests/RequestsDesk";
import { BusinessesDesk } from "@/components/businesses/BusinessesDesk";
import { SourcesDesk } from "@/components/sources/SourcesDesk";
import { ToastContainer } from "@/components/ToastContainer";

const REFRESH_MS = 60_000;

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
}

function lensFromHash(): Lens {
  const h = typeof window === "undefined" ? "" : window.location.hash.slice(1);
  return LENSES.some((l) => l.key === h) ? (h as Lens) : "requests";
}

export default function DeskPage() {
  const [lens, setLensState] = useState<Lens>("requests");
  const [intentStats, setIntentStats] = useState<IntentStats | null>(null);
  const [leadStats, setLeadStats] = useState<LeadStats | null>(null);
  const [sources, setSources] = useState<IntentSource[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [view, setView] = useState<IntentStatus>("NEW");
  const [fit, setFit] = useState<IntentFit | null>(null);
  const { toasts, toast, dismiss } = useToast();

  const setLens = useCallback((next: Lens) => {
    setLensState(next);
    history.replaceState(null, "", `#${next}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  useEffect(() => {
    setLensState(lensFromHash());
    const onHash = () => setLensState(lensFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const loadStats = useCallback(async () => {
    const [i, l, s] = await Promise.allSettled([fetchIntentStats(), fetchLeadStats(), fetchIntentSources()]);
    if (i.status === "fulfilled") setIntentStats(i.value);
    if (l.status === "fulfilled") setLeadStats(l.value);
    if (s.status === "fulfilled") setSources(s.value);
  }, []);

  const refreshAll = useCallback(() => {
    loadStats();
    setRefreshKey((k) => k + 1);
  }, [loadStats]);

  useEffect(() => {
    loadStats();
    const t = setInterval(refreshAll, REFRESH_MS);
    return () => clearInterval(t);
  }, [loadStats, refreshAll]);

  const pollSource = useCallback(
    async (key: IntentSourceKey) => {
      try {
        await pollIntentSource(key);
        setSources((prev) => prev.map((s) => (s.key === key ? { ...s, poll_requested: true } : s)));
        // The radar picks it up within ~10 s; look again shortly after
        setTimeout(refreshAll, 15_000);
      } catch (err) {
        toast(err instanceof Error ? err.message : "Couldn't queue the check", "error");
      }
    },
    [refreshAll, toast]
  );

  const pollAll = useCallback(() => {
    sources.filter((s) => s.configured).forEach((s) => pollSource(s.key));
    toast("Checking every source now. New requests land in the inbox shortly.", "info");
  }, [sources, pollSource, toast]);

  // Global keys: ⌘K / Ctrl+K palette, 1-3 lenses
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target) || paletteOpen) return;
      const l = LENSES.find((x) => x.hotkey === e.key);
      if (l) setLens(l.key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [paletteOpen, setLens]);

  const commands = useMemo<PaletteCommand[]>(
    () => [
      ...LENSES.map((l) => ({
        id: `lens-${l.key}`,
        group: "Go to",
        label: `${l.verb} ${l.noun}`,
        hint: l.hotkey,
        run: () => setLens(l.key),
      })),
      ...STATUS_ORDER.map((s) => ({
        id: `tray-${s}`,
        group: "Requests",
        label: `Open ${STATUS_META[s].label.toLowerCase()}`,
        run: () => {
          setView(s);
          setLens("requests");
        },
      })),
      ...FIT_ORDER.map((f) => ({
        id: `fit-${f}`,
        group: "Requests",
        label: `Only “${FIT_META[f].label}”`,
        run: () => {
          setFit(f);
          setLens("requests");
        },
      })),
      { id: "fit-all", group: "Requests", label: "Show every kind of request", run: () => setFit(null) },
      { id: "poll-all", group: "Radar", label: "Check every source now", run: pollAll },
      { id: "refresh", group: "Radar", label: "Refresh this page's data", run: refreshAll },
    ],
    [setLens, pollAll, refreshAll]
  );

  return (
    <main className="mx-auto max-w-[1400px] px-4 pb-24 sm:px-8">
      <Masthead
        lens={lens}
        onLens={setLens}
        intentStats={intentStats}
        leadStats={leadStats}
        sources={sources}
        onOpenPalette={() => setPaletteOpen(true)}
      />

      {lens === "requests" && (
        <RequestsDesk
          stats={intentStats}
          view={view}
          onView={setView}
          fit={fit}
          onFit={setFit}
          refreshKey={refreshKey}
          onChanged={loadStats}
          toast={toast}
        />
      )}
      {lens === "businesses" && (
        <BusinessesDesk stats={leadStats} refreshKey={refreshKey} onChanged={loadStats} toast={toast} />
      )}
      {lens === "sources" && <SourcesDesk sources={sources} stats={intentStats} onPoll={pollSource} />}

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </main>
  );
}
