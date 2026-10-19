import { LeadCategory } from "./types";

export const CATEGORY_ORDER: LeadCategory[] = [
  "DIGITAL_GHOST",
  "DIGITAL_DINOSAUR",
  "LAGGY_UX",
  "AUTOMATION_CANDIDATE",
];

export const CATEGORY_LABELS: Record<LeadCategory, string> = {
  DIGITAL_GHOST: "Digital Ghost",
  DIGITAL_DINOSAUR: "Digital Dinosaur",
  LAGGY_UX: "Laggy UX",
  AUTOMATION_CANDIDATE: "Automation Candidate",
};

export const CATEGORY_BADGE_STYLES: Record<LeadCategory, string> = {
  DIGITAL_GHOST: "bg-slate-100 text-slate-700 ring-slate-600/20",
  DIGITAL_DINOSAUR: "bg-amber-100 text-amber-800 ring-amber-600/20",
  LAGGY_UX: "bg-red-100 text-red-700 ring-red-600/20",
  AUTOMATION_CANDIDATE: "bg-emerald-100 text-emerald-700 ring-emerald-600/20",
};
