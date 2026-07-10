"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  CheckCircle2,
  ExternalLink,
  Link2,
  Mail,
  Play,
  RefreshCw,
  Unlink,
} from "lucide-react";
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
    try {
      setLogs(await api.getLogs(token, company.slug));
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
      setNotice("Gmail connected successfully.");
      reload();
    }
    if (gmail === "disconnected") setNotice("Gmail disconnected.");
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
      setNotice("Inbox checked — see message log below.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Poll failed");
    } finally {
      setPolling(false);
    }
  }

  async function onDisconnect() {
    const token = getToken();
    if (!token || !company) return;
    try {
      await api.disconnectGmail(token, company.slug);
      await reload();
      setNotice("Gmail disconnected.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Disconnect failed");
    }
  }

  function onConnectGmail() {
    const token = getToken();
    if (!token || !company) return;
    window.location.href = api.gmailConnectUrl(company.slug, token);
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
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{company?.name || "Dashboard"}</h1>
          <p className="mt-1 text-slate-600">
            {company?.gmail_connected && company.connected_gmail_email
              ? company.connected_gmail_email
              : "Connect Gmail to start processing inquiries"}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          {company?.gmail_connected ? (
            <>
              <button onClick={onConnectGmail} className="btn-secondary">
                <Link2 className="h-4 w-4" />
                Switch Gmail
              </button>
              <button onClick={onDisconnect} className="btn-secondary">
                <Unlink className="h-4 w-4" />
                Disconnect
              </button>
              <button onClick={onPoll} className="btn-primary" disabled={polling}>
                <Play className="h-4 w-4" />
                {polling ? "Checking…" : "Check inbox now"}
              </button>
            </>
          ) : (
            <button onClick={onConnectGmail} className="btn-primary">
              <Mail className="h-4 w-4" />
              Connect Gmail
            </button>
          )}
        </div>
      </div>

      {company && !company.gmail_connected && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Connect your company Gmail to read inquiries. Use Incognito if switching Google accounts.
        </div>
      )}

      {notice && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
          {notice}
        </div>
      )}

      {(error || companyError) && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error || companyError}
        </div>
      )}

      {company && (
        <div className="mb-8 grid gap-4 sm:grid-cols-3">
          <div className="card">
            <p className="text-sm text-slate-500">Gmail</p>
            <p className="mt-1 font-semibold text-slate-900">
              {company.gmail_connected ? "Connected" : "Not connected"}
            </p>
          </div>
          <div className="card">
            <p className="text-sm text-slate-500">Auto-check inbox</p>
            <p className="mt-1 font-semibold text-slate-900">Every {company.poll_interval_minutes} min</p>
          </div>
          <div className="card">
            <p className="text-sm text-slate-500">Pricing sheet</p>
            {company.pricing_sheet_url ? (
              <a
                href={company.pricing_sheet_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 font-semibold text-brand-600 hover:text-brand-700"
              >
                Open sheet
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            ) : (
              <p className="mt-1 font-semibold text-amber-600">Not set — go to Settings</p>
            )}
          </div>
        </div>
      )}

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Message log</h2>
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
