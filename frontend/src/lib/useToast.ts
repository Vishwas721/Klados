"use client";

import { useCallback, useReducer, useRef } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
export type ToastVariant = "success" | "error" | "info";

export interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

type Action =
  | { type: "ADD"; toast: Toast }
  | { type: "REMOVE"; id: number };

function reducer(state: Toast[], action: Action): Toast[] {
  if (action.type === "ADD") return [...state, action.toast];
  if (action.type === "REMOVE") return state.filter((t) => t.id !== action.id);
  return state;
}

// ── Hook ──────────────────────────────────────────────────────────────────────
export function useToast() {
  const [toasts, dispatch] = useReducer(reducer, []);
  const idRef = useRef(0);

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info", durationMs = 4000) => {
      const id = ++idRef.current;
      dispatch({ type: "ADD", toast: { id, message, variant } });
      setTimeout(() => dispatch({ type: "REMOVE", id }), durationMs);
    },
    []
  );

  const dismiss = useCallback((id: number) => {
    dispatch({ type: "REMOVE", id });
  }, []);

  return { toasts, toast, dismiss };
}
