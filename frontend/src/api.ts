const API_BASE = "";

export interface Client {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  description: string | null;
  social_links: string[] | null;
  created_at: string;
}

export interface ClientPage {
  items: Client[];
  next_cursor: string | null;
  has_more: boolean;
  count: number;
}

export interface DocumentItem {
  id: string;
  client_id: string;
  client_name: string;
  title: string;
  content: string;
  created_at: string;
}

export interface DocumentPage {
  items: DocumentItem[];
  next_cursor: string | null;
  has_more: boolean;
  count: number;
}

export interface DocumentHit {
  id: string;
  document_id: string;
  client_id: string;
  title: string;
  chunk_index: number;
  content: string;
}

export interface SearchResult {
  type: "client" | "document";
  score: number;
  client?: Client;
  document?: DocumentHit;
}

export interface ErrorDetail {
  code: string;
  message: string;
  resource_id: string | null;
}

async function handleError(resp: Response): Promise<never> {
  let detail: ErrorDetail;
  try {
    const body = await resp.json();
    detail = body.detail ?? body;
  } catch {
    throw new Error(`HTTP ${resp.status}`);
  }
  throw new Error(detail.message ?? "Request failed");
}

export async function listClients(cursor?: string, limit: number = 20): Promise<ClientPage> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  const resp = await fetch(`${API_BASE}/v1/clients?${params}`);
  if (!resp.ok) return handleError(resp);
  return resp.json();
}

export async function listDocuments(cursor?: string, limit: number = 20): Promise<DocumentPage> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  const resp = await fetch(`${API_BASE}/v1/documents?${params}`);
  if (!resp.ok) return handleError(resp);
  return resp.json();
}

export async function createClient(payload: {
  first_name: string;
  last_name: string;
  email: string;
  description?: string;
  social_links?: string[];
}): Promise<Client> {
  const resp = await fetch(`${API_BASE}/v1/clients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) return handleError(resp);
  return resp.json();
}

export async function createDocument(
  clientEmail: string,
  payload: { title: string; content: string },
): Promise<{ id: string }> {
  const lookup = await fetch(`${API_BASE}/v1/clients/lookup?email=${encodeURIComponent(clientEmail)}`);
  if (!lookup.ok) throw new Error("Client not found");
  const client = await lookup.json();
  const resp = await fetch(`${API_BASE}/v1/clients/${client.id}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) return handleError(resp);
  return resp.json();
}

export async function search(q: string, limit: number = 20): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  const resp = await fetch(`${API_BASE}/v1/search?${params}`);
  if (!resp.ok) return handleError(resp);
  return resp.json();
}
