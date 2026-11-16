import { heat } from "@/lib/intent";

const STROKE = { hot: "var(--signal)", warm: "var(--ink)", cool: "var(--faint)" };

/** Score as a numeral inside a ring that fills with the score. */
export function ScoreMark({ score, size = 44 }: { score: number; size?: number }) {
  const h = heat(score);
  const r = size / 2 - 3;
  const c = 2 * Math.PI * r;
  return (
    <span
      className="relative inline-grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
      title={`Score ${score}/100`}
    >
      <svg width={size} height={size} className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={2} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={STROKE[h]}
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * c} ${c}`}
        />
      </svg>
      <span
        className={`font-serif leading-none tabular-nums ${h === "hot" ? "text-signal" : h === "warm" ? "text-ink" : "text-faint"}`}
        style={{ fontSize: size * 0.42 }}
      >
        {score}
      </span>
    </span>
  );
}
