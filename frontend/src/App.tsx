import { useCallback, useEffect, useRef, useState } from "react";
import {
  type ChatMessage,
  type ChatSource,
  type Client,
  type ClientPage,
  type DocumentItem,
  type DocumentPage,
  type SearchResult,
  createClient,
  createDocument,
  getDocument,
  listClients,
  listDocuments,
  search,
  streamChat,
} from "./api";

type Mode = "list" | "search";
type Tab = "clients" | "documents";

interface ClientFormData {
  first_name: string;
  last_name: string;
  email: string;
  description: string;
  social_links: string;
}

interface DocFormData {
  client_email: string;
  title: string;
  content: string;
}

const EMPTY_CLIENT_FORM: ClientFormData = { first_name: "", last_name: "", email: "", description: "", social_links: "" };
const EMPTY_DOC_FORM: DocFormData = { client_email: "", title: "", content: "" };

function isSafeUrl(link: string): boolean {
  try {
    const url = new URL(link);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export default function App() {
  const [mode, setMode] = useState<Mode>("list");
  const [tab, setTab] = useState<Tab>("clients");
  const [clients, setClients] = useState<Client[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const [clientCursor, setClientCursor] = useState<string | null>(null);
  const [clientHasMore, setClientHasMore] = useState(false);
  const [docCursor, setDocCursor] = useState<string | null>(null);
  const [docHasMore, setDocHasMore] = useState(false);

  const [showClientForm, setShowClientForm] = useState(false);
  const [showDocForm, setShowDocForm] = useState(false);

  const [expandedDocs, setExpandedDocs] = useState<Record<string, DocumentItem | null>>({});

  const toggleDoc = useCallback(async (docId: string) => {
    if (expandedDocs[docId] !== undefined) {
      setExpandedDocs((prev) => {
        const next = { ...prev };
        delete next[docId];
        return next;
      });
      return;
    }
    setExpandedDocs((prev) => ({ ...prev, [docId]: null }));
    try {
      const doc = await getDocument(docId);
      setExpandedDocs((prev) => ({ ...prev, [docId]: doc }));
    } catch {
      setExpandedDocs((prev) => {
        const next = { ...prev };
        delete next[docId];
        return next;
      });
    }
  }, [expandedDocs]);
  const [clientForm, setClientForm] = useState<ClientFormData>(EMPTY_CLIENT_FORM);
  const [docForm, setDocForm] = useState<DocFormData>(EMPTY_DOC_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const clientCursorHistory = useRef<string[]>([]);
  const docCursorHistory = useRef<string[]>([]);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const streamAbort = useRef<AbortController | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const handleSendMessage = useCallback(async () => {
    const q = chatInput.trim();
    if (!q || streaming) return;
    setChatInput("");
    setChatError(null);
    setStreaming(true);

    const userMsg: ChatMessage = { role: "user", content: q };
    const assistantMsg: ChatMessage = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    let sources: ChatSource[] = [];
    const msgIndex = messages.length + 1;

    const ctrl = streamChat(
      q,
      (token) => {
        setMessages((prev) => {
          const next = [...prev];
          next[msgIndex] = { ...next[msgIndex], content: next[msgIndex].content + token };
          return next;
        });
      },
      (srcs) => {
        sources = srcs;
      },
      () => {
        setMessages((prev) => {
          const next = [...prev];
          next[msgIndex] = { ...next[msgIndex], sources };
          return next;
        });
        setStreaming(false);
        setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
      },
      (err) => {
        setChatError(err);
        setMessages((prev) => {
          const next = [...prev];
          next[msgIndex] = { ...next[msgIndex], content: "[Error: " + err + "]" };
          return next;
        });
        setStreaming(false);
      },
    );
    streamAbort.current = ctrl;
  }, [chatInput, streaming, messages.length]);

  const loadClients = useCallback(async (reset: boolean = false) => {
    setLoading(true);
    setError(null);
    try {
      const cursor = reset ? undefined : clientCursor ?? undefined;
      const page: ClientPage = await listClients(cursor, 20);
      if (reset) clientCursorHistory.current = [];
      setClients(page.items);
      setClientHasMore(page.has_more);
      setClientCursor(page.next_cursor);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [clientCursor]);

  const loadDocuments = useCallback(async (reset: boolean = false) => {
    setLoading(true);
    setError(null);
    try {
      const cursor = reset ? undefined : docCursor ?? undefined;
      const page: DocumentPage = await listDocuments(cursor, 20);
      if (reset) docCursorHistory.current = [];
      setDocuments(page.items);
      setDocHasMore(page.has_more);
      setDocCursor(page.next_cursor);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [docCursor]);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setMode("list");
      setSearchResults([]);
      return;
    }
    setMode("search");
    setLoading(true);
    setError(null);
    try {
      const results = await search(q, 50);
      setSearchResults(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const onSearchChange = (value: string) => {
    setSearchQuery(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => doSearch(value), 300);
  };

  useEffect(() => {
    loadClients(true);
    loadDocuments(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchTab = (t: Tab) => { setTab(t); setMode("list"); setSearchQuery(""); setSearchResults([]); };

  const loadNext = () => tab === "clients" ? loadClients(false) : loadDocuments(false);

  const loadPrev = () => {
    const history = tab === "clients" ? clientCursorHistory : docCursorHistory;
    const setCursor = tab === "clients" ? setClientCursor : setDocCursor;
    const loadFn = tab === "clients" ? () => loadClients(false) : () => loadDocuments(false);
    if (history.current.length >= 2) {
      history.current.pop();
      const prev = history.current.pop();
      setCursor(prev ?? null);
      setTimeout(loadFn, 0);
    } else {
      setCursor(null);
      tab === "clients" ? loadClients(true) : loadDocuments(true);
    }
  };

  const hasMore = tab === "clients" ? clientHasMore : docHasMore;
  const cursorHistory = tab === "clients" ? clientCursorHistory : docCursorHistory;
  const items = tab === "clients" ? clients : documents;

  const handleCreateClient = async () => {
    setFormError(null);
    if (!clientForm.first_name.trim() || !clientForm.last_name.trim() || !clientForm.email.trim()) {
      setFormError("First name, last name, and email are required");
      return;
    }
    setSubmitting(true);
    try {
      const links = clientForm.social_links.trim()
        ? clientForm.social_links.split(",").map((s) => s.trim()).filter(Boolean)
        : undefined;

      await createClient({
        first_name: clientForm.first_name.trim(),
        last_name: clientForm.last_name.trim(),
        email: clientForm.email.trim(),
        description: clientForm.description.trim() || undefined,
        social_links: links,
      });
      setShowClientForm(false);
      setClientForm(EMPTY_CLIENT_FORM);
      loadClients(true);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Failed to create client");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateDocument = async () => {
    setFormError(null);
    if (!docForm.client_email.trim() || !docForm.title.trim() || !docForm.content.trim()) {
      setFormError("Email, title, and content are required");
      return;
    }
    setSubmitting(true);
    try {
      await createDocument(docForm.client_email.trim(), {
        title: docForm.title.trim(),
        content: docForm.content.trim(),
      });
      setShowDocForm(false);
      setDocForm(EMPTY_DOC_FORM);
      loadDocuments(true);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Failed to create document");
    } finally {
      setSubmitting(false);
    }
  };

  const clientCount = searchResults.filter((r) => r.type === "client").length;
  const docCount = searchResults.filter((r) => r.type === "document").length;

  return (
    <div className="main-layout">
      <div className="left-panel">
    <div className="container">
      <h1>RAG Search — WealthTech</h1>
      <p className="subtitle">Hybrid search across clients &amp; documents · RRF-fused retrieval</p>

      {error && <div className="error-msg">{error}</div>}

      <div className="search-bar">
        <input type="text"
          placeholder="Search everything…"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        <button onClick={() => doSearch(searchQuery)} disabled={loading}>Search</button>
      </div>

      <div className="toolbar">
        <div className="tabs">
          <button className={`tab-btn ${tab === "clients" ? "active" : ""}`} onClick={() => switchTab("clients")}>
            Clients
          </button>
          <button className={`tab-btn ${tab === "documents" ? "active" : ""}`} onClick={() => switchTab("documents")}>
            Documents
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="add-btn" onClick={() => { setFormError(null); setShowDocForm(true); }}>+ Document</button>
          <button className="add-btn" onClick={() => { setFormError(null); setShowClientForm(true); }}>+ Client</button>
        </div>
      </div>

      <div className="card">
        {loading && <div className="loading">Loading…</div>}

        {!loading && mode === "search" && (
          <div className="stats">
            <span className="badge badge-search">SEARCH</span>{" "}
            {searchResults.length} result{searchResults.length !== 1 ? "s" : ""}{" "}
            {clientCount > 0 && <span style={{ color: "#4f46e5" }}>· {clientCount} client{clientCount !== 1 ? "s" : ""}</span>}
            {docCount > 0 && <span style={{ color: "#059669" }}>· {docCount} document{docCount !== 1 ? "s" : ""}</span>}
          </div>
        )}

        {!loading && mode === "list" && items.length === 0 && (
          <div className="empty">{tab === "clients" ? "No clients yet." : "No documents yet."}</div>
        )}

        {!loading && mode === "search" && searchResults.length === 0 && (
          <div className="empty">No results found.</div>
        )}

        {!loading && mode === "search" && searchResults.map((r, i) => (
          <div key={i} className={`result-row ${r.type === "document" ? "doc-row" : "client-row"}`}>
            <div className="result-info">
              <div className="result-title">
                {r.type === "document"
                  ? <><span className="badge badge-doc">DOC</span> {r.document?.title}</>
                  : <><span className="badge badge-client">CLIENT</span> {r.client?.first_name} {r.client?.last_name}</>
                }
                <span className="result-score">{r.score.toFixed(4)}</span>
              </div>
              {r.type === "client" && r.client && (
                <>
                  <div className="result-sub">{r.client.email}</div>
                  {r.client.description && <div className="result-desc">{r.client.description}</div>}
                  {r.client.social_links && r.client.social_links.length > 0 && (
                    <div className="result-desc">
                      {r.client.social_links.map((link: string) =>
                        isSafeUrl(link) ? (
                          <a key={link} className="social-link" href={link}
                             target="_blank" rel="noopener noreferrer">{link}</a>
                        ) : (
                          <span key={link} className="social-link social-link-unsafe"
                                title="Unsafe URL blocked">{link}</span>
                        )
                      )}
                    </div>
                  )}
                </>
              )}
              {r.type === "document" && r.document && (
                <>
                  <div className="result-sub">
                    {r.document.title} · Chunk #{r.document.chunk_index}
                  </div>
                  <div className="result-desc">{r.document.content}</div>
                  <button className="btn-link"
                    onClick={() => toggleDoc(r.document!.document_id)}>
                    {expandedDocs[r.document!.document_id] !== undefined
                      ? "Hide full document"
                      : "View full document"}
                  </button>
                  {expandedDocs[r.document!.document_id] && (
                    <div className="doc-content">
                      {expandedDocs[r.document!.document_id]!.content}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}

        {!loading && mode === "list" && items.map((item) => (
          <div key={item.id} className={`result-row ${tab === "documents" ? "doc-row" : "client-row"}`}>
            <div className="result-info">
              <div className="result-title">
                {tab === "documents"
                  ? (item as DocumentItem).title
                  : `${(item as Client).first_name} ${(item as Client).last_name}`
                }
              </div>
              <div className="result-sub">
                {tab === "documents"
                  ? `by ${(item as DocumentItem).client_name}`
                  : (item as Client).email
                }
              </div>
              {tab === "documents" && (
                <div className="doc-content">{(item as DocumentItem).content}</div>
              )}
              {tab === "clients" && (item as Client).description && (
                <div className="result-desc">{(item as Client).description}</div>
              )}
              {tab === "clients" && (item as Client).social_links && (item as Client).social_links!.length > 0 && (
                <div className="result-desc">
                  {(item as Client).social_links!.map((link) =>
                    isSafeUrl(link) ? (
                      <a key={link} className="social-link" href={link}
                         target="_blank" rel="noopener noreferrer">{link}</a>
                    ) : (
                      <span key={link} className="social-link social-link-unsafe"
                            title="Unsafe URL blocked">{link}</span>
                    )
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {mode === "list" && !loading && (
        <div className="pagination">
          <button onClick={loadPrev} disabled={cursorHistory.current.length === 0}>← Previous</button>
          <button onClick={loadNext} disabled={!hasMore}>Next →</button>
        </div>
      )}

      {showClientForm && (
        <Modal title="Add New Client" onClose={() => setShowClientForm(false)}>
          {formError && <div className="error-msg">{formError}</div>}
          <Field label="First Name *"><input type="text" value={clientForm.first_name}
            onChange={(e) => setClientForm({ ...clientForm, first_name: e.target.value })} /></Field>
          <Field label="Last Name *"><input type="text" value={clientForm.last_name}
            onChange={(e) => setClientForm({ ...clientForm, last_name: e.target.value })} /></Field>
          <Field label="Email *"><input type="email" value={clientForm.email}
            onChange={(e) => setClientForm({ ...clientForm, email: e.target.value })} /></Field>
          <Field label="Description"><textarea rows={3} value={clientForm.description}
            onChange={(e) => setClientForm({ ...clientForm, description: e.target.value })} /></Field>
          <Field label="Social Links (comma-separated)">
            <input type="text" value={clientForm.social_links} placeholder="https://linkedin.com/in/john, https://twitter.com/john"
              onChange={(e) => setClientForm({ ...clientForm, social_links: e.target.value })} /></Field>
          <div className="form-actions">
            <button className="btn btn-secondary" onClick={() => setShowClientForm(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleCreateClient} disabled={submitting}>
              {submitting ? "Creating…" : "Create Client"}</button>
          </div>
        </Modal>
      )}

      {showDocForm && (
        <Modal title="Add Document" onClose={() => setShowDocForm(false)}>
          {formError && <div className="error-msg">{formError}</div>}
          <Field label="Client Email *"><input type="email" value={docForm.client_email}
            onChange={(e) => setDocForm({ ...docForm, client_email: e.target.value })}
            placeholder="john@example.com" /></Field>
          <Field label="Title *"><input type="text" value={docForm.title}
            onChange={(e) => setDocForm({ ...docForm, title: e.target.value })} /></Field>
          <Field label="Content *"><textarea rows={6} value={docForm.content}
            onChange={(e) => setDocForm({ ...docForm, content: e.target.value })} /></Field>
          <div className="form-actions">
            <button className="btn btn-secondary" onClick={() => setShowDocForm(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleCreateDocument} disabled={submitting}>
              {submitting ? "Indexing…" : "Create Document"}</button>
          </div>
        </Modal>
      )}
    </div>
      </div>
      <div className="right-panel">
        <div className="chat-header">AI Assistant</div>
        <div className="chat-messages">
          {chatError && <div className="chat-error">{chatError}</div>}
          {messages.length === 0 && !streaming && (
            <div className="chat-empty">
              Ask a question about clients, documents, or portfolio data.
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`chat-msg ${msg.role}`}>
              <div className="chat-msg-avatar">{msg.role === "user" ? "U" : "AI"}</div>
              <div className="chat-msg-body">
                <div className="chat-msg-header">
                  <span className="chat-msg-name">{msg.role === "user" ? "You" : "Assistant"}</span>
                </div>
                <div className="chat-msg-text">
                  {msg.content || (streaming && i === messages.length - 1 ? <span className="typing-cursor" /> : null)}
                </div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="chat-sources">
                    Sources:{" "}
                    {msg.sources.map((s) => (
                      <span
                        key={s.num}
                        className="chat-source-chip"
                        onClick={() => {
                          if (s.type === "document") toggleDoc(s.id);
                        }}
                        title={s.type === "document" ? "View full document" : "Client: " + s.title}
                      >
                        [{s.num}] {s.title}
                      </span>
                    ))}
                  </div>
                )}
                {msg.sources && msg.sources.some((s) => s.type === "document" && expandedDocs[s.id]) && (
                  <div>
                    {msg.sources.filter((s) => s.type === "document" && expandedDocs[s.id]).map((s) => (
                      <div key={s.id} className="doc-content">
                        {expandedDocs[s.id]?.content}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
        <div className="chat-input-row">
          <textarea
            className="chat-input"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            placeholder="Ask a question…"
            rows={2}
            disabled={streaming}
          />
          <button
            className="chat-send-btn"
            onClick={handleSendMessage}
            disabled={streaming || !chatInput.trim()}
          >
            {streaming ? "…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="form-overlay" onClick={onClose}>
      <div className="form-modal" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="form-field"><label>{label}</label>{children}</div>;
}
