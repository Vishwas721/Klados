import { IntentPost } from "@/lib/types";
import { FIT_META, SOURCE_META, askedAt } from "@/lib/intent";
import { budgetLabel, timeAgo } from "@/lib/format";
import { ScoreMark } from "./ScoreMark";

interface RequestCardProps {
  post: IntentPost;
  selected: boolean;
  onSelect: () => void;
}

export function RequestCard({ post, selected, onSelect }: RequestCardProps) {
  const fit = FIT_META[post.fit];
  const budget = budgetLabel(post);
  return (
    <button
      type="button"
      onClick={onSelect}
      data-post-id={post.id}
      aria-current={selected ? "true" : undefined}
      className={`group relative flex w-full gap-3.5 rounded-xl px-3 py-3 text-left transition ${
        selected ? "bg-card shadow-sm ring-1 ring-line" : "hover:bg-card/60"
      }`}
    >
      {selected && <span className="absolute inset-y-3 left-0 w-[3px] rounded-full bg-signal" />}
      <ScoreMark score={post.score} />
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 text-[15px] font-medium leading-snug text-ink">{post.title}</span>
        <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: fit.tone }} />
            {fit.short}
          </span>
          <span className="text-faint">·</span>
          <span className="font-mono text-[10px] tracking-wide text-faint">{SOURCE_META[post.source].mark}</span>
          {post.channel && <span className="max-w-[9rem] truncate">{post.channel}</span>}
          <span className="text-faint">·</span>
          <span suppressHydrationWarning>{timeAgo(askedAt(post))}</span>
          {budget && (
            <>
              <span className="text-faint">·</span>
              <span className="font-medium text-ink">{budget}</span>
            </>
          )}
          {post.is_local && (
            <span className="rounded-full border border-line px-1.5 text-[10px] uppercase tracking-wide">IN</span>
          )}
        </span>
      </span>
    </button>
  );
}
