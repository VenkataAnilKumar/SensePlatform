"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { roomsApi, agentsApi, usageApi, healthApi, type Room } from "@/lib/api";

export default function DashboardPage() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [apiCalls, setApiCalls] = useState(0);
  const [uptime, setUptime] = useState("—");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [roomList, usage, health] = await Promise.allSettled([
        roomsApi.list(),
        usageApi.get(),
        healthApi.check(),
      ]);

      if (roomList.status === "fulfilled") setRooms(roomList.value);

      if (usage.status === "fulfilled") {
        const apiCallStat = usage.value.summary.find((s) => s.event_type === "api_call");
        setApiCalls(apiCallStat?.count ?? 0);
      }

      if (health.status === "fulfilled") setUptime("Online");
      else setUptime("Offline");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const activeRooms = rooms.filter((r) => r.num_participants > 0);

  return (
    <div>
      <Header
        title="Overview"
        description="Real-time status of your Sense Platform deployment."
        onRefresh={load}
      />

      <StatsCards
        rooms={activeRooms.length}
        agents={0}
        apiCalls={apiCalls}
        uptime={uptime}
      />

      {/* Active rooms table */}
      <div className="mt-6 bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-900">Active Rooms</h2>
        </div>
        {loading ? (
          <div className="px-5 py-8 text-center text-sm text-gray-400">Loading…</div>
        ) : activeRooms.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <p className="text-sm text-gray-500">No active rooms.</p>
            <p className="text-xs text-gray-400 mt-1">
              Rooms appear here when participants join via Sense Relay.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Room</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Participants</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Started</th>
              </tr>
            </thead>
            <tbody>
              {activeRooms.map((room) => (
                <tr key={room.room_id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3 font-medium text-gray-900">{room.room_id}</td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-green-400" />
                      {room.num_participants}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {new Date(room.creation_time * 1000).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Quick start */}
      <div className="mt-6 bg-sense-950 rounded-xl p-6 text-white">
        <h2 className="font-semibold mb-1">Quick Start</h2>
        <p className="text-sense-300 text-sm mb-4">Get a room running in 3 steps.</p>
        <div className="space-y-2 font-mono text-xs bg-black/30 rounded-lg p-4">
          <p><span className="text-sense-400"># 1. Create a room and get a relay token</span></p>
          <p>curl -X POST http://localhost:3000/rooms/my-room/join \</p>
          <p>  -H &quot;X-API-Key: sk_live_...&quot; \</p>
          <p>  -d {'\'{"user_id": "alice"}\''}</p>
          <p className="mt-2"><span className="text-sense-400"># 2. Start an AI agent in the room</span></p>
          <p>curl -X POST http://localhost:3000/agents/start \</p>
          <p>  -H &quot;X-API-Key: sk_live_...&quot; \</p>
          <p>  -d {'\'{"room_id": "my-room", "lenses": ["MoodLens"]}\''}</p>
        </div>
      </div>
    </div>
  );
}
