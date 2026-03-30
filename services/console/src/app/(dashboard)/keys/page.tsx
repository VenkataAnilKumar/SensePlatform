"use client";

import { useEffect, useState } from "react";
import { Plus, Copy, Trash2, Key } from "lucide-react";
import { Header } from "@/components/layout/header";
import { apiKeysApi, type ApiKey } from "@/lib/api";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try { setKeys(await apiKeysApi.list()); }
    catch { setKeys([]); }
    finally { setLoading(false); }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const key = await apiKeysApi.create(newName || "New Key");
      setKeys((prev) => [...prev, key]);
      setNewName("");
      setShowCreate(false);
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id: string) {
    if (!confirm("Revoke this API key? This cannot be undone.")) return;
    await apiKeysApi.revoke(id);
    setKeys((prev) => prev.filter((k) => k.id !== id));
  }

  async function handleCopy(key: string, id: string) {
    await navigator.clipboard.writeText(key);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  useEffect(() => { void load(); }, []);

  return (
    <div>
      <Header
        title="API Keys"
        description="Manage authentication keys for your Sense Platform integration."
        onRefresh={load}
        action={
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 bg-sense-600 hover:bg-sense-700
                       text-white text-sm rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" /> New Key
          </button>
        }
      />

      {/* Create key form */}
      {showCreate && (
        <div className="mb-4 bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-medium text-gray-900 mb-3">Create API Key</h3>
          <form onSubmit={handleCreate} className="flex gap-3">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Key name (e.g. Production)"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm
                         focus:outline-none focus:ring-2 focus:ring-sense-500"
            />
            <button
              type="submit"
              disabled={creating}
              className="px-4 py-2 bg-sense-600 text-white text-sm rounded-lg
                         hover:bg-sense-700 disabled:opacity-50 transition-colors"
            >
              {creating ? "Creating…" : "Create"}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200"
            >
              Cancel
            </button>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200">
        {loading ? (
          <div className="py-12 text-center text-sm text-gray-400">Loading…</div>
        ) : keys.length === 0 ? (
          <div className="py-12 text-center">
            <Key className="w-8 h-8 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">No API keys yet.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Name</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Key</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Type</th>
                <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3 font-medium text-gray-900">{k.name}</td>
                  <td className="px-5 py-3">
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-700">
                      {k.key.slice(0, 16)}…
                    </code>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                      ${k.is_test ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"}`}>
                      {k.is_test ? "test" : "live"}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleCopy(k.key, k.id)}
                        className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                        title="Copy key"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                      {copiedId === k.id && (
                        <span className="text-xs text-green-600">Copied!</span>
                      )}
                      <button
                        onClick={() => handleRevoke(k.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                        title="Revoke key"
                      >
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
