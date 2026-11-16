"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, Check, Copy, X } from "lucide-react";
import { IntentPost, IntentStatus } from "@/lib/types";
import { FIT_META, SOURCE_META, STATUS_META, STATUS_ORDER, askedAt } from "@/lib/intent";
import { budgetLabel, timeAgo } from "@/lib/format";
import { ScoreMark } from "./ScoreMark";

interface RequestReaderProps {
  post: IntentPost;
  reply: string;
  onReplyChange: (text: string) => void;
  onStatus: (status: IntentStatus) => void;
  onCopyAndOpen: () => void;
  onCopy: () => void;
  onClose?: () => void;
  busy: boolean;
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">{label}</dt>
      <dd className="mt-1 truncate text-sm text-ink">{children}</dd>
    </div>
  );
}

const BODY_PREVIEW = 900;

export function RequestReader({
  post,
  reply,
  onReplyChange,
  onStatus,
  onCopyAndOpen,
  onCopy,
  onClose,
  busy,
}: RequestReaderProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setExpanded(false);
    setCopied(false);
  }, [post.id]);

  const fit = FIT_META[post.fit];
  const budget = budgetLabel(post);
  const longBody = post.body.length > BODY_PREVIEW;
  const body = expanded || !longBody ? post.body : `${post.body.slice(0, BODY_PREVIEW).trimEnd()}…`;

  const copy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <article key={post.id} className="rise rounded-2xl border border-line bg-card p-5 shadow-sm sm:p-7">
      {/* Kicker */}
      <div className="flex items-start justify-between gap-4">
        <p className="text-xs text-muted">
          <span className="font-semibold uppercase tracking-[0.14em] text-ink">{SOURCE_META[post.source].label}</span>
          {post.channel && <> · {post.channel}</>}
          <span suppressHydrationWarning> · asked {timeAgo(askedAt(post))}</span>
          {post.author && <> · by {post.author}</>}
        </p>
        <div className="flex items-center gap-2">
          <ScoreMark score={post.score} size={52} />
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="grid h-8 w-8 place-items-center rounded-full border border-line text-muted"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <h2 className="mt-3 font-serif text-[1.9rem] leading-[1.1] tracking-tight sm:text-4xl">{post.title}</h2>

      <dl className="mt-5 grid grid-cols-2 gap-4 border-y border-line py-4 sm:grid-cols-4">
        <Fact label="They need">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: fit.tone }} />
            {fit.label}
          </span>
        </Fact>
        <Fact label="Budget">{budget ?? <span className="text-faint">not stated</span>}</Fact>
        <Fact label="Competition">
          {post.bid_count !== null ? `${post.bid_count} bids` : <span className="text-faint">unknown</span>}
        </Fact>
        <Fact label="Where">{post.is_local ? "India" : <span className="text-faint">anywhere</span>}</Fact>
      </dl>

      {post.signals.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-1.5">
          {post.signals.map((s) => (
            <li
              key={s}
              className={`rounded-full border px-2.5 py-0.5 text-xs ${
                s.startsWith("off-target") || s === "tiny budget"
                  ? "border-bad/40 text-bad"
                  : "border-line text-muted"
              }`}
            >
              {s}
            </li>
          ))}
        </ul>
      )}

      {post.summary && (
        <p className="mt-5 font-serif text-xl italic leading-snug text-ink">
          <span className="not-italic text-signal">“</span>
          {post.summary}
          <span className="not-italic text-signal">”</span>
        </p>
      )}

      {/* Their words */}
      {post.body && (
        <section className="mt-5">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">In their words</h3>
          <p className="mt-2 whitespace-pre-wrap break-words text-[15px] leading-relaxed text-muted">{body}</p>
          {longBody && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-2 text-sm font-medium text-ink underline decoration-line underline-offset-4 hover:decoration-signal"
            >
              {expanded ? "Show less" : "Read all of it"}
            </button>
          )}
        </section>
      )}

      {/* Reply */}
      <section className="mt-6 rounded-xl bg-sunk p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">Your first message</h3>
          <span className="text-[11px] text-faint">edit freely · C copies</span>
        </div>
        <textarea
          value={reply}
          onChange={(e) => onReplyChange(e.target.value)}
          rows={5}
          className="mt-2 w-full resize-y bg-transparent text-[15px] leading-relaxed text-ink outline-none"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onCopyAndOpen}
            className="inline-flex items-center gap-1.5 rounded-full bg-signal px-4 py-2 text-sm font-semibold text-signal-ink transition hover:brightness-110"
          >
            Copy &amp; open post <ArrowUpRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={copy}
            className="inline-flex items-center gap-1.5 rounded-full border border-line bg-card px-4 py-2 text-sm text-ink transition hover:border-ink"
          >
            {copied ? <Check className="h-4 w-4 text-ok" /> : <Copy className="h-4 w-4" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </section>

      {/* File it */}
      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="mr-1 text-xs text-faint">File it:</span>
        {STATUS_ORDER.filter((s) => s !== post.status).map((s) => (
          <button
            key={s}
            type="button"
            disabled={busy}
            onClick={() => onStatus(s)}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition disabled:opacity-50 ${
              s === "DISMISSED"
                ? "border-line text-muted hover:border-bad hover:text-bad"
                : s === "WON"
                  ? "border-line text-muted hover:border-ok hover:text-ok"
                  : "border-line text-ink hover:border-ink"
            }`}
          >
            {STATUS_META[s].verb}
            <kbd className="font-mono text-[10px] text-faint">{STATUS_META[s].key}</kbd>
          </button>
        ))}
      </div>
    </article>
  );
}
