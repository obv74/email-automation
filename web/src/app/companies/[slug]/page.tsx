"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Link2,
  Mail,
  Play,
  RefreshCw,
  Unlink,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { api, ApiError, MessageLog, Tenant } from "@/lib/api";
import { getToken } from "@/lib/auth";

function directionBadge(direction: string) {
  const styles: Record<string, string> = {
    draft: "bg-blue-50 text-blue-700",
    outbound: "bg-emerald-50 text-emerald-700",
    ignored: "bg-slate-100 text-slate-600",
    reminder: "bg-purple-50 text-purple-700",
    followup: "bg-orange-50 text-orange-700",
  };
  return styles[direction] || "bg-slate-100 text-slate-600";
}

export default function CompanyPageWrapper() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <RefreshCw className="h-8 w-8 animate-spin text-brand-600" />
        </div>
      }
    >
      <CompanyPage />
    </Suspense>
  );
}

function CompanyPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const slug = params.slug as string;

  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [logs, setLogs] = useState<MessageLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    setLoading(true);
    try {
      const [t, l] = await Promise.all([api.getTenant(token, slug), api.getLogs(token, slug)]);
      setTenant(t);
      setLogs(l);
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load company");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const gmail = searchParams.get("gmail");
    if (gmail === "connected") setNotice("Gmail connected successfully.");
    if (gmail === "disconnected") setNotice("Gmail disconnected.");
  }, [searchParams]);

  async function onPoll() {
    const token = getToken();
    if (!token) return;
    setPolling(true);
    try {
      await api.poll(token, slug);
      await load();
      setNotice("Inbox polled — check message log below.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Poll failed");
    } finally {
      setPolling(false);
    }
  }

  async function onDisconnect() {
    const token = getToken();
    if (!token) return;
    try {
      await api.disconnectGmail(token, slug);
      await load();
      setNotice("Gmail disconnected.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Disconnect failed");
    }
  }

  function onConnectGmail() {
    const token = getToken();
    if (!token) return;
    window.location.href = api.gmailConnectUrl(slug, token);
  }

  if (loading && !tenant) {
    return (
      <AuthGuard>
        <AppShell>
          <div className="flex justify-center py-24">
            <RefreshCw className="h-8 w-8 animate-spin text-brand-600" />
          </div>
        </AppShell>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <AppShell>
        <Link
          href="/dashboard"
          className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" />
          All companies
        </Link>

        {tenant && (
          <>
            <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">{tenant.name}</h1>
                <p className="mt-1 text-slate-600">
                  {tenant.gmail_connected && tenant.connected_gmail_email
                    ? `Gmail: ${tenant.connected_gmail_email}`
                    : "Gmail not connected"}
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                {tenant.gmail_connected ? (
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
                      {polling ? "Polling…" : "Poll now"}
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

            {!tenant.gmail_connected && (
              <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Connect Gmail to start reading inquiries. Use Incognito if switching Google accounts.
              </div>
            )}

            {notice && (
              <div className="mb-6 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                {notice}
              </div>
            )}

            {error && (
              <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="card mb-6 grid gap-4 sm:grid-cols-3">
              <div>
                <p className="text-sm text-slate-500">Reply mode</p>
                <p className="font-semibold capitalize text-slate-900">{tenant.reply_mode}</p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Pricing sheet</p>
                <p className="truncate font-semibold text-slate-900">
                  {tenant.pricing_sheet_id || "Not set"}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Auto-poll</p>
                <p className="font-semibold text-slate-900">Every 5 minutes</p>
              </div>
            </div>

            <h2 className="mb-4 text-lg font-semibold text-slate-900">Message log</h2>
            {logs.length === 0 ? (
              <div className="card py-12 text-center text-sm text-slate-500">
                No messages yet. Connect Gmail and wait for inquiries, or click Poll now.
              </div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-surface-border bg-white shadow-card">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-surface-border bg-slate-50">
                    <tr>
                      <th className="px-4 py-3 font-medium text-slate-600">Time</th>
                      <th className="px-4 py-3 font-medium text-slate-600">Type</th>
                      <th className="px-4 py-3 font-medium text-slate-600">Subject</th>
                      <th className="px-4 py-3 font-medium text-slate-600">Quote</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {logs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-50/50">
                        <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${directionBadge(log.direction)}`}
                          >
                            {log.direction}
                          </span>
                        </td>
                        <td className="max-w-xs truncate px-4 py-3 text-slate-900">
                          {log.subject || "—"}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{log.quote_amount || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </AppShell>
    </AuthGuard>
  );
}
