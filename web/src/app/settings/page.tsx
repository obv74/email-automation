"use client";

import { FormEvent, useEffect, useState } from "react";
import { ExternalLink, Save } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { useCompany } from "@/hooks/useCompany";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function SettingsPage() {
  const { company, loading, reload } = useCompany();
  const [name, setName] = useState("");
  const [sheetId, setSheetId] = useState("");
  const [replyMode, setReplyMode] = useState("draft");
  const [pollMinutes, setPollMinutes] = useState(5);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (company) {
      setName(company.name);
      setSheetId(company.pricing_sheet_id || "");
      setReplyMode(company.reply_mode);
      setPollMinutes(company.poll_interval_minutes);
    }
  }, [company]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await api.updateCompany(token, {
        name,
        pricing_sheet_id: sheetId,
        reply_mode: replyMode,
        poll_interval_minutes: pollMinutes,
      });
      await reload();
      setNotice("Settings saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  const sheetUrl = sheetId
    ? `https://docs.google.com/spreadsheets/d/${sheetId.trim()}/edit`
    : null;

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
          <p className="mt-1 text-slate-600">Company profile, pricing sheet, and automation preferences.</p>
        </div>

        {notice && (
          <div className="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {notice}
          </div>
        )}
        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading && !company ? (
          <p className="text-slate-500">Loading…</p>
        ) : (
          <form onSubmit={onSave} className="max-w-2xl space-y-6">
            <section className="card space-y-4">
              <h2 className="font-semibold text-slate-900">Company</h2>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Company name</label>
                <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} required />
              </div>
              {company?.connected_gmail_email && (
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">Connected Gmail</label>
                  <p className="text-sm text-slate-600">{company.connected_gmail_email}</p>
                </div>
              )}
            </section>

            <section className="card space-y-4">
              <h2 className="font-semibold text-slate-900">Pricing sheet</h2>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Google Sheet ID</label>
                <input
                  className="input-field"
                  value={sheetId}
                  onChange={(e) => setSheetId(e.target.value)}
                  placeholder="Paste ID from sheet URL"
                />
                <p className="mt-1.5 text-xs text-slate-500">
                  From: docs.google.com/spreadsheets/d/<strong>THIS_PART</strong>/edit
                </p>
              </div>
              {sheetUrl && (
                <a
                  href={sheetUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 hover:text-brand-700"
                >
                  Open pricing sheet
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </section>

            <section className="card space-y-4">
              <h2 className="font-semibold text-slate-900">Automation</h2>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Reply mode</label>
                <select
                  className="input-field"
                  value={replyMode}
                  onChange={(e) => setReplyMode(e.target.value)}
                >
                  <option value="draft">Draft — create Gmail draft for review</option>
                  <option value="send">Send — auto-send replies (use with care)</option>
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Auto-check inbox (minutes)
                </label>
                <input
                  type="number"
                  min={1}
                  max={1440}
                  className="input-field"
                  value={pollMinutes}
                  onChange={(e) => setPollMinutes(Number(e.target.value))}
                />
                <p className="mt-1.5 text-xs text-slate-500">
                  How often the agent checks Gmail for new inquiries (1–1440 minutes).
                </p>
              </div>
            </section>

            <button type="submit" className="btn-primary" disabled={saving}>
              <Save className="h-4 w-4" />
              {saving ? "Saving…" : "Save settings"}
            </button>
          </form>
        )}
      </AppShell>
    </AuthGuard>
  );
}
