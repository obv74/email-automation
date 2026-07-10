"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, Send } from "lucide-react";
import clsx from "clsx";
import { MessageLog } from "@/lib/api";

function directionBadge(direction: string) {
  const styles: Record<string, string> = {
    draft: "bg-blue-50 text-blue-700 ring-blue-600/20",
    outbound: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    ignored: "bg-slate-100 text-slate-600 ring-slate-500/10",
    discarded: "bg-slate-100 text-slate-500 ring-slate-500/10",
    reminder: "bg-purple-50 text-purple-700 ring-purple-600/20",
    followup: "bg-orange-50 text-orange-700 ring-orange-600/20",
  };
  return styles[direction] || "bg-slate-100 text-slate-600 ring-slate-500/10";
}

function draftStatus(log: MessageLog) {
  if (log.direction === "outbound") return { label: "Sent", className: "text-emerald-600" };
  if (log.direction === "ignored") return { label: "Skipped", className: "text-slate-500" };
  if (log.direction === "discarded") return { label: "Deleted", className: "text-slate-500" };
  if (log.direction === "draft") return { label: "Draft in Gmail", className: "text-blue-600" };
  return { label: log.direction, className: "text-slate-500" };
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toISOString().replace("T", " ").slice(0, 16) + " UTC";
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

  useEffect(() => {
    setMounted(true);
  }, []);

  const visibleLogs = logs.filter((log) => log.direction !== "discarded");

  if (visibleLogs.length === 0) {
    return (
      <div className="card py-12 text-center text-sm text-slate-500">
        No messages yet. Connect Gmail and wait for inquiries, or click Poll now.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {visibleLogs.map((log) => {
        const open = expanded === log.id;
        const status = draftStatus(log);
        return (
          <div key={log.id} className="card overflow-hidden p-0">
            <button
              type="button"
              onClick={() => setExpanded(open ? null : log.id)}
              className="flex w-full items-start gap-4 px-5 py-4 text-left hover:bg-slate-50/80"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={clsx(
                      "rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
                      directionBadge(log.direction)
                    )}
                  >
                    {log.direction}
                  </span>
                  <span className={clsx("text-xs font-medium", status.className)}>{status.label}</span>
                  {log.quote_amount && (
                    <span className="text-xs font-semibold text-brand-700">{log.quote_amount}</span>
                  )}
                </div>
                <p className="mt-1 truncate font-medium text-slate-900">{log.subject || "No subject"}</p>
                <p className="mt-0.5 text-xs text-slate-500" suppressHydrationWarning>
                  {mounted ? formatTime(log.created_at) : "—"}
                </p>
              </div>
              {open ? (
                <ChevronUp className="mt-1 h-5 w-5 flex-shrink-0 text-slate-400" />
              ) : (
                <ChevronDown className="mt-1 h-5 w-5 flex-shrink-0 text-slate-400" />
              )}
            </button>

            {open && (
              <div className="border-t border-surface-border bg-slate-50/50 px-5 py-4">
                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Customer email
                    </h4>
                    <pre className="max-h-48 overflow-auto rounded-lg border border-surface-border bg-white p-3 text-sm text-slate-700 whitespace-pre-wrap">
                      {log.inbound_body || "Original email not stored for this entry."}
                    </pre>
                  </div>
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      AI summary
                    </h4>
                    <div className="rounded-lg border border-brand-200 bg-brand-50/50 p-3 text-sm text-slate-800">
                      {log.summary || "No AI summary available."}
                    </div>
                  </div>
                </div>

                {log.reply_body && (
                  <div className="mt-4">
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Draft reply
                    </h4>
                    <pre className="max-h-56 overflow-auto rounded-lg border border-surface-border bg-white p-3 text-sm text-slate-700 whitespace-pre-wrap">
                      {log.reply_body}
                    </pre>
                  </div>
                )}

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  {log.can_send && (
                    <button
                      type="button"
                      onClick={() => onSend(log.id)}
                      disabled={sendingId === log.id}
                      className="btn-primary"
                    >
                      <Send className="h-4 w-4" />
                      {sendingId === log.id ? "Sending…" : "Send reply"}
                    </button>
                  )}
                  {log.gmail_thread_id && (
                    <a
                      href={`https://mail.google.com/mail/u/0/#inbox/${log.gmail_thread_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-secondary"
                    >
                      <ExternalLink className="h-4 w-4" />
                      Open in Gmail
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
