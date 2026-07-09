import Link from "next/link";
import { ArrowRight, Bot, Mail, Sheet, Zap } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-indigo-50">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2 font-semibold text-brand-900">
          <Mail className="h-6 w-6 text-brand-600" />
          Email Agent
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900">
            Sign in
          </Link>
          <Link href="/register" className="btn-primary">
            Get started
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 pb-20 pt-16 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-4 py-1.5 text-sm font-medium text-brand-700">
          <Bot className="h-4 w-4" />
          AI-powered Gmail automation
        </div>
        <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
          Turn moving inquiries into quoted replies — automatically
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600">
          Connect Gmail, link your pricing sheet, and let AI read threads, extract job details,
          and draft professional quotes every 5 minutes.
        </p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link href="/register" className="btn-primary px-6 py-3 text-base">
            Create free account
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/login" className="btn-secondary px-6 py-3 text-base">
            Sign in
          </Link>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 pb-24 sm:grid-cols-3">
        {[
          {
            icon: Mail,
            title: "Gmail connected",
            desc: "Reads unread inbox threads and drafts replies — you stay in control.",
          },
          {
            icon: Sheet,
            title: "Sheet pricing",
            desc: "Pulls rates from your Google Sheet and inserts quotes into every reply.",
          },
          {
            icon: Zap,
            title: "Multi-company",
            desc: "One account, many moving companies — each with its own Gmail and sheet.",
          },
        ].map((f) => (
          <div key={f.title} className="card text-left">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
              <f.icon className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-slate-900">{f.title}</h3>
            <p className="mt-2 text-sm text-slate-600">{f.desc}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
