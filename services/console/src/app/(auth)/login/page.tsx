"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_GATE_URL}/tenants/me`,
        { headers: { "X-API-Key": apiKey } },
      );

      if (!resp.ok) {
        setError("Invalid API key. Check your Sense Gate credentials.");
        return;
      }

      // Store key in cookie for subsequent API calls
      document.cookie = `sense_api_key=${apiKey}; path=/; max-age=86400; SameSite=Strict`;
      router.push("/dashboard");
    } catch {
      setError("Cannot reach Sense Gate. Is it running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sense-950 to-sense-800">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <div className="w-10 h-10 rounded-xl bg-sense-500 flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-white">Sense Console</span>
          </div>
          <p className="text-sense-300 text-sm">Developer Dashboard · Sense Platform</p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-1">Sign in to your project</h1>
          <p className="text-sm text-gray-500 mb-6">
            Enter your API key from{" "}
            <code className="bg-gray-100 px-1 rounded text-xs">sense-gate</code>
          </p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Key
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk_live_..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
                           focus:outline-none focus:ring-2 focus:ring-sense-500 focus:border-transparent"
                required
              />
              <p className="text-xs text-gray-400 mt-1">
                Found in your tenant settings or auto-generated on first run.
              </p>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !apiKey}
              className="w-full bg-sense-600 hover:bg-sense-700 disabled:opacity-50
                         text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
            >
              {loading ? "Connecting…" : "Sign in"}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-100 text-center">
            <p className="text-xs text-gray-400">
              Don&apos;t have a key?{" "}
              <code className="bg-gray-100 px-1 rounded">docker compose up</code>{" "}
              and create a tenant via the API.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
