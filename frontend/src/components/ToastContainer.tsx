"use client";

import { X, CheckCircle, XCircle, Info } from "lucide-react";
import { Toast, ToastVariant } from "@/lib/useToast";

const VARIANT_STYLES: Record<
  ToastVariant,
  { wrapper: string; icon: React.ElementType; iconClass: string }
> = {
  success: {
    wrapper: "bg-emerald-50 border-emerald-200 text-emerald-800",
    icon: CheckCircle,
    iconClass: "text-emerald-500",
  },
  error: {
    wrapper: "bg-red-50 border-red-200 text-red-800",
    icon: XCircle,
    iconClass: "text-red-500",
  },
  info: {
    wrapper: "bg-blue-50 border-blue-200 text-blue-800",
    icon: Info,
    iconClass: "text-blue-500",
  },
};

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: number) => void;
}

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const { wrapper, icon: Icon, iconClass } = VARIANT_STYLES[toast.variant];
  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 shadow-lg text-sm font-medium transition-all ${wrapper}`}
    >
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconClass}`} />
      <span className="flex-1">{toast.message}</span>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        className="ml-2 opacity-50 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (!toasts.length) return null;
  return (
    <div
      aria-live="polite"
      className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
