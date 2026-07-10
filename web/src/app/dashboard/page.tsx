"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, ExternalLink, Play, RefreshCw, Settings } from "lucide-react";
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
          : "Inbox checked — emails logged (AI is off)."
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
            {company?.ai_enabled ? "AI processing on" : "Monitor only — AI off"}
            {company?.gmail_connected ? " · Inbox connected" : " · Gmail not connected"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/settings" className="btn-secondary">
            <Settings className="h-4 w-4" />
            Settings
          </Link>
          {company?.gmail_connected ? (
            <button onClick={onPoll} className="btn-primary" disabled={polling}>
              <Play className="h-4 w-4" />
              {polling ? "Checking…" : "Check inbox"}
            </button>
          ) : (
            <Link href="/settings" className="btn-primary">
              Connect Gmail
            </Link>
          )}
        </div>
      </div>

      {!company?.gmail_connected && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Connect Gmail in Settings to start monitoring inquiries.
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
            Auto-check: <strong className="text-slate-900">every {company.poll_interval_minutes} min</strong>
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
