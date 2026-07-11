"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, ExternalLink, Play, RefreshCw, Settings, Sparkles } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { MessageLogPanel } from "@/components/MessageLogPanel";
import { useCompany } from "@/hooks/useCompany";
import { api, ApiError, MessageLog, ThreadPreview } from "@/lib/api";
import { getToken } from "@/lib/auth";

function DashboardContent() {
  const searchParams = useSearchParams();
  const { company, loading, error: companyError, reload } = useCompany();
  const [logs, setLogs] = useState<MessageLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractingId, setExtractingId] = useState<string | null>(null);
  const [threadRef, setThreadRef] = useState("");
  const [recent, setRecent] = useState<ThreadPreview[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);
  const [sendingId, setSendingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadLogs = useCallback(async () => {
    const token = getToken();
    if (!token || !company) return;
    setLogsLoading(true);
    setLogs([]);
    try {
      const next = await api.getLogs(token, company.slug);
      setLogs(next.filter((log) => log.direction !== "discarded"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load messages");
    } finally {
      setLogsLoading(false);
    }
  }, [company]);

  const loadRecent = useCallback(async () => {
    const token = getToken();
    if (!token || !company?.gmail_connected) return;
    setRecentLoading(true);
    try {
      const data = await api.listRecentThreads(token, company.slug);
      setRecent(data.previews || []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load recent mail");
    } finally {
      setRecentLoading(false);
    }
  }, [company]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    loadRecent();
  }, [loadRecent]);

  useEffect(() => {
    const gmail = searchParams.get("gmail");
    if (gmail === "connected") {
      setNotice("Gmail connected. Manage it anytime in Settings.");
      reload();
    }
  }, [searchParams, reload]);

  async function runExtract(ref: string) {
    const token = getToken();
    if (!token || !company) return;
    setExtracting(true);
    setError("");
    try {
      const result = await api.extractThread(token, company.slug, ref);
      await loadLogs();
      setNotice(
        result.status === "extracted"
          ? "Extracted that one email into job categories (no reply drafted)."
          : `Done: ${result.status}`
      );
      setThreadRef("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Extract failed");
    } finally {
      setExtracting(false);
      setExtractingId(null);
    }
  }

  async function onExtractPaste() {
    if (!threadRef.trim()) {
      setError("Paste a Gmail API thread id, or pick an email from the list below.");
      return;
    }
    if (threadRef.includes("FMfcgz") || threadRef.trim().startsWith("FMfcgz")) {
      setError(
        "Gmail browser links (FMfcgz…) do not work with Google’s API. Pick the email from the list below instead."
      );
      return;
    }
    await runExtract(threadRef.trim());
  }

  async function onExtractRow(threadId: string) {
    setExtractingId(threadId);
    await runExtract(threadId);
  }

  async function onPoll() {
    const token = getToken();
    if (!token || !company) return;
    setPolling(true);
    setError("");
    try {
      await api.poll(token, company.slug);
      await loadLogs();
      await reload();
      setNotice(
        company.ai_enabled
          ? "Inbox checked — AI processed new mail."
          : "Inbox not auto-processed (AI is off). Use Extract on one email instead."
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Poll failed");
    } finally {
      setPolling(false);
    }
  }

  async function onSend(logId: number) {
    const token = getToken();
    if (!token || !company) return;
    setSendingId(logId);
    setError("");
    try {
      await api.sendLog(token, company.slug, logId);
      await loadLogs();
      setNotice("Reply sent.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Send failed");
    } finally {
      setSendingId(null);
    }
  }

  if (loading && !company) {
    return (
      <div className="flex justify-center py-24">
        <RefreshCw className="h-8 w-8 animate-spin text-brand-600" />
      </div>
    );
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{company?.name || "Dashboard"}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {company?.ai_enabled ? "Auto-poll on" : "Manual mode — AI auto-poll off"}
            {company?.gmail_connected ? " · Inbox connected" : " · Gmail not connected"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/settings" className="btn-secondary">
            <Settings className="h-4 w-4" />
            Settings
          </Link>
          {company?.gmail_connected && company.ai_enabled ? (
            <button onClick={onPoll} className="btn-secondary" disabled={polling}>
              <Play className="h-4 w-4" />
              {polling ? "Checking…" : "Check inbox (all unread)"}
            </button>
          ) : null}
          {!company?.gmail_connected ? (
            <Link href="/settings" className="btn-primary">
              Connect Gmail
            </Link>
          ) : null}
        </div>
      </div>

      {company?.gmail_connected ? (
        <div className="card mb-5 space-y-4">
          <div className="flex items-start gap-2">
            <Sparkles className="mt-0.5 h-4 w-4 text-brand-600" />
            <div>
              <h2 className="font-semibold text-slate-900">Extract one email</h2>
              <p className="mt-1 text-sm text-slate-500">
                Pick an email below (works on phone). Only that thread is read — no full-inbox scan,
                no auto-reply.
              </p>
              <p className="mt-1 text-xs text-amber-700">
                Do not paste normal Gmail browser links (they start with FMfcgz and Google rejects
                them). Use the list.
              </p>
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-medium text-slate-800">Recent inbox</h3>
              <button
                type="button"
                onClick={loadRecent}
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
                disabled={recentLoading}
              >
                {recentLoading ? "Loading…" : "Refresh list"}
              </button>
            </div>
            {recentLoading && recent.length === 0 ? (
              <div className="flex justify-center py-6">
                <RefreshCw className="h-5 w-5 animate-spin text-brand-600" />
              </div>
            ) : recent.length === 0 ? (
              <p className="rounded-md border border-dashed border-surface-border px-3 py-4 text-sm text-slate-500">
                No recent inbox threads found.
              </p>
            ) : (
              <ul className="divide-y divide-surface-border overflow-hidden rounded-lg border border-surface-border bg-white">
                {recent.map((t) => (
                  <li key={t.thread_id} className="flex items-start gap-3 px-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">{t.subject}</p>
                      <p className="truncate text-xs text-slate-500">{t.from}</p>
                      {t.snippet ? (
                        <p className="mt-0.5 line-clamp-2 text-xs text-slate-400">{t.snippet}</p>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      className="btn-primary !px-2.5 !py-1.5 text-xs"
                      disabled={extracting}
                      onClick={() => onExtractRow(t.thread_id)}
                    >
                      {extractingId === t.thread_id ? "…" : "Extract"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <details className="text-sm text-slate-600">
            <summary className="cursor-pointer font-medium text-slate-700">
              Advanced: paste API thread id
            </summary>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <input
                type="text"
                value={threadRef}
                onChange={(e) => setThreadRef(e.target.value)}
                placeholder="hex thread id from API (not FMfcgz…)"
                className="input-field flex-1"
              />
              <button
                type="button"
                onClick={onExtractPaste}
                disabled={extracting}
                className="btn-secondary whitespace-nowrap"
              >
                {extracting && !extractingId ? "Extracting…" : "Extract"}
              </button>
            </div>
          </details>
        </div>
      ) : (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Connect Gmail in Settings, then pick one email from the list to extract.
        </div>
      )}

      {notice && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
          {notice}
        </div>
      )}

      {(error || companyError) && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error || companyError}
        </div>
      )}

      {company && (
        <div className="mb-5 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
          <span>
            Auto-check:{" "}
            <strong className="text-slate-900">
              {company.ai_enabled ? `every ${company.poll_interval_minutes} min` : "off (manual only)"}
            </strong>
          </span>
          <span>
            Pricing:{" "}
            {company.pricing_sheet_url ? (
              <a
                href={company.pricing_sheet_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-semibold text-brand-600 hover:text-brand-700"
              >
                Open sheet
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            ) : (
              <Link href="/settings" className="font-semibold text-amber-600 hover:text-amber-700">
                Set in Settings
              </Link>
            )}
          </span>
        </div>
      )}

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">Message log</h2>
        <button onClick={loadLogs} className="text-sm font-medium text-brand-600 hover:text-brand-700">
          Refresh
        </button>
      </div>

      {logsLoading ? (
        <div className="flex justify-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin text-brand-600" />
        </div>
      ) : (
        <MessageLogPanel logs={logs} onSend={onSend} sendingId={sendingId} />
      )}
    </>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard>
      <AppShell>
        <Suspense
          fallback={
            <div className="flex justify-center py-24">
              <RefreshCw className="h-8 w-8 animate-spin text-brand-600" />
            </div>
          }
        >
          <DashboardContent />
        </Suspense>
      </AppShell>
    </AuthGuard>
  );
}
