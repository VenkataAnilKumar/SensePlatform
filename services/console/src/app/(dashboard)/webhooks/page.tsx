"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, Send, Webhook } from "lucide-react";
import { Header } from "@/components/layout/header";
import { webhooksApi, type Webhook as WebhookType } from "@/lib/api";

const EVENT_OPTIONS = [
  "*", "room.created", "room.ended",
  "room.participant_joined", "room.participant_left",
  "agent.started", "agent.stopped",
  "lens.event", "call.escalated",
];

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState<WebhookType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState("*");
  const [creating, setCreating] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, boolean>>({});

  async function load() {
    setLoading(true);
    try { setWebhooks(await webhooksApi.list()); }
    catch { setWebhooks([]); }
    finally { setLoading(false); }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const wh = await webhooksApi.create(url, events);
      setWebhooks((prev) => [...prev, wh]);
      setUrl(""); setEvents("*"); setShowCreate(false);
    } finally { setCreating(false); }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this webhook?")) return;
    await webhooksApi.delete(id);
    setWebhooks((prev) => prev.filter((w) => w.id !== id));
  }

  async function handleTest(id: string) {
    const result = await webhooksApi.test(id);
    setTestResults((prev) => ({ ...prev, [id]: result.delivered }));
    setTimeout(() => setTestResults((prev) => { const n = { ...prev }; delete n[id]; return n; }), 3000);
  }

  useEffect(() => { void load(); }, []);

  return (
    <div>
      <Header
        title="Webhooks"
        description="Receive signed event notifications from Sense Platform."
        onRefresh={load}
        action={
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 bg-sense-600 hover:bg-sense-700 text-white text-sm rounded-lg transition-colors">
            <Plus className="w-4 h-4" /> Add Webhook
          </button>
        }
      />

      {showCreate && (
        <div className="mb-4 bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-medium text-gray-900 mb-3">Register Webhook</h3>
          <form onSubmit={handleCreate} className="space-y-3">
            <input value={url} onChange={(e) => setUrl(e.target.value)}
              placeholder="https://your-server.com/webhooks/sense"
              type="url" required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-sense-500" />
            <select value={events} onChange={(e) => setEvents(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-sense-500">
              {EVENT_OPTIONS.map((ev) => (
                <option key={ev} value={ev}>{ev === "*" ? "All events (*)" : ev}</option>
              ))}
            </select>
            <div className="flex gap-2">
              <button type="submit" disabled={creating}
                className="px-4 py-2 bg-sense-600 text-white text-sm rounded-lg hover:bg-sense-700 disabled:opacity-50">
                {creating ? "Saving…" : "Save"}
              </button>
              <button type="button" onClick={() => setShowCreate(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200">
        {loading ? (
          <div className="py-12 text-center text-sm text-gray-400">Loading…</div>
        ) : webhooks.length === 0 ? (
          <div className="py-12 text-center">
            <Webhook className="w-8 h-8 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">No webhooks registered.</p>
            <p className="text-xs text-gray-400 mt-1">
              Webhooks are signed with HMAC-SHA256 — verify using <code className="bg-gray-100 px-1 rounded">X-Sense-Signature</code>
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">URL</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Events</th>
                <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody>
              {webhooks.map((wh) => (
                <tr key={wh.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3 font-mono text-xs text-gray-700 max-w-xs truncate">{wh.url}</td>
                  <td className="px-5 py-3">
                    <span className="text-xs bg-gray-100 px-2 py-0.5 rounded font-medium text-gray-600">{wh.events}</span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => handleTest(wh.id)}
                        className="flex items-center gap-1 px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs rounded-md">
                        <Send className="w-3 h-3" />
                        {testResults[wh.id] === true ? "✓ Sent" : testResults[wh.id] === false ? "✗ Failed" : "Test"}
                      </button>
                      <button onClick={() => handleDelete(wh.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
