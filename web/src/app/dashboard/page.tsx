"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Building2, Mail, Plus, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { api, ApiError, Tenant } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function DashboardPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", pricing_sheet_id: "" });

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    setLoading(true);
    try {
      setTenants(await api.listTenants(token));
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load companies");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    const token = getToken();
    if (!token) return;
    setCreating(true);
    try {
      await api.createTenant(token, {
        name: form.name,
        slug: form.slug || undefined,
        pricing_sheet_id: form.pricing_sheet_id || undefined,
      });
      setForm({ name: "", slug: "", pricing_sheet_id: "" });
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create company");
    } finally {
      setCreating(false);
    }
  }

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Your companies</h1>
            <p className="mt-1 text-slate-600">Each company has its own Gmail and pricing sheet.</p>
          </div>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary">
            <Plus className="h-4 w-4" />
            Add company
          </button>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {showForm && (
          <form onSubmit={onCreate} className="card mb-8 space-y-4">
            <h2 className="font-semibold text-slate-900">New company</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Company name</label>
                <input
                  className="input-field"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Acme Moving"
                  required
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">URL slug (optional)</label>
                <input
                  className="input-field"
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  placeholder="acme-moving"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Google Sheet ID</label>
                <input
                  className="input-field"
                  value={form.pricing_sheet_id}
                  onChange={(e) => setForm({ ...form, pricing_sheet_id: e.target.value })}
                  placeholder="From sheet URL: docs.google.com/spreadsheets/d/THIS_PART/edit"
                />
              </div>
            </div>
            <div className="flex gap-3">
              <button type="submit" className="btn-primary" disabled={creating}>
                {creating ? "Creating…" : "Create company"}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
                Cancel
              </button>
            </div>
          </form>
        )}

        {loading ? (
          <div className="flex justify-center py-16">
            <RefreshCw className="h-8 w-8 animate-spin text-brand-600" />
          </div>
        ) : tenants.length === 0 ? (
          <div className="card py-16 text-center">
            <Building2 className="mx-auto h-12 w-12 text-slate-300" />
            <h3 className="mt-4 font-semibold text-slate-900">No companies yet</h3>
            <p className="mt-2 text-sm text-slate-600">Add your first moving company to get started.</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {tenants.map((t) => (
              <Link
                key={t.slug}
                href={`/companies/${t.slug}`}
                className="card group transition hover:border-brand-300 hover:shadow-elevated"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-900 group-hover:text-brand-700">{t.name}</h3>
                    <p className="text-sm text-slate-500">{t.slug}</p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      t.gmail_connected
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-amber-50 text-amber-700"
                    }`}
                  >
                    {t.gmail_connected ? "Gmail on" : "Gmail off"}
                  </span>
                </div>
                {t.gmail_connected && t.connected_gmail_email && (
                  <p className="mt-3 flex items-center gap-2 text-sm text-slate-600">
                    <Mail className="h-4 w-4" />
                    {t.connected_gmail_email}
                  </p>
                )}
              </Link>
            ))}
          </div>
        )}
      </AppShell>
    </AuthGuard>
  );
}
