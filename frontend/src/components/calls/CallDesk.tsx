"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { MessageCircle, Phone, Settings2 } from "lucide-react";
import { CallOutcome, CallStats, Lead } from "@/lib/types";
import { fetchCallQueue, fetchInterested, logCall, updateLeadStatus } from "@/lib/api";
import { CATEGORY_META } from "@/lib/categories";
import { ScriptLang, buildCallScript, buildFollowUpLink, formatPhone, telHref } from "@/lib/callScript";
import { isLandline } from "@/lib/pitch";
import { displayCity, timeAgo } from "@/lib/format";
import { ToastVariant } from "@/lib/useToast";

interface CallDeskProps {
  stats: CallStats | null;
  refreshKey: number;
  onChanged: () => void;
  toast: (message: string, variant?: ToastVariant, durationMs?: number) => void;
}

const OUTCOMES: { key: CallOutcome; label: string; hotkey: string; tone: string }[] = [
  { key: "INTERESTED", label: "Interested", hotkey: "Y", tone: "bg-ok text-white border-ok hover:brightness-110" },
  { key: "CALL_BACK", label: "Call back", hotkey: "B", tone: "border-line text-ink hover:border-ink" },
  { key: "NO_ANSWER", label: "No answer", hotkey: "A", tone: "border-line text-ink hover:border-ink" },
  { key: "NOT_INTERESTED", label: "Not interested", hotkey: "N", tone: "border-line text-muted hover:border-bad hover:text-bad" },
  { key: "WRONG_NUMBER", label: "Wrong number", hotkey: "W", tone: "border-line text-muted hover:border-bad hover:text-bad" },
];

const OUTCOME_DONE: Record<CallOutcome, string> = {
  INTERESTED: "Said yes. Send the WhatsApp follow-up while it's warm.",
  CALL_BACK: "Call back scheduled.",
  NO_ANSWER: "No answer. It comes back tomorrow (3 tries max).",
  NOT_INTERESTED: "Not interested. Won't come up again.",
  WRONG_NUMBER: "Wrong number. Removed from the queue.",
};

const CALL_BACK_OPTIONS: { label: string; hours: number }[] = [
  { label: "In 2 hours", hours: 2 },
  { label: "Tomorrow", hours: 24 },
  { label: "In 3 days", hours: 72 },
  { label: "Next week", hours: 168 },
];

const LANGS: { key: ScriptLang; label: string }[] = [
  { key: "kn", label: "ಕನ್ನಡ" },
  { key: "roman", label: "Kannada (English letters)" },
  { key: "en", label: "English" },
];

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
}

function usePref(key: string, fallback: string): [string, (v: string) => void] {
  const [value, setValue] = useState(fallback);
  useEffect(() => {
    try {
      const saved = localStorage.getItem(key);
      if (saved !== null) setValue(saved);
    } catch {
      // storage blocked: keep the default for this session
    }
  }, [key]);
  const save = (v: string) => {
    setValue(v);
    try {
      localStorage.setItem(key, v);
    } catch {
      // ignore
    }
  };
  return [value, save];
}

function Stat({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
  return (
    <div>
      <div className={`font-serif text-3xl leading-none tabular-nums ${accent ? "text-signal" : ""}`}>{value}</div>
      <div className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">{label}</div>
    </div>
  );
}

export function CallDesk({ stats, refreshKey, onChanged, toast }: CallDeskProps) {
  const [tab, setTab] = useState<"queue" | "yes">("queue");
  const [queue, setQueue] = useState<Lead[]>([]);
  const [interested, setInterested] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [pickingCallback, setPickingCallback] = useState(false);
  const [justSaidYes, setJustSaidYes] = useState<Lead | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [lang, setLang] = usePref("klados-call-lang", "kn");
  const [me, setMe] = usePref("klados-caller-name", "");
  const [portfolio, setPortfolio] = usePref("klados-portfolio", "");

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [q, yes] = await Promise.all([fetchCallQueue(60), fetchInterested()]);
      setQueue(q);
      setInterested(yes);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the call queue");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (refreshKey) load(true);
  }, [refreshKey, load]);

  useEffect(() => {
    if (!queue.length) setCurrentId(null);
    else if (!currentId || !queue.some((l) => l.id === currentId)) setCurrentId(queue[0].id);
  }, [queue, currentId]);

  const current = queue.find((l) => l.id === currentId) ?? null;

  useEffect(() => {
    setNotes(current?.call_notes ?? "");
    setPickingCallback(false);
  }, [current?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const script = useMemo(() => (current ? buildCallScript(current, me) : null), [current, me]);

  const record = useCallback(
    async (outcome: CallOutcome, callbackHours?: number) => {
      if (!current || busy) return;
      if (outcome === "CALL_BACK" && callbackHours === undefined) {
        setPickingCallback(true);
        return;
      }
      setBusy(true);
      try {
        const callbackAt =
          callbackHours !== undefined ? new Date(Date.now() + callbackHours * 3_600_000).toISOString() : undefined;
        const updated = await logCall(current.id, outcome, { notes, callbackAt });
        const idx = queue.findIndex((l) => l.id === current.id);
        const next = queue[idx + 1] ?? queue[idx - 1] ?? null;
        setQueue((prev) => prev.filter((l) => l.id !== current.id));
        setCurrentId(next?.id ?? null);
        setPickingCallback(false);
        if (outcome === "INTERESTED") {
          setInterested((prev) => [updated, ...prev]);
          setJustSaidYes(updated);
        } else {
          setJustSaidYes(null);
        }
        toast(`${current.business_name}: ${OUTCOME_DONE[outcome]}`, outcome === "INTERESTED" ? "success" : "info", 3000);
        onChanged();
      } catch (err) {
        toast(err instanceof Error ? err.message : "Couldn't save the call", "error");
      } finally {
        setBusy(false);
      }
    },
    [current, busy, notes, queue, toast, onChanged]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (tab !== "queue" || e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return;
      const hit = OUTCOMES.find((o) => o.hotkey.toLowerCase() === e.key.toLowerCase());
      if (hit) {
        e.preventDefault();
        record(hit.key);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tab, record]);

  const markConverted = async (lead: Lead) => {
    try {
      const updated = await updateLeadStatus(lead.id, "CONVERTED");
      setInterested((prev) => prev.map((l) => (l.id === lead.id ? { ...l, status: updated.status } : l)));
      toast(`${lead.business_name} marked as a client. Nice work!`, "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Update failed", "error");
    }
  };

  const yesToday = stats?.today_by_outcome.INTERESTED ?? 0;
  const lang3 = lang as ScriptLang;

  return (
    <section className="mt-8">
      {/* Today's numbers + caller settings */}
      <div className="flex flex-wrap items-end justify-between gap-6 border-b border-line pb-5">
        <div className="flex flex-wrap gap-8">
          <Stat label="Called today" value={stats?.called_today ?? 0} />
          <Stat label="Yes today" value={yesToday} accent={yesToday > 0} />
          <Stat label="In the queue" value={stats?.queue ?? queue.length} />
          <Stat label="Said yes, all time" value={stats?.interested_total ?? interested.length} />
        </div>
        <button
          type="button"
          onClick={() => setShowSettings((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-xs text-muted transition hover:border-ink hover:text-ink"
        >
          <Settings2 className="h-3.5 w-3.5" />
          {me ? `Calling as ${me}` : "Set your name"}
        </button>
      </div>

      {(showSettings || !me) && (
        <div className="rise mt-4 grid gap-3 rounded-2xl border border-line bg-card p-4 sm:grid-cols-2">
          <label className="text-xs text-muted">
            Your name (used in the script and WhatsApp follow-up)
            <input
              value={me}
              onChange={(e) => setMe(e.target.value)}
              placeholder="e.g. Vishwas"
              className="mt-1 h-9 w-full rounded-lg border border-line bg-paper px-3 text-sm text-ink outline-none focus:border-ink"
            />
          </label>
          <label className="text-xs text-muted">
            Portfolio or samples link (sent after a yes)
            <input
              value={portfolio}
              onChange={(e) => setPortfolio(e.target.value)}
              placeholder="https://…"
              className="mt-1 h-9 w-full rounded-lg border border-line bg-paper px-3 text-sm text-ink outline-none focus:border-ink"
            />
          </label>
        </div>
      )}

      {/* Queue / Said yes */}
      <div className="mt-5 flex gap-6 border-b border-line">
        {(
          [
            ["queue", "Up next", queue.length],
            ["yes", "Said yes", interested.length],
          ] as const
        ).map(([key, label, n]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 pb-2.5 text-sm transition ${
              tab === key ? "border-signal text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {label}
            <span className={`ml-1.5 font-mono text-[11px] ${tab === key ? "text-signal" : "text-faint"}`}>{n}</span>
          </button>
        ))}
      </div>

      {error && (
        <p className="mt-4 rounded-xl border border-bad/40 px-4 py-3 text-sm text-bad">{error}. Is the API running?</p>
      )}

      {justSaidYes && tab === "queue" && (
        <div className="rise mt-4 flex flex-col gap-3 rounded-2xl border border-ok/50 bg-ok/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink">
            <span className="font-semibold">{justSaidYes.business_name}</span> said yes. Send the follow-up while
            they remember you.
          </p>
          <FollowUpButton lead={justSaidYes} me={me} portfolio={portfolio} />
        </div>
      )}

      {tab === "queue" ? (
        <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)]">
          {/* Who's next */}
          <ol className="scroll-quiet min-w-0 space-y-0.5 lg:max-h-[75vh] lg:overflow-y-auto">
            {loading
              ? Array.from({ length: 6 }).map((_, i) => <li key={i} className="h-14 animate-pulse rounded-xl bg-sunk" />)
              : queue.map((l, i) => {
                  const meta = CATEGORY_META[l.category];
                  const active = l.id === currentId;
                  return (
                    <li key={l.id}>
                      <button
                        type="button"
                        onClick={() => setCurrentId(l.id)}
                        className={`relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition ${
                          active ? "bg-card shadow-sm ring-1 ring-line" : "hover:bg-card/60"
                        }`}
                      >
                        {active && <span className="absolute inset-y-2.5 left-0 w-[3px] rounded-full bg-signal" />}
                        <span className="w-5 shrink-0 text-right font-mono text-[11px] text-faint">{i + 1}</span>
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: meta.tone }} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm text-ink">{l.business_name}</span>
                          <span className="block text-xs text-muted">
                            {meta.label}
                            {l.call_outcome === "CALL_BACK" && <span className="text-signal"> · call back</span>}
                            {l.call_outcome === "NO_ANSWER" && <span> · try {l.call_attempts + 1}</span>}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
          </ol>

          {/* The call */}
          <div className="min-w-0">
            {!loading && !current ? (
              <div className="rounded-2xl border border-dashed border-line px-6 py-14 text-center">
                <p className="font-serif text-2xl italic">Nobody left to call right now.</p>
                <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
                  Run a scan in <em>businesses</em> to find more, or come back tomorrow for the ones who didn&apos;t pick
                  up.
                </p>
              </div>
            ) : current && script ? (
              <article key={current.id} className="rise rounded-2xl border border-line bg-card p-5 sm:p-7">
                <p className="text-xs text-muted">
                  <span className="font-semibold uppercase tracking-[0.14em]" style={{ color: CATEGORY_META[current.category].tone }}>
                    {CATEGORY_META[current.category].label}
                  </span>{" "}
                  · {CATEGORY_META[current.category].problem} · {displayCity(current.city)}
                </p>
                <h2 className="mt-2 font-serif text-[1.9rem] leading-[1.1] tracking-tight sm:text-4xl">
                  {current.business_name}
                </h2>

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <a
                    href={telHref(current.phone_number)}
                    className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-2.5 font-mono text-lg tracking-wide text-paper transition hover:brightness-125"
                  >
                    <Phone className="h-4 w-4" />
                    {formatPhone(current.phone_number)}
                  </a>
                  {isLandline(current.phone_number) && <span className="text-xs text-muted">landline: no WhatsApp</span>}
                  {current.website_url && (
                    <a
                      href={current.website_url}
                      target="_blank"
                      rel="noreferrer"
                      className="max-w-[16rem] truncate text-sm text-muted underline decoration-line underline-offset-4 hover:text-ink"
                    >
                      {current.website_url.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                    </a>
                  )}
                </div>
                {current.last_called_at && (
                  <p className="mt-2 text-xs text-muted" suppressHydrationWarning>
                    Called {current.call_attempts}× · last {timeAgo(current.last_called_at)}
                  </p>
                )}

                {/* Script */}
                <div className="mt-6 flex items-center justify-between gap-3">
                  <h3 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">What to say</h3>
                  <div className="flex rounded-full border border-line p-0.5 text-xs">
                    {LANGS.map((l) => (
                      <button
                        key={l.key}
                        type="button"
                        onClick={() => setLang(l.key)}
                        className={`rounded-full px-2.5 py-1 transition ${
                          lang3 === l.key ? "bg-ink text-paper" : "text-muted hover:text-ink"
                        }`}
                      >
                        {l.label}
                      </button>
                    ))}
                  </div>
                </div>
                <ol className="mt-3 space-y-3">
                  {(
                    [
                      ["Open", script.open],
                      ["Why you're calling", script.point],
                      ["The one question", script.ask],
                    ] as const
                  ).map(([label, l], i) => (
                    <li key={label} className={`rounded-xl p-3.5 ${i === 2 ? "bg-signal/10 ring-1 ring-signal/30" : "bg-sunk"}`}>
                      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
                        {i + 1} · {label}
                      </div>
                      <p className={`mt-1 leading-relaxed text-ink ${lang3 === "kn" ? "text-xl" : "text-[17px]"}`}>{l[lang3]}</p>
                      {lang3 !== "en" && <p className="mt-1 text-xs text-faint">{l.en}</p>}
                    </li>
                  ))}
                </ol>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  {(
                    [
                      ["If yes", script.ifYes],
                      ["If busy", script.ifBusy],
                      ["If no", script.ifNo],
                    ] as const
                  ).map(([label, l]) => (
                    <div key={label} className="rounded-xl border border-line p-3">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">{label}</div>
                      <p className={`mt-1 leading-snug text-ink ${lang3 === "kn" ? "text-base" : "text-sm"}`}>{l[lang3]}</p>
                    </div>
                  ))}
                </div>

                {/* Outcome */}
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  placeholder="Notes (optional): who you spoke to, what they said…"
                  className="mt-6 w-full resize-y rounded-xl border border-line bg-paper px-3 py-2 text-sm outline-none placeholder:text-faint focus:border-ink"
                />
                {pickingCallback ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="mr-1 text-xs text-faint">Call back:</span>
                    {CALL_BACK_OPTIONS.map((o) => (
                      <button
                        key={o.label}
                        type="button"
                        disabled={busy}
                        onClick={() => record("CALL_BACK", o.hours)}
                        className="rounded-full border border-line px-3 py-1.5 text-sm text-ink transition hover:border-ink disabled:opacity-50"
                      >
                        {o.label}
                      </button>
                    ))}
                    <button type="button" onClick={() => setPickingCallback(false)} className="text-xs text-muted underline">
                      cancel
                    </button>
                  </div>
                ) : (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {OUTCOMES.map((o) => (
                      <button
                        key={o.key}
                        type="button"
                        disabled={busy}
                        onClick={() => record(o.key)}
                        className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition disabled:opacity-50 ${o.tone}`}
                      >
                        {o.label}
                        <kbd className="font-mono text-[10px] opacity-70">{o.hotkey}</kbd>
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ) : (
              <div className="h-96 animate-pulse rounded-2xl bg-sunk" />
            )}
          </div>
        </div>
      ) : (
        /* People who said yes: your human follow-up list */
        <div className="mt-5">
          {interested.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-line px-6 py-14 text-center">
              <p className="font-serif text-2xl italic">No yeses yet.</p>
              <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
                Expect about one in a hundred. Everyone who says yes lands here for you to follow up.
              </p>
            </div>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {interested.map((l) => (
                <li key={l.id} className="flex flex-col rounded-2xl border border-line bg-card p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-serif text-xl leading-tight">{l.business_name}</h3>
                    {l.status === "CONVERTED" && (
                      <span className="shrink-0 rounded-full bg-ok/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ok">
                        client
                      </span>
                    )}
                  </div>
                  <a href={telHref(l.phone_number)} className="mt-1 font-mono text-sm text-muted hover:text-ink">
                    {formatPhone(l.phone_number)}
                  </a>
                  <p className="mt-1 text-xs text-faint" suppressHydrationWarning>
                    said yes {timeAgo(l.last_called_at)} · {CATEGORY_META[l.category].pitch}
                  </p>
                  {l.call_notes && <p className="mt-2 text-sm italic text-muted">“{l.call_notes}”</p>}
                  <div className="mt-auto flex flex-wrap gap-2 pt-3">
                    <FollowUpButton lead={l} me={me} portfolio={portfolio} />
                    {l.status !== "CONVERTED" && (
                      <button
                        type="button"
                        onClick={() => markConverted(l)}
                        className="rounded-full border border-line px-3 py-1.5 text-xs text-ink transition hover:border-ok hover:text-ok"
                      >
                        Became a client
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="mt-6 text-[11px] text-faint">
        The number opens your phone app (on a PC, Phone Link if it&apos;s set up), or dial it from your mobile. Keys:{" "}
        <kbd className="font-mono">Y</kbd> interested · <kbd className="font-mono">B</kbd> call back ·{" "}
        <kbd className="font-mono">A</kbd> no answer · <kbd className="font-mono">N</kbd> not interested ·{" "}
        <kbd className="font-mono">W</kbd> wrong number.
      </p>
    </section>
  );
}

function FollowUpButton({ lead, me, portfolio }: { lead: Lead; me: string; portfolio: string }) {
  const link = buildFollowUpLink(lead, me, portfolio);
  if (!link) {
    return <span className="self-center text-xs text-muted">Landline: ask for their WhatsApp number</span>;
  }
  return (
    <a
      href={link}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-full bg-ok px-3.5 py-1.5 text-xs font-semibold text-white transition hover:brightness-110"
    >
      <MessageCircle className="h-3.5 w-3.5" />
      WhatsApp follow-up (ಕನ್ನಡ)
    </a>
  );
}
