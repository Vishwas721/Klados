import { LeadCategory } from "@/lib/types";
import { CATEGORY_BADGE_STYLES, CATEGORY_LABELS } from "@/lib/categories";

export function CategoryBadge({ category }: { category: LeadCategory }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${
        CATEGORY_BADGE_STYLES[category] ?? "bg-gray-100 text-gray-700 ring-gray-600/20"
      }`}
    >
      {CATEGORY_LABELS[category] ?? category}
    </span>
  );
}
