"use client";

import { useState } from "react";
import { CheckCircle2, FileSearch, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { JobFieldsPanel } from "@/components/JobFieldsPanel";
import { useCompany } from "@/hooks/useCompany";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function ExtractPage() {
  const { company, loading, error: companyError } = useCompany();
  const [text, setText] = useState("");
  const [saveSheet, setSaveSheet] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [extractionJson, setExtractionJson] = useState<string | null>(null);
  const [copyable, setCopyable] = useState("");

  async function onExtract() {
    const token = getToken();
    if (!token || !company) return;
    if (text.trim().length < 20) {
      setError("Paste the email thread text (at least a few lines).");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    setExtractionJson(null);
    setCopyable("");
    try {
      const result = await api.extractText(token, company.slug, text.trim(), {
        save_to_sheet: saveSheet,
        save_to_log: true,
      });
      setExtractionJson(JSON.stringify(result.extraction));
      setCopyable(result.copyable || "");
      setNotice(
        result.saved_to_sheet
          ? "Extracted and saved to your Google Sheet."
          : "Extracted — review categories below. (Sheet save was off.)"
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Extract failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !company) {
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
        <div className="mb-6">
          <div className="flex items-center gap-2">
            <FileSearch className="h-6 w-6 text-brand-600" />
            <h1 className="text-2xl font-bold text-slate-900">Extract job</h1>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Paste any email thread text → get structured job categories. No Gmail link needed. Works
            on phone.
          </p>
        </div>

        {(error || companyError) && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error || companyError}
          </div>
        )}
        {notice && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
            {notice}
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <section className="card space-y-3">
            <h2 className="font-semibold text-slate-900">1. Paste email text</h2>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={16}
              placeholder={`From: customer@email.com\nSubject: Move help\n\nHi, I need help unloading a 15ft truck on July 9 at 1pm...\n\n(Paste the full thread here)`}
              className="input-field min-h-[280px] font-mono text-xs leading-relaxed"
            />
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={saveSheet}
                onChange={(e) => setSaveSheet(e.target.checked)}
                className="rounded border-slate-300"
              />
              <span>
                Also save row to{" "}
                {company?.pricing_sheet_url ? (
                  <a
                    href={company.pricing_sheet_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-brand-600 underline decoration-brand-300 underline-offset-2 hover:text-brand-700"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Google Sheet
                  </a>
                ) : (
                  <span className="font-medium text-slate-700">Google Sheet</span>
                )}
                {!company?.pricing_sheet_url ? (
                  <span className="text-slate-400"> (set sheet ID in Settings)</span>
                ) : null}
              </span>
            </label>
            <button
              type="button"
              onClick={onExtract}
              disabled={busy || !company}
              className="btn-primary w-full sm:w-auto"
            >
              {busy ? "Extracting…" : "Extract categories"}
            </button>
          </section>

          <section className="card space-y-3">
            <h2 className="font-semibold text-slate-900">2. Result</h2>
            {!extractionJson && !busy ? (
              <p className="rounded-md border border-dashed border-surface-border px-3 py-10 text-center text-sm text-slate-500">
                Categories will appear here after you extract.
              </p>
            ) : busy ? (
              <div className="flex justify-center py-16">
                <RefreshCw className="h-7 w-7 animate-spin text-brand-600" />
              </div>
            ) : (
              <>
                <JobFieldsPanel extractionJson={extractionJson} />
                {copyable ? (
                  <div>
                    <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Copy block (title + booking entry)
                    </h3>
                    <pre className="max-h-56 overflow-auto rounded-md border border-surface-border bg-slate-50 p-2.5 text-xs whitespace-pre-wrap text-slate-700">
                      {copyable}
                    </pre>
                  </div>
                ) : null}
              </>
            )}
          </section>
        </div>
      </AppShell>
    </AuthGuard>
  );
}
