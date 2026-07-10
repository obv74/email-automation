"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ExternalLink, Link2, Mail, RotateCcw, Save, Unlink } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { useCompany } from "@/hooks/useCompany";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";

function PromptEditor({
  label,
  description,
  placeholders,
  value,
  onChange,
  rows = 8,
  disabled,
  isDefault,
}: {
  label: string;
  description: string;
  placeholders: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  disabled?: boolean;
  isDefault?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="block text-sm font-medium text-slate-700">{label}</label>
        {isDefault ? (
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
            Default
          </span>
        ) : (
          <span className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
            Custom
          </span>
        )}
      </div>
      <p className="text-sm text-slate-500">{description}</p>
      <p className="font-mono text-xs text-slate-400">Placeholders: {placeholders}</p>
      <textarea
        className="input-field min-h-[8rem] resize-y font-mono text-[13px] leading-relaxed"
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        spellCheck={false}
      />
    </div>
  );
}

function SettingsForm() {
  const searchParams = useSearchParams();
  const { company, loading, reload } = useCompany();
  const [name, setName] = useState("");
  const [sheetId, setSheetId] = useState("");
  const [replyMode, setReplyMode] = useState("draft");
  const [pollMinutes, setPollMinutes] = useState(5);
  const [aiEnabled, setAiEnabled] = useState(true);
  const [classifyPrompt, setClassifyPrompt] = useState("");
  const [extractionSystem, setExtractionSystem] = useState("");
  const [extractionUser, setExtractionUser] = useState("");
  const [replyTemplate, setReplyTemplate] = useState("");
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (company) {
      setName(company.name);
      setSheetId(company.pricing_sheet_id || "");
      setReplyMode(company.reply_mode);
      setPollMinutes(company.poll_interval_minutes);
      setAiEnabled(company.ai_enabled !== false);
      setClassifyPrompt(company.classify_prompt || "");
      setExtractionSystem(company.extraction_system_prompt || "");
      setExtractionUser(company.extraction_user_prompt || "");
      setReplyTemplate(company.reply_template || "");
    }
  }, [company]);

  useEffect(() => {
    const gmail = searchParams.get("gmail");
    if (gmail === "connected") setNotice("Gmail connected successfully.");
    if (gmail === "disconnected") setNotice("Gmail disconnected.");
  }, [searchParams]);

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
        ai_enabled: aiEnabled,
        classify_prompt: classifyPrompt,
        extraction_system_prompt: extractionSystem,
        extraction_user_prompt: extractionUser,
        reply_template: replyTemplate,
      });
      await reload();
      setNotice("Settings saved. New emails will use your updated AI prompts.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  async function onResetPrompts() {
    const token = getToken();
    if (!token) return;
    if (!window.confirm("Reset classify, extract, and reply text to the built-in defaults?")) {
      return;
    }
    setResetting(true);
    setError("");
    setNotice("");
    try {
      await api.updateCompany(token, { reset_prompts: true });
      await reload();
      setNotice("AI prompts reset to defaults.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reset prompts");
    } finally {
      setResetting(false);
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

  const sheetUrl = sheetId
    ? `https://docs.google.com/spreadsheets/d/${sheetId.trim()}/edit`
    : null;

  const placeholders = company?.prompt_placeholders || {
    classify: "{email}",
    extraction: "{email}, {schema}",
    reply: "{customer_name}, {summary}, {quote}, …",
  };
  const defaults = company?.using_default_prompts;

  return (
    <>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-slate-600">Gmail, AI prompts, pricing, and automation.</p>
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
        <form onSubmit={onSave} className="max-w-3xl space-y-5">
          <section className="card space-y-4">
            <h2 className="font-semibold text-slate-900">Company</h2>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Company name</label>
              <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
          </section>

          <section className="card space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold text-slate-900">Gmail</h2>
                <p className="mt-1 text-sm text-slate-500">
                  {company?.gmail_connected && company.connected_gmail_email
                    ? company.connected_gmail_email
                    : "Not connected"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {company?.gmail_connected ? (
                  <>
                    <button type="button" onClick={onConnectGmail} className="btn-secondary">
                      <Link2 className="h-4 w-4" />
                      Switch Gmail
                    </button>
                    <button type="button" onClick={onDisconnect} className="btn-secondary">
                      <Unlink className="h-4 w-4" />
                      Disconnect
                    </button>
                  </>
                ) : (
                  <button type="button" onClick={onConnectGmail} className="btn-primary">
                    <Mail className="h-4 w-4" />
                    Connect Gmail
                  </button>
                )}
              </div>
            </div>
            <p className="text-xs text-slate-500">
              Use an Incognito window if you need to sign into a different Google account.
            </p>
          </section>

          <section className="card space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold text-slate-900">AI summarize & reply</h2>
                <p className="mt-1 text-sm text-slate-500">
                  On: classify, extract, quote, and draft replies.
                  <br />
                  Off: only monitor Gmail and log new emails.
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={aiEnabled}
                onClick={() => setAiEnabled(!aiEnabled)}
                className={`relative h-7 w-12 flex-shrink-0 rounded-full transition ${
                  aiEnabled ? "bg-brand-600" : "bg-slate-300"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 h-6 w-6 rounded-full bg-white shadow transition ${
                    aiEnabled ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          </section>

          <section
            className={`card space-y-6 ${!aiEnabled ? "opacity-60" : ""}`}
            aria-disabled={!aiEnabled}
          >
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
              <div>
                <h2 className="font-semibold text-slate-900">AI prompts & reply</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Edit how the AI decides yes/no, what it extracts, and the Gmail draft text.
                  Each company has its own copy.
                </p>
              </div>
              <button
                type="button"
                onClick={onResetPrompts}
                className="btn-secondary"
                disabled={!aiEnabled || resetting}
              >
                <RotateCcw className="h-4 w-4" />
                {resetting ? "Resetting…" : "Reset to defaults"}
              </button>
            </div>

            <div className="rounded-lg border border-slate-100 bg-slate-50/80 px-4 py-3 text-xs text-slate-600">
              <ol className="list-decimal space-y-1 pl-4">
                <li>
                  <strong className="text-slate-800">Classify</strong> — yes/no moving inquiry
                </li>
                <li>
                  <strong className="text-slate-800">Extract</strong> — pull date, movers, truck, addresses
                </li>
                <li>
                  <strong className="text-slate-800">Reply</strong> — fill template → Gmail draft (not AI-written)
                </li>
              </ol>
            </div>

            <PromptEditor
              label="1. Classify prompt (yes / no)"
              description="Ask whether the email is a moving inquiry. Must keep {email} so the message is included."
              placeholders={placeholders.classify}
              value={classifyPrompt}
              onChange={setClassifyPrompt}
              rows={10}
              disabled={!aiEnabled}
              isDefault={defaults?.classify}
            />

            <PromptEditor
              label="2a. Extract — system instructions"
              description="How the model should behave when reading the email."
              placeholders="(no placeholders — plain instructions)"
              value={extractionSystem}
              onChange={setExtractionSystem}
              rows={7}
              disabled={!aiEnabled}
              isDefault={defaults?.extraction_system}
            />

            <PromptEditor
              label="2b. Extract — user prompt"
              description="The extraction request. Keep {email} and preferably {schema} so fields stay valid."
              placeholders={placeholders.extraction}
              value={extractionUser}
              onChange={setExtractionUser}
              rows={8}
              disabled={!aiEnabled}
              isDefault={defaults?.extraction_user}
            />

            <PromptEditor
              label="3. Gmail reply template"
              description="Filled with extracted fields and the quote. This is not sent to the AI — it becomes the draft body."
              placeholders={placeholders.reply}
              value={replyTemplate}
              onChange={setReplyTemplate}
              rows={14}
              disabled={!aiEnabled}
              isDefault={defaults?.reply}
            />
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
                disabled={!aiEnabled}
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
            </div>
          </section>

          <button type="submit" className="btn-primary" disabled={saving}>
            <Save className="h-4 w-4" />
            {saving ? "Saving…" : "Save settings"}
          </button>
        </form>
      )}
    </>
  );
}

export default function SettingsPage() {
  return (
    <AuthGuard>
      <AppShell>
        <Suspense fallback={<p className="text-slate-500">Loading…</p>}>
          <SettingsForm />
        </Suspense>
      </AppShell>
    </AuthGuard>
  );
}
