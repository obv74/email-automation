"use client";

import { useMemo, useState } from "react";
import { Check, Copy } from "lucide-react";
import clsx from "clsx";

type JobFields = Record<string, unknown>;

const FIELD_GROUPS: { title: string; keys: { key: string; label: string }[] }[] = [
  {
    title: "Title",
    keys: [
      { key: "customer_name", label: "Client Name" },
      { key: "customer_phone", label: "Phone" },
      { key: "move_date", label: "Date" },
      { key: "move_time", label: "Time" },
      { key: "city_state", label: "City, State" },
      { key: "service_requested", label: "Service / Job Description" },
      { key: "minimum_hours", label: "Minimum hours" },
      { key: "special_notes", label: "Special Notes" },
    ],
  },
  {
    title: "Booking entry",
    keys: [
      { key: "load_address", label: "Load Address" },
      { key: "unload_address", label: "Unload Address" },
      { key: "inventory", label: "Inventory List" },
      { key: "heaviest_item", label: "Heaviest Item" },
      { key: "customer_requests", label: "Customer Requests" },
      { key: "promises_made", label: "Company Promises" },
      { key: "booking_source", label: "Booking source" },
      { key: "truck_type", label: "Truck" },
      { key: "num_movers", label: "Movers" },
      { key: "customer_email", label: "Email" },
    ],
  },
  {
    title: "Special handling",
    keys: [
      { key: "over_250_lbs", label: "Over 250 lbs?" },
      { key: "super_fragile", label: "Super fragile?" },
      { key: "over_1000_value", label: "Over $1000 value?" },
      { key: "packing", label: "Packing?" },
      { key: "unpacking", label: "Unpacking?" },
      { key: "assembly", label: "Assembly?" },
      { key: "disassembly", label: "Disassembly?" },
      { key: "special_handling_notes", label: "Notes" },
    ],
  },
  {
    title: "Pricing",
    keys: [
      { key: "minimum_hours", label: "Minimum Hours" },
      { key: "minimum_price", label: "Minimum Price" },
      { key: "hourly_rate", label: "Hourly Rate" },
      { key: "deposit", label: "Deposit" },
      { key: "balance_due", label: "Balance Due" },
    ],
  },
];

function formatValue(value: unknown): string {
  if (value == null || value === "") return "";
  if (Array.isArray(value)) return value.filter(Boolean).join(", ");
  return String(value);
}

function buildCopyText(job: JobFields): string {
  const lines: string[] = ["=== TITLE ==="];
  for (const f of FIELD_GROUPS[0].keys) {
    lines.push(`${f.label}: ${formatValue(job[f.key])}`);
  }
  lines.push("", "=== BOOKING ENTRY ===");
  for (const f of FIELD_GROUPS[1].keys) {
    lines.push(`${f.label}: ${formatValue(job[f.key])}`);
  }
  lines.push("", "=== SPECIAL HANDLING ===");
  for (const f of FIELD_GROUPS[2].keys) {
    lines.push(`${f.label}: ${formatValue(job[f.key])}`);
  }
  lines.push("", "=== PRICING ===");
  for (const f of FIELD_GROUPS[3].keys) {
    lines.push(`${f.label}: ${formatValue(job[f.key])}`);
  }
  if (job.summary) {
    lines.push("", "=== SUMMARY ===", formatValue(job.summary));
  }
  return lines.join("\n");
}

export function parseExtraction(extractionJson: string | null): JobFields | null {
  if (!extractionJson) return null;
  try {
    const data = JSON.parse(extractionJson);
    if (!data || typeof data !== "object") return null;
    return data as JobFields;
  } catch {
    return null;
  }
}

type Props = {
  extractionJson: string | null;
  summaryFallback?: string | null;
};

export function JobFieldsPanel({ extractionJson, summaryFallback }: Props) {
  const job = useMemo(() => parseExtraction(extractionJson), [extractionJson]);
  const [copied, setCopied] = useState(false);

  if (!job) {
    return (
      <div className="rounded-md border border-slate-200 bg-slate-100 p-2.5 text-xs text-slate-600">
        {summaryFallback || "No structured job fields yet."}
      </div>
    );
  }

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText(buildCopyText(job));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Job categories
        </h4>
        <button
          type="button"
          onClick={copyAll}
          className="inline-flex items-center gap-1 rounded-md border border-surface-border bg-white px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy all"}
        </button>
      </div>

      {FIELD_GROUPS.map((group) => (
        <div key={group.title}>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            {group.title}
          </p>
          <dl className="overflow-hidden rounded-md border border-surface-border bg-white">
            {group.keys.map((f, i) => {
              const val = formatValue(job[f.key]);
              return (
                <div
                  key={f.key}
                  className={clsx(
                    "grid grid-cols-[140px_1fr] gap-2 px-2.5 py-1.5 text-xs",
                    i > 0 && "border-t border-slate-100"
                  )}
                >
                  <dt className="text-slate-500">{f.label}</dt>
                  <dd className={clsx("text-slate-800", !val && "text-slate-300")}>
                    {val || "—"}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      ))}

      {job.summary ? (
        <div>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            Summary
          </p>
          <p className="rounded-md border border-brand-200 bg-brand-50/50 p-2.5 text-xs text-slate-800">
            {formatValue(job.summary)}
          </p>
        </div>
      ) : null}
    </div>
  );
}
