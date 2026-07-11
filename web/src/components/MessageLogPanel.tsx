"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, ExternalLink, Send } from "lucide-react";
import clsx from "clsx";
import { MessageLog } from "@/lib/api";
import { JobFieldsPanel } from "@/components/JobFieldsPanel";

const PAGE_SIZE = 15;

function directionBadge(direction: string) {
  const styles: Record<string, string> = {
    draft: "bg-blue-50 text-blue-700 ring-blue-600/20",
    outbound: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    ignored: "bg-slate-100 text-slate-600 ring-slate-500/10",
    monitored: "bg-amber-50 text-amber-700 ring-amber-600/20",
    discarded: "bg-slate-100 text-slate-500 ring-slate-500/10",
    reminder: "bg-purple-50 text-purple-700 ring-purple-600/20",
    followup: "bg-orange-50 text-orange-700 ring-orange-600/20",
    extracted: "bg-teal-50 text-teal-700 ring-teal-600/20",
    needs_human: "bg-rose-50 text-rose-700 ring-rose-600/20",
  };
  return styles[direction] || "bg-slate-100 text-slate-600 ring-slate-500/10";
}

function directionLabel(direction: string) {
  if (direction === "ignored") return "skipped";
  if (direction === "outbound") return "sent";
  if (direction === "monitored") return "logged";
  if (direction === "extracted") return "extracted";
  if (direction === "needs_human") return "needs human";
  return direction;
}

function statusMeta(log: MessageLog) {
  if (log.direction === "outbound") return { label: "Sent", className: "text-emerald-600" };
  if (log.direction === "ignored") return { label: "Skipped", className: "text-slate-500" };
  if (log.direction === "monitored") return { label: "Monitor only", className: "text-amber-600" };
  if (log.direction === "discarded") return { label: "Deleted", className: "text-slate-500" };
  if (log.direction === "draft") return { label: "Draft", className: "text-blue-600" };
  if (log.direction === "extracted") return { label: "Booked job", className: "text-teal-700" };
  if (log.direction === "needs_human") return { label: "Needs you", className: "text-rose-700" };
  return { label: log.direction, className: "text-slate-500" };
}

function replySectionTitle(direction: string) {
  if (direction === "ignored") return "Why skipped";
  if (direction === "monitored") return "Note";
  if (direction === "outbound") return "Sent reply";
  if (direction === "draft") return "Draft reply";
  if (direction === "extracted") return "Note";
  if (direction === "needs_human") return "Why flagged";
  return "Reply";
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toISOString().replace("T", " ").slice(0, 16);
  } catch {
    return iso;
  }
}

type Props = {
  logs: MessageLog[];
  onSend: (logId: number) => Promise<void>;
  sendingId: number | null;
};

export function MessageLogPanel({ logs, onSend, sendingId }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [mounted, setMounted] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setMounted(true);
  }, []);

  const visibleLogs = useMemo(
    () => logs.filter((log) => log.direction !== "discarded"),
    [logs]
  );

  const totalPages = Math.max(1, Math.ceil(visibleLogs.length / PAGE_SIZE));

  useEffect(() => {
    setPage(1);
  }, [logs]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const pageLogs = visibleLogs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (visibleLogs.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-surface-border bg-white px-4 py-10 text-center text-sm text-slate-500">
        No messages yet. Connect Gmail in Settings, then check the inbox.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {pageLogs.map((log) => {
        const open = expanded === log.id;
        const status = statusMeta(log);
        const isSkipped = log.direction === "ignored" || log.direction === "monitored";
        const showJobFields =
          !!log.extraction_json &&
          (log.direction === "extracted" ||
            log.direction === "draft" ||
            log.direction === "outbound");
        return (
          <div
            key={log.id}
            className={clsx(
              "overflow-hidden rounded-lg border border-surface-border bg-white",
              isSkipped && "bg-slate-50/90",
              log.direction === "needs_human" && "border-rose-200 bg-rose-50/30",
              log.direction === "extracted" && "border-teal-200 bg-teal-50/20"
            )}
          >
            <button
              type="button"
              onClick={() => setExpanded(open ? null : log.id)}
              className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left hover:bg-slate-50/80"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span
                    className={clsx(
                      "rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
                      directionBadge(log.direction)
                    )}
                  >
                    {directionLabel(log.direction)}
                  </span>
                  <span className={clsx("text-[11px] font-medium", status.className)}>{status.label}</span>
                  {log.quote_amount && log.direction === "draft" && (
                    <span className="text-[11px] font-semibold text-brand-700">{log.quote_amount}</span>
                  )}
                  <span className="text-[11px] text-slate-400" suppressHydrationWarning>
                    {mounted ? formatTime(log.created_at) : "—"}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-sm font-medium text-slate-900">
                  {log.subject || "No subject"}
                </p>
              </div>
              {open ? (
                <ChevronUp className="h-4 w-4 flex-shrink-0 text-slate-400" />
              ) : (
                <ChevronDown className="h-4 w-4 flex-shrink-0 text-slate-400" />
              )}
            </button>

            {open && (
              <div className="border-t border-surface-border bg-slate-50/40 px-3.5 py-3">
                <div className="grid gap-3 lg:grid-cols-2">
                  <div>
                    <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Customer email
                    </h4>
                    <pre className="max-h-36 overflow-auto rounded-md border border-surface-border bg-white p-2.5 text-xs text-slate-700 whitespace-pre-wrap">
                      {log.inbound_body || "Original email not stored for this entry."}
                    </pre>
                  </div>
                  <div>
                    {showJobFields ? (
                      <JobFieldsPanel
                        extractionJson={log.extraction_json}
                        summaryFallback={log.summary}
                      />
                    ) : (
                      <>
                        <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                          Status
                        </h4>
                        <div
                          className={clsx(
                            "rounded-md border p-2.5 text-xs",
                            isSkipped
                              ? "border-slate-200 bg-slate-100 text-slate-600"
                              : log.direction === "needs_human"
                                ? "border-rose-200 bg-rose-50 text-rose-900"
                                : "border-brand-200 bg-brand-50/50 text-slate-800"
                          )}
                        >
                          {log.direction === "ignored"
                            ? "Not extracted — skipped (not a moving inquiry)."
                            : log.direction === "monitored"
                              ? "AI is off — email was logged only."
                              : log.direction === "needs_human"
                                ? "Flagged for human — left unread in Gmail."
                                : log.summary || "No AI summary available."}
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {log.reply_body && (
                  <div className="mt-3">
                    <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      {replySectionTitle(log.direction)}
                    </h4>
                    <pre
                      className={clsx(
                        "max-h-40 overflow-auto rounded-md border p-2.5 text-xs whitespace-pre-wrap",
                        isSkipped ||
                          log.direction === "extracted" ||
                          log.direction === "needs_human"
                          ? "border-slate-200 bg-slate-100 text-slate-600"
                          : "border-surface-border bg-white text-slate-700"
                      )}
                    >
                      {log.reply_body}
                    </pre>
                  </div>
                )}

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {log.can_send && log.direction === "draft" && (
                    <button
                      type="button"
                      onClick={() => onSend(log.id)}
                      disabled={sendingId === log.id}
                      className="btn-primary !px-3 !py-1.5 text-xs"
                    >
                      <Send className="h-3.5 w-3.5" />
                      {sendingId === log.id ? "Sending…" : "Send reply"}
                    </button>
                  )}
                  {log.gmail_thread_id && (
                    <a
                      href={`https://mail.google.com/mail/u/0/#inbox/${log.gmail_thread_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-secondary !px-3 !py-1.5 text-xs"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      Gmail
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {totalPages > 1 && (
        <div className="flex items-center justify-between gap-3 pt-2">
          <p className="text-xs text-slate-500">
            {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, visibleLogs.length)} of{" "}
            {visibleLogs.length}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-secondary !px-2.5 !py-1.5 text-xs"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <span className="text-xs font-medium text-slate-600">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              className="btn-secondary !px-2.5 !py-1.5 text-xs"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
