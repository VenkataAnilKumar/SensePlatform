"use client";

import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { Header } from "@/components/layout/header";
import { usageApi, type UsageSummary } from "@/lib/api";

const UNIT_LABELS: Record<string, string> = {
  count: "calls",
  minutes: "min",
  seconds: "sec",
  characters: "chars",
};

export default function UsagePage() {
  const [summary, setSummary] = useState<UsageSummary[]>([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(true);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await usageApi.get(fromDate || undefined, toDate || undefined);
      setSummary(data.summary);
      setTotalRecords(data.total_records);
    } catch {
      setSummary([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const maxQty = Math.max(...summary.map((s) => s.total_quantity), 1);

  return (
    <div>
      <Header
        title="Usage"
        description="API calls, room minutes, agent minutes, and STT/TTS consumption."
        onRefresh={load}
      />

      {/* Date filter */}
      <div className="flex items-center gap-3 mb-6">
        <div>
          <label className="block text-xs text-gray-500 mb-1">From</label>
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-sense-500" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">To</label>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-sense-500" />
        </div>
        <button onClick={load}
          className="mt-5 px-4 py-1.5 bg-sense-600 text-white text-sm rounded-lg hover:bg-sense-700">
          Apply
        </button>
      </div>

      {/* Summary cards */}
      {!loading && summary.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {summary.slice(0, 4).map((s) => (
            <div key={s.event_type} className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500 truncate">
                {s.event_type.replace(/_/g, " ")}
              </p>
              <p className="text-2xl font-semibold text-gray-900 mt-1">
                {s.total_quantity.toLocaleString()}
              </p>
              <p className="text-xs text-gray-400">
                {UNIT_LABELS[s.unit] ?? s.unit} · {s.count} events
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Bar chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">Usage by Event Type</h2>

        {loading ? (
          <div className="py-10 text-center text-sm text-gray-400">Loading…</div>
        ) : summary.length === 0 ? (
          <div className="py-10 text-center">
            <BarChart3 className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No usage records found.</p>
            <p className="text-xs text-gray-400 mt-1">
              Usage is recorded automatically as you make API calls and run agents.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {summary.map((s) => {
              const pct = (s.total_quantity / maxQty) * 100;
              return (
                <div key={s.event_type}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-gray-700 font-medium">
                      {s.event_type.replace(/_/g, " ")}
                    </span>
                    <span className="text-gray-500">
                      {s.total_quantity.toLocaleString()} {UNIT_LABELS[s.unit] ?? s.unit}
                    </span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-sense-500 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {totalRecords > 0 && (
          <p className="text-xs text-gray-400 mt-4">{totalRecords.toLocaleString()} total records</p>
        )}
      </div>
    </div>
  );
}
