"use client";

import { X } from "lucide-react";
import { Toast, ToastVariant } from "@/lib/useToast";

const DOT: Record<ToastVariant, string> = {
  success: "bg-ok",
  error: "bg-bad",
  info: "bg-signal",
};

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (!toasts.length) return null;
  return (
    <div
      aria-live="polite"
      className="fixed inset-x-0 bottom-5 z-50 mx-auto flex w-[min(30rem,calc(100vw-2rem))] flex-col gap-2"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="alert"
          className="rise flex items-start gap-3 rounded-xl bg-ink px-4 py-3 text-sm text-paper shadow-xl"
        >
          <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${DOT[t.variant]}`} />
          <span className="flex-1 leading-snug">{t.message}</span>
          <button
            type="button"
            onClick={() => onDismiss(t.id)}
            className="opacity-50 transition-opacity hover:opacity-100"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
