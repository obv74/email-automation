const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type User = {
  id: number;
  email: string;
  name: string | null;
  created_at: string;
};

export type Tenant = {
  id: string;
  slug: string;
  name: string;
  gmail_connected: boolean;
  connected_gmail_email: string | null;
  pricing_sheet_id: string | null;
  pricing_sheet_url: string | null;
  is_active: boolean;
  reply_mode: string;
  poll_interval_minutes: number;
};

export type MessageLog = {
  id: number;
  direction: string;
  subject: string | null;
  quote_amount: string | null;
  rule_name: string | null;
  reply_body: string | null;
  inbound_body: string | null;
  summary: string | null;
  extraction_json: string | null;
  gmail_thread_id: string | null;
  gmail_draft_id: string | null;
  gmail_message_id: string | null;
  draft_exists: boolean | null;
  can_send: boolean;
  created_at: string;
};

export type UpdateCompanyBody = {
  name?: string;
  pricing_sheet_id?: string;
  reply_mode?: string;
  poll_interval_minutes?: number;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), res.status);
  }
  return res.json();
}

export const api = {
  register: (email: string, password: string, name: string) =>
    request<{ access_token: string; user: User }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),

  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: (token: string) => request<User>("/api/auth/me", {}, token),

  getCompany: (token: string) => request<Tenant>("/api/company", {}, token),

  updateCompany: (token: string, data: UpdateCompanyBody) =>
    request<Tenant>("/api/company", { method: "PATCH", body: JSON.stringify(data) }, token),

  getLogs: (token: string, slug: string) =>
    request<MessageLog[]>(`/api/tenants/${slug}/logs`, {}, token),

  poll: (token: string, slug: string) =>
    request<unknown[]>(`/api/tenants/${slug}/poll`, { method: "POST" }, token),

  sendLog: (token: string, slug: string, logId: number) =>
    request<{ status: string; message_id?: string }>(
      `/api/tenants/${slug}/logs/${logId}/send`,
      { method: "POST" },
      token
    ),

  disconnectGmail: (token: string, slug: string) =>
    request<{ status: string }>(`/api/tenants/${slug}/gmail/disconnect`, { method: "POST" }, token),

  gmailConnectUrl: (slug: string, token: string) =>
    `${API_URL}/auth/google/connect?tenant=${encodeURIComponent(slug)}&token=${encodeURIComponent(token)}`,
};

export { API_URL };
