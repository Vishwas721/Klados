import { LeadCategory } from "./types";

export const CATEGORY_ORDER: LeadCategory[] = [
  "DIGITAL_GHOST",
  "DIGITAL_DINOSAUR",
  "LAGGY_UX",
  "AUTOMATION_CANDIDATE",
];

export const CATEGORY_META: Record<
  LeadCategory,
  { label: string; problem: string; pitch: string; tone: string }
> = {
  DIGITAL_GHOST: {
    label: "Digital Ghost",
    problem: "No website, or it doesn't load",
    pitch: "Build them a site",
    tone: "var(--c-ghost)",
  },
  DIGITAL_DINOSAUR: {
    label: "Digital Dinosaur",
    problem: "No HTTPS or not mobile-friendly",
    pitch: "Modernize it",
    tone: "var(--c-dino)",
  },
  LAGGY_UX: {
    label: "Laggy",
    problem: "Slow to respond or load",
    pitch: "Speed it up",
    tone: "var(--c-lag)",
  },
  AUTOMATION_CANDIDATE: {
    label: "Automation",
    problem: "Healthy site, manual operations",
    pitch: "Add booking or chat",
    tone: "var(--c-auto)",
  },
};
