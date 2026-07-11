"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { RotateCcw, Save, Sparkles } from "lucide-react";
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

function PromptsForm() {
  const { company, loading, reload } = useCompany();
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
      setClassifyPrompt(company.classify_prompt || "");
      setExtractionSystem(company.extraction_system_prompt || "");
      setExtractionUser(company.extraction_user_prompt || "");
      setReplyTemplate(company.reply_template || "");
    }
  }, [company]);

  const aiEnabled = company?.ai_enabled !== false;

  async function onSave(e: FormEvent) {
    e.preventDefault();
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await api.updateCompany(token, {
        classify_prompt: classifyPrompt,
        extraction_system_prompt: extractionSystem,
        extraction_user_prompt: extractionUser,
        reply_template: replyTemplate,
      });
      await reload();
      setNotice("Prompts saved. New emails will use this text.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save prompts");
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
      setNotice("Prompts reset to defaults.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reset prompts");
    } finally {
      setResetting(false);
    }
  }

  const placeholders = company?.prompt_placeholders || {
    classify: "{email}",
    extraction: "{email}, {schema}",
    reply: "{customer_name}, {summary}, {quote}, …",
  };
  const defaults = company?.using_default_prompts;

  return (
    <>
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">AI prompts</h1>
          <p className="mt-1 text-slate-600">
            Classify → extract → Gmail draft. Saved per company in the database.
          </p>
        </div>
        <button
          type="button"
          onClick={onResetPrompts}
          className="btn-secondary"
          disabled={!aiEnabled || resetting || loading}
        >
          <RotateCcw className="h-4 w-4" />
          {resetting ? "Resetting…" : "Reset to defaults"}
        </button>
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

      {!aiEnabled && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          AI is off. Turn it on in{" "}
          <Link href="/settings" className="font-semibold underline">
            Settings
          </Link>{" "}
          for these prompts to run.
        </div>
      )}

      {loading && !company ? (
        <p className="text-slate-500">Loading…</p>
      ) : (
        <form onSubmit={onSave} className={`max-w-3xl space-y-5 ${!aiEnabled ? "opacity-70" : ""}`}>
          <div className="rounded-lg border border-slate-100 bg-white px-4 py-3 text-xs text-slate-600 shadow-sm">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-800">
              <Sparkles className="h-4 w-4 text-brand-600" />
              Pipeline
            </div>
            <ol className="list-decimal space-y-1 pl-4">
              <li>
                <strong className="text-slate-800">Classify</strong> — booked / inquiry / ignore /
                unclear
              </li>
              <li>
                <strong className="text-slate-800">Extract</strong> — full job categories (booked +
                inquiry)
              </li>
              <li>
                <strong className="text-slate-800">Reply</strong> — stock/template draft for{" "}
                <em>inquiries only</em> (booked jobs are extract-only)
              </li>
            </ol>
          </div>

          <section className="card space-y-6">
            <PromptEditor
              label="1. Classify prompt (booked / inquiry / ignore / unclear)"
              description="Return email_type. Keep {email}. Booked = already paid/scheduled (Moving Helper). Unclear escalates to Needs-Human."
              placeholders={placeholders.classify}
              value={classifyPrompt}
              onChange={setClassifyPrompt}
              rows={10}
              disabled={!aiEnabled}
              isDefault={defaults?.classify}
            />
          </section>

          <section className="card space-y-6">
            <PromptEditor
              label="2a. Extract — system instructions"
              description="Keep this short — long system prompts slow CPU Ollama."
              placeholders="(no placeholders — plain instructions)"
              value={extractionSystem}
              onChange={setExtractionSystem}
              rows={7}
              disabled={!aiEnabled}
              isDefault={defaults?.extraction_system}
            />
            <PromptEditor
              label="2b. Extract — user prompt"
              description="Keep {schema}, {example}, and {email}. Short prompts = faster on weak VPS."
              placeholders={placeholders.extraction}
              value={extractionUser}
              onChange={setExtractionUser}
              rows={10}
              disabled={!aiEnabled}
              isDefault={defaults?.extraction_user}
            />
          </section>

          <section className="card space-y-6">
            <PromptEditor
              label="3. Gmail reply template"
              description="Filled with extracted fields and the quote. This becomes the draft body — not sent to the AI."
              placeholders={placeholders.reply}
              value={replyTemplate}
              onChange={setReplyTemplate}
              rows={14}
              disabled={!aiEnabled}
              isDefault={defaults?.reply}
            />
          </section>

          <button type="submit" className="btn-primary" disabled={saving || !aiEnabled}>
            <Save className="h-4 w-4" />
            {saving ? "Saving…" : "Save prompts"}
          </button>
        </form>
      )}
    </>
  );
}

export default function PromptsPage() {
  return (
    <AuthGuard>
      <AppShell>
        <PromptsForm />
      </AppShell>
    </AuthGuard>
  );
}
