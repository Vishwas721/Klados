import { Bot, Ghost, Skull, Turtle, Users } from "lucide-react";
import { Lead } from "@/lib/types";

export function MetricCards({ leads }: { leads: Lead[] }) {
  const counts = {
    total: leads.length,
    DIGITAL_GHOST: leads.filter((l) => l.category === "DIGITAL_GHOST").length,
    DIGITAL_DINOSAUR: leads.filter((l) => l.category === "DIGITAL_DINOSAUR").length,
    LAGGY_UX: leads.filter((l) => l.category === "LAGGY_UX").length,
    AUTOMATION_CANDIDATE: leads.filter((l) => l.category === "AUTOMATION_CANDIDATE").length,
  };

  const cards = [
    { label: "Total Extracted", value: counts.total, icon: Users, accent: "text-slate-900", bg: "bg-slate-50" },
    { label: "Digital Ghosts", value: counts.DIGITAL_GHOST, icon: Ghost, accent: "text-slate-600", bg: "bg-slate-100" },
    { label: "Digital Dinosaurs", value: counts.DIGITAL_DINOSAUR, icon: Skull, accent: "text-amber-600", bg: "bg-amber-50" },
    { label: "Laggy UX", value: counts.LAGGY_UX, icon: Turtle, accent: "text-red-600", bg: "bg-red-50" },
    { label: "Automation Candidates", value: counts.AUTOMATION_CANDIDATE, icon: Bot, accent: "text-emerald-600", bg: "bg-emerald-50" },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map(({ label, value, icon: Icon, accent, bg }) => (
        <div key={label} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-500">{label}</span>
            <span className={`rounded-lg p-1.5 ${bg}`}>
              <Icon className={`h-4 w-4 ${accent}`} />
            </span>
          </div>
          <p className="mt-2 text-2xl font-semibold text-gray-900">{value}</p>
        </div>
      ))}
    </div>
  );
}
