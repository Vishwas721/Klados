"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { IntentFit, IntentPost, IntentSourceKey, IntentStats, IntentStatus } from "@/lib/types";
import { fetchIntentPosts, updateIntentStatus } from "@/lib/api";
import { Band, FIT_META, FIT_ORDER, SOURCE_META, SOURCE_ORDER, STATUS_META, STATUS_ORDER, askedAt, band } from "@/lib/intent";
import { ToastVariant } from "@/lib/useToast";
import { RequestCard } from "./RequestCard";
import { RequestReader } from "./RequestReader";

export type SortMode = "best" | "newest";

interface RequestsDeskProps {
  stats: IntentStats | null;
  view: IntentStatus;
  onView: (v: IntentStatus) => void;
  fit: IntentFit | null;
  onFit: (f: IntentFit | null) => void;
  refreshKey: number;
  onChanged: () => void;
  toast: (message: string, variant?: ToastVariant, durationMs?: number) => void;
}

const BANDS: Band[] = ["Last hour", "Today", "This week", "Earlier"];

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition ${
        active ? "border-ink bg-ink text-paper" : "border-line text-muted hover:border-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

export function RequestsDesk({ stats, view, onView, fit, onFit, refreshKey, onChanged, toast }: RequestsDeskProps) {
  const [posts, setPosts] = useState<IntentPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<IntentSourceKey | null>(null);
  const [sort, setSort] = useState<SortMode>("best");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const listRef = useRef<HTMLDivElement>(null);

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        setPosts(await fetchIntentPosts({ status: view, limit: 400 }));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load requests");
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [view]
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (refreshKey) load(true);
  }, [refreshKey, load]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = posts.filter(
      (p) =>
        (!fit || p.fit === fit) &&
        (!source || p.source === source) &&
        (!q || `${p.title} ${p.body} ${p.channel ?? ""}`.toLowerCase().includes(q))
    );
    return list.sort((a, b) =>
      sort === "best"
        ? b.score - a.score || +new Date(askedAt(b)) - +new Date(askedAt(a))
        : +new Date(askedAt(b)) - +new Date(askedAt(a))
    );
  }, [posts, fit, source, query, sort]);

  // Keep a valid selection as the list changes
  useEffect(() => {
    if (!visible.length) {
      setSelectedId(null);
    } else if (!selectedId || !visible.some((p) => p.id === selectedId)) {
      setSelectedId(visible[0].id);
    }
  }, [visible, selectedId]);

  const selected = visible.find((p) => p.id === selectedId) ?? null;
  const reply = selected ? drafts[selected.id] ?? selected.reply_draft ?? "" : "";

  const grouped = useMemo(() => {
    if (sort === "best") return [{ band: null as Band | null, items: visible }];
    return BANDS.map((b) => ({ band: b as Band | null, items: visible.filter((p) => band(p) === b) })).filter(
      (g) => g.items.length
    );
  }, [visible, sort]);

  const move = useCallback(
    (delta: number) => {
      if (!visible.length) return;
      const i = Math.max(0, visible.findIndex((p) => p.id === selectedId));
      const next = visible[Math.min(visible.length - 1, Math.max(0, i + delta))];
      setSelectedId(next.id);
      listRef.current
        ?.querySelector(`[data-post-id="${next.id}"]`)
        ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    },
    [visible, selectedId]
  );

  const fileAs = useCallback(
    async (status: IntentStatus) => {
      if (!selected || busy) return;
      const idx = visible.findIndex((p) => p.id === selected.id);
      const after = visible[idx + 1] ?? visible[idx - 1] ?? null;
      setBusy(true);
      try {
        await updateIntentStatus(selected.id, status);
        setPosts((prev) => prev.filter((p) => p.id !== selected.id));
        setSelectedId(after?.id ?? null);
        toast(`${STATUS_META[status].label}: ${selected.title.slice(0, 60)}`, status === "WON" ? "success" : "info", 2500);
        onChanged();
      } catch (err) {
        toast(err instanceof Error ? err.message : "Update failed", "error");
      } finally {
        setBusy(false);
      }
    },
    [selected, busy, visible, toast, onChanged]
  );

  const copyReply = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(reply);
      return true;
    } catch {
      toast("Couldn't reach the clipboard; select the text and copy it.", "error");
      return false;
    }
  }, [reply, toast]);

  const copyAndOpen = useCallback(async () => {
    if (!selected) return;
    await copyReply();
    window.open(selected.url, "_blank", "noopener,noreferrer");
  }, [selected, copyReply]);

  // Keyboard: j/k move, s/r/w/x/u file, c copy, o copy & open
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return;
      const k = e.key.toLowerCase();
      if (k === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        move(1);
      } else if (k === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        move(-1);
      } else if (k === "c" && selected) {
        copyReply().then((ok) => ok && toast("Reply copied", "success", 1500));
      } else if (k === "o" && selected) {
        copyAndOpen();
      } else {
        const target = STATUS_ORDER.find((s) => STATUS_META[s].key.toLowerCase() === k);
        if (target && selected && target !== selected.status) fileAs(target);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, selected, copyReply, copyAndOpen, fileAs, toast]);

  const readerProps = selected && {
    post: selected,
    reply,
    onReplyChange: (text: string) => setDrafts((d) => ({ ...d, [selected.id]: text })),
    onStatus: fileAs,
    onCopy: () => {
      copyReply();
    },
    onCopyAndOpen: copyAndOpen,
    busy,
  };

  return (
    <section className="mt-8">
      {/* Trays: where a request sits in your pipeline */}
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3 border-b border-line">
        {STATUS_ORDER.map((s) => {
          const active = s === view;
          const n = stats?.by_status[s] ?? 0;
          return (
            <button
              key={s}
              type="button"
              onClick={() => onView(s)}
              className={`-mb-px border-b-2 pb-2.5 text-sm transition ${
                active ? "border-signal text-ink" : "border-transparent text-muted hover:text-ink"
              }`}
            >
              {STATUS_META[s].label}
              <span className={`ml-1.5 font-mono text-[11px] ${active ? "text-signal" : "text-faint"}`}>{n}</span>
            </button>
          );
        })}
      </div>

      {/* Filters */}
      <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip active={!fit} onClick={() => onFit(null)}>
            Everything
          </Chip>
          {FIT_ORDER.map((f) => (
            <Chip key={f} active={fit === f} onClick={() => onFit(fit === f ? null : f)}>
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: FIT_META[f].tone }} />
              {FIT_META[f].label}
              {stats?.by_fit[f] ? <span className="opacity-60">{stats.by_fit[f]}</span> : null}
            </Chip>
          ))}
          <span className="mx-1 hidden h-4 w-px bg-line sm:inline-block" />
          {SOURCE_ORDER.map((s) => (
            <Chip key={s} active={source === s} onClick={() => setSource(source === s ? null : s)}>
              <span className="font-mono text-[10px]">{SOURCE_META[s].mark}</span>
              <span className="hidden sm:inline">{SOURCE_META[s].label}</span>
            </Chip>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label className="relative flex-1 lg:w-56 lg:flex-none">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search requests"
              className="h-8 w-full rounded-full border border-line bg-card pl-8 pr-3 text-sm outline-none placeholder:text-faint focus:border-ink"
            />
          </label>
          <div className="flex rounded-full border border-line p-0.5 text-xs">
            {(["best", "newest"] as SortMode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setSort(m)}
                className={`rounded-full px-3 py-1 capitalize transition ${
                  sort === m ? "bg-ink text-paper" : "text-muted hover:text-ink"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <p className="mt-4 rounded-xl border border-bad/40 px-4 py-3 text-sm text-bad">
          {error}. Is the API running?
        </p>
      )}

      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {/* The list */}
        <div ref={listRef} className="min-w-0">
          {loading ? (
            <ul className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <li key={i} className="h-[68px] animate-pulse rounded-xl bg-sunk" />
              ))}
            </ul>
          ) : visible.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-line px-6 py-14 text-center">
              <p className="font-serif text-2xl italic">
                {view === "NEW" ? "Inbox zero." : `Nothing in ${STATUS_META[view].label.toLowerCase()}.`}
              </p>
              <p className="mx-auto mt-2 max-w-xs text-sm text-muted">
                {view === "NEW"
                  ? "New requests land here as the radar finds them. Check the sources if it stays quiet."
                  : "Requests you file here will show up in this tray."}
              </p>
            </div>
          ) : (
            grouped.map((g) => (
              <div key={g.band ?? "all"} className="mb-4">
                {g.band && (
                  <h3 className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
                    {g.band}
                  </h3>
                )}
                <ul className="space-y-0.5">
                  {g.items.map((p) => (
                    <li key={p.id}>
                      <RequestCard
                        post={p}
                        selected={p.id === selectedId}
                        onSelect={() => {
                          setSelectedId(p.id);
                          setMobileOpen(true);
                        }}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
          {!loading && visible.length > 0 && (
            <p className="px-3 pt-2 text-[11px] text-faint">
              <kbd className="font-mono">J</kbd>/<kbd className="font-mono">K</kbd> to move ·{" "}
              <kbd className="font-mono">O</kbd> copy reply &amp; open · <kbd className="font-mono">S</kbd> shortlist ·{" "}
              <kbd className="font-mono">X</kbd> bin
            </p>
          )}
        </div>

        {/* The reader */}
        <div className="hidden min-w-0 lg:block">
          <div className="scroll-quiet sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto">
            {readerProps ? (
              <RequestReader {...readerProps} />
            ) : (
              !loading && (
                <div className="grid h-64 place-items-center rounded-2xl border border-dashed border-line text-sm text-faint">
                  Pick a request to read it.
                </div>
              )
            )}
          </div>
        </div>
      </div>

      {/* Mobile: reader as a sheet */}
      {readerProps && mobileOpen && (
        <div className="fixed inset-0 z-40 overflow-y-auto bg-paper/95 p-3 backdrop-blur-sm lg:hidden">
          <RequestReader {...readerProps} onClose={() => setMobileOpen(false)} />
        </div>
      )}
    </section>
  );
}
