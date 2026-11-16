"use client";

import { RefreshCw } from "lucide-react";
import { IntentSource, IntentSourceKey, IntentStats } from "@/lib/types";
import { SOURCE_META } from "@/lib/intent";
import { everyLabel, timeAgo } from "@/lib/format";

interface SourcesDeskProps {
  sources: IntentSource[];
  stats: IntentStats | null;
  onPoll: (key: IntentSourceKey) => void;
}

const STATE: Record<string, { label: string; dot: string }> = {
  ok: { label: "Listening", dot: "bg-ok breathe" },
  error: { label: "Failing", dot: "bg-bad" },
  backing_off: { label: "Cooling off", dot: "bg-warn" },
  not_configured: { label: "Needs setup", dot: "bg-faint" },
  waiting: { label: "Waiting for first run", dot: "bg-faint" },
};

function stateOf(s: IntentSource): keyof typeof STATE {
  if (!s.configured) return "not_configured";
  if (s.backoff_s > 0) return "backing_off";
  return (s.state as keyof typeof STATE) ?? "waiting";
}

const SCORE_RULES: [string, string][] = [
  ["Asks for a site, fix or automation", "up to +45"],
  ["Posted on a job board / tagged [Hiring]", "+10"],
  ["Budget stated (bigger is better)", "−10 … +20"],
  ["Posted in the last 2 / 12 / 48 h", "+15 / +10 / +5"],
  ["In India, or priced in ₹", "+10"],
  ["“My shop / clinic / salon…”", "+8"],
  ["Few bids / crowded", "+5 / −10"],
  ["Off-target (apps, crypto, sales gigs…)", "−30 each"],
];

export function SourcesDesk({ sources, stats, onPoll }: SourcesDeskProps) {
  return (
    <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,8fr)_minmax(0,4fr)]">
      <div className="grid gap-4 sm:grid-cols-2">
        {sources.length === 0 && (
          <p className="rounded-2xl border border-dashed border-line px-6 py-10 text-center text-sm text-muted sm:col-span-2">
            Couldn&apos;t load sources. Is the API running?
          </p>
        )}
        {sources.map((s) => {
          const st = STATE[stateOf(s)];
          const found = stats?.by_source[s.key] ?? 0;
          return (
            <article key={s.key} className="flex flex-col rounded-2xl border border-line bg-card p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-full bg-ink font-mono text-xs text-paper">
                    {SOURCE_META[s.key].mark}
                  </span>
                  <div>
                    <h3 className="font-serif text-2xl leading-none">{s.label}</h3>
                    <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-muted">
                      <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
                      {st.label}
                      {s.backoff_s > 0 && <> · {Math.ceil(s.backoff_s / 60)} min left</>}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onPoll(s.key)}
                  disabled={!s.configured || s.poll_requested}
                  className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-xs text-ink transition hover:border-ink disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <RefreshCw className={`h-3 w-3 ${s.poll_requested ? "animate-spin" : ""}`} />
                  {s.poll_requested ? "Queued" : "Check now"}
                </button>
              </div>

              <dl className="mt-5 grid grid-cols-3 gap-3 border-y border-line py-3">
                <div>
                  <dt className="text-[10px] uppercase tracking-[0.14em] text-faint">Kept</dt>
                  <dd className="font-serif text-2xl tabular-nums">{found}</dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-[0.14em] text-faint">Last pass</dt>
                  <dd className="font-serif text-2xl tabular-nums">
                    {s.last_new ?? "–"}
                    <span className="text-sm text-faint">/{s.last_fetched ?? "–"}</span>
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-[0.14em] text-faint">Checked</dt>
                  <dd className="mt-1.5 text-sm" suppressHydrationWarning>
                    {timeAgo(s.last_attempt_at)}
                  </dd>
                </div>
              </dl>

              <p className="mt-3 text-xs text-muted">
                {everyLabel(s.interval_s)} · last pass kept <em>new</em> / <em>seen</em>
              </p>
              {s.last_error && (
                <p className="mt-2 break-words rounded-lg bg-bad/10 px-3 py-2 font-mono text-[11px] text-bad">
                  {s.last_error}
                </p>
              )}
              <p className={`mt-auto pt-3 text-xs ${s.configured ? "text-faint" : "text-ink"}`}>{s.setup_hint}</p>
            </article>
          );
        })}
      </div>

      <aside className="space-y-4">
        <div className="rounded-2xl border border-line bg-card p-5">
          <h3 className="font-serif text-2xl">How a request is scored</h3>
          <p className="mt-1 text-sm text-muted">Out of 100. Below 20 is dropped; 70+ counts as hot.</p>
          <ul className="mt-4 divide-y divide-line text-sm">
            {SCORE_RULES.map(([rule, pts]) => (
              <li key={rule} className="flex items-baseline justify-between gap-3 py-2">
                <span className="text-muted">{rule}</span>
                <span className="shrink-0 font-mono text-xs text-ink">{pts}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-line bg-sunk p-5 text-sm text-muted">
          <h3 className="font-serif text-xl text-ink">Be first to reply</h3>
          <p className="mt-2">
            Good posts get dozens of replies within the hour. Set <code className="font-mono text-xs">TELEGRAM_BOT_TOKEN</code>{" "}
            and <code className="font-mono text-xs">TELEGRAM_CHAT_ID</code> to get a phone ping for every hot request.
          </p>
          <p className="mt-2">
            With Ollama running, hot requests also get a one-line summary and a reply written for that post.
          </p>
        </div>
      </aside>
    </section>
  );
}
