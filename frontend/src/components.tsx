import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2, Loader2, X } from "lucide-react";
import { title } from "./api";
export function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${value.toLowerCase().replaceAll("_", "-")}`}>
      {title(value)}
    </span>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      role={error ? "alert" : "status"}
      className={`notice ${error ? "error" : ""}`}
    >
      {error ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
      <div>{children}</div>
    </div>
  );
}
export function Loading() {
  return (
    <div role="status" className="loading">
      <Loader2 className="spin" size={20} /> Loading workspace…
    </div>
  );
}
export function Empty({
  title: heading,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark">↗</div>
      <h3>{heading}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog ref={ref} className="modal" aria-label={title} onCancel={onClose}>
      <div className="modal-head">
        <h2>{title}</h2>
        <button
          aria-label="Close dialog"
          className="icon-button"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Heading({
  eyebrow,
  title: heading,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{heading}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      <div className="heading-actions">{actions}</div>
    </div>
  );
}
