"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, ExternalLink, Play, RefreshCw, Settings, Sparkles } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { MessageLogPanel } from "@/components/MessageLogPanel";
import { useCompany } from "@/hooks/useCompany";
import { api, ApiError, MessageLog } from "@/lib/api";
import { getToken } from "@/lib/auth";

function DashboardContent() {
  const searchParams = useSearchParams();
  const { company, loading, error: companyError, reload } = useCompany();
  const [logs, setLogs] = useState<MessageLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [threadRef, setThreadRef] = useState("");
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

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    const gmail = searchParams.get("gmail");
    if (gmail === "connected") {
      setNotice("Gmail connected. Manage it anytime in Settings.");
      reload();
    }
  }, [searchParams, reload]);

  async function onExtract() {
    const token = getToken();
    if (!token || !company) return;
    if (!threadRef.trim()) {
      setError("Paste a Gmail thread link (or thread id) first.");
      return;
    }
    setExtracting(true);
    setError("");
    try {
      const result = await api.extractThread(token, company.slug, threadRef.trim());
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
    }
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
          : "Inbox not auto-processed (AI is off). Use Extract one email instead."
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
        <div className="card mb-5 space-y-3">
          <div className="flex items-start gap-2">
            <Sparkles className="mt-0.5 h-4 w-4 text-brand-600" />
            <div>
              <h2 className="font-semibold text-slate-900">Extract one email (recommended)</h2>
              <p className="mt-1 text-sm text-slate-500">
                Paste a Gmail link for the thread you choose. Only that email is read — no full-inbox
                scan, no auto-reply. Job categories appear in the log below (and{" "}
                <code className="text-xs">ExtractedJobs</code> sheet).
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={threadRef}
              onChange={(e) => setThreadRef(e.target.value)}
              placeholder="https://mail.google.com/mail/u/0/#inbox/…"
              className="input-field flex-1"
            />
            <button
              type="button"
              onClick={onExtract}
              disabled={extracting || !company.gmail_connected}
              className="btn-primary whitespace-nowrap"
            >
              {extracting ? "Extracting…" : "Extract job"}
            </button>
          </div>
        </div>
      ) : (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Connect Gmail in Settings, then paste one thread link to extract.
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
          <span>
            AI prompts:{" "}
            <Link href="/prompts" className="font-semibold text-brand-600 hover:text-brand-700">
              Edit prompts
            </Link>
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
