export type FilterTab =
  | "ALL"
  | "DIGITAL_GHOST"
  | "DIGITAL_DINOSAUR"
  | "LAGGY_UX"
  | "AUTOMATION_CANDIDATE"
  | "OPTED_OUT";

const TABS: { key: FilterTab; label: string }[] = [
  { key: "ALL", label: "All" },
  { key: "DIGITAL_GHOST", label: "Digital Ghost" },
  { key: "DIGITAL_DINOSAUR", label: "Digital Dinosaur" },
  { key: "LAGGY_UX", label: "Laggy UX" },
  { key: "AUTOMATION_CANDIDATE", label: "Automation Candidate" },
  { key: "OPTED_OUT", label: "Opted Out" },
];

interface FilterTabsProps {
  active: FilterTab;
  onChange: (tab: FilterTab) => void;
  counts: Record<FilterTab, number>;
}

export function FilterTabs({ active, onChange, counts }: FilterTabsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {TABS.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            type="button"
            suppressHydrationWarning
            onClick={() => onChange(tab.key)}
            className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
              isActive
                ? "bg-gray-900 text-white"
                : "bg-white text-gray-600 ring-1 ring-inset ring-gray-200 hover:bg-gray-50"
            }`}
          >
            {tab.label}
            <span className={`ml-1.5 ${isActive ? "text-gray-300" : "text-gray-400"}`}>
              {counts[tab.key] ?? 0}
            </span>
          </button>
        );
      })}
    </div>
  );
}
