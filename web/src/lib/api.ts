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
  is_active: boolean;
  reply_mode: string;
};

export type MessageLog = {
  id: number;
  direction: string;
  subject: string | null;
  quote_amount: string | null;
  rule_name: string | null;
  reply_body: string | null;
  gmail_thread_id: string | null;
  created_at: string;
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

  listTenants: (token: string) => request<Tenant[]>("/api/tenants", {}, token),

  createTenant: (
    token: string,
    data: { name: string; slug?: string; pricing_sheet_id?: string; contact_email?: string }
  ) =>
    request<Tenant>("/api/tenants", {
      method: "POST",
      body: JSON.stringify(data),
    }, token),

  getTenant: (token: string, slug: string) => request<Tenant>(`/api/tenants/${slug}`, {}, token),

  getLogs: (token: string, slug: string) =>
    request<MessageLog[]>(`/api/tenants/${slug}/logs`, {}, token),

  poll: (token: string, slug: string) =>
    request<unknown[]>(`/api/tenants/${slug}/poll`, { method: "POST" }, token),

  disconnectGmail: (token: string, slug: string) =>
    request<{ status: string }>(`/api/tenants/${slug}/gmail/disconnect`, { method: "POST" }, token),

  gmailConnectUrl: (slug: string, token: string) =>
    `${API_URL}/auth/google/connect?tenant=${encodeURIComponent(slug)}&token=${encodeURIComponent(token)}`,

  gmailDisconnectUrl: (slug: string, token: string) =>
    `${API_URL}/auth/google/disconnect?tenant=${encodeURIComponent(slug)}&token=${encodeURIComponent(token)}`,
};

export { API_URL };
