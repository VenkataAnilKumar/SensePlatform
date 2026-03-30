/**
 * Sense Console — API Client
 * Thin wrapper over Sense Gate REST API.
 * Reads API key from cookie set at login.
 */

const GATE_URL = process.env.NEXT_PUBLIC_GATE_URL ?? "http://localhost:3000";

async function request<T>(
  path: string,
  options: RequestInit = {},
  apiKey?: string,
): Promise<T> {
  const key = apiKey ?? (typeof document !== "undefined"
    ? document.cookie.match(/sense_api_key=([^;]+)/)?.[1]
    : undefined);

  const resp = await fetch(`${GATE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "X-API-Key": key } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(`[SenseGate] ${resp.status}: ${err.detail}`);
  }

  return resp.json() as Promise<T>;
}

// ── Tenant ────────────────────────────────────────────────────────────────────

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  email: string;
  is_active: boolean;
}

export const tenantsApi = {
  me: () => request<Tenant>("/tenants/me"),
  create: (data: { name: string; slug: string; email: string }) =>
    request<Tenant>("/tenants", { method: "POST", body: JSON.stringify(data) }),
};

// ── API Keys ──────────────────────────────────────────────────────────────────

export interface ApiKey {
  id: string;
  key: string;
  name: string;
  is_test: boolean;
}

export const apiKeysApi = {
  list: () => request<ApiKey[]>("/tenants/me/api-keys"),
  create: (name: string, test = false) =>
    request<ApiKey>("/tenants/me/api-keys", {
      method: "POST",
      body: JSON.stringify({ name, test }),
    }),
  revoke: (id: string) =>
    request<void>(`/tenants/me/api-keys/${id}`, { method: "DELETE" }),
};

// ── Rooms ─────────────────────────────────────────────────────────────────────

export interface Room {
  room_id: string;
  room_name: string;
  num_participants: number;
  creation_time: number;
}

export const roomsApi = {
  list: () => request<Room[]>("/rooms"),
};

// ── Agents ────────────────────────────────────────────────────────────────────

export interface AgentStatus {
  status: string;
  room?: string;
  lenses: Array<{ name: string; available: boolean }>;
}

export const agentsApi = {
  start: (roomId: string, lenses: string[] = [], llm = "claude-sonnet-4-6") =>
    request<{ status: string; room: string }>("/agents/start", {
      method: "POST",
      body: JSON.stringify({ room_id: roomId, lenses, llm }),
    }),
  stop: (roomId: string) =>
    request<{ status: string }>("/agents/stop", {
      method: "POST",
      body: JSON.stringify({ room_id: roomId }),
    }),
  status: (roomId: string) =>
    request<AgentStatus>(`/agents/status?room_id=${roomId}`),
};

// ── Webhooks ──────────────────────────────────────────────────────────────────

export interface Webhook {
  id: string;
  url: string;
  events: string;
  is_active: boolean;
  secret?: string;
}

export const webhooksApi = {
  list: () => request<Webhook[]>("/webhooks"),
  create: (url: string, events = "*") =>
    request<Webhook>("/webhooks", {
      method: "POST",
      body: JSON.stringify({ url, events }),
    }),
  delete: (id: string) =>
    request<void>(`/webhooks/${id}`, { method: "DELETE" }),
  test: (id: string) =>
    request<{ delivered: boolean; url: string }>(`/webhooks/${id}/test`, { method: "POST" }),
};

// ── Usage ─────────────────────────────────────────────────────────────────────

export interface UsageSummary {
  event_type: string;
  total_quantity: number;
  unit: string;
  count: number;
}

export interface UsageResponse {
  tenant_id: string;
  from_date: string;
  to_date: string;
  summary: UsageSummary[];
  total_records: number;
}

export const usageApi = {
  get: (fromDate?: string, toDate?: string) => {
    const params = new URLSearchParams();
    if (fromDate) params.set("from_date", fromDate);
    if (toDate) params.set("to_date", toDate);
    return request<UsageResponse>(`/usage?${params}`);
  },
};

// ── Health ────────────────────────────────────────────────────────────────────

export const healthApi = {
  check: () => request<{ status: string; service: string }>("/health"),
};
