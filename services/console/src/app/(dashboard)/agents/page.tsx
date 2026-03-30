"use client";

import { useEffect, useState } from "react";
import { Bot, Play, Square, Eye } from "lucide-react";
import { Header } from "@/components/layout/header";
import { roomsApi, agentsApi, type Room } from "@/lib/api";

const LENS_OPTIONS = ["MoodLens", "PoseLens", "GuardLens", "FaceLens"];

export default function AgentsPage() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRoom, setSelectedRoom] = useState("");
  const [selectedLenses, setSelectedLenses] = useState<string[]>(["MoodLens"]);
  const [launching, setLaunching] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try { setRooms(await roomsApi.list()); }
    catch { setRooms([]); }
    finally { setLoading(false); }
  }

  async function handleStart() {
    if (!selectedRoom) return;
    setLaunching(true);
    setResult(null);
    try {
      const res = await agentsApi.start(selectedRoom, selectedLenses);
      setResult(`Agent launched in "${selectedRoom}" — status: ${res.status}`);
    } catch (e) {
      setResult(`Error: ${(e as Error).message}`);
    } finally {
      setLaunching(false);
    }
  }

  function toggleLens(lens: string) {
    setSelectedLenses((prev) =>
      prev.includes(lens) ? prev.filter((l) => l !== lens) : [...prev, lens]
    );
  }

  useEffect(() => { void load(); }, []);

  return (
    <div>
      <Header
        title="Agents"
        description="Launch and manage Sense Mind AI agents in your rooms."
        onRefresh={load}
      />

      {/* Launch panel */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Bot className="w-4 h-4 text-sense-600" /> Launch Agent
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Room</label>
            <select
              value={selectedRoom}
              onChange={(e) => setSelectedRoom(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-sense-500"
            >
              <option value="">Select a room…</option>
              {rooms.map((r) => (
                <option key={r.room_id} value={r.room_id}>
                  {r.room_id} ({r.num_participants} participants)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Vision Lenses</label>
            <div className="flex flex-wrap gap-2">
              {LENS_OPTIONS.map((lens) => (
                <button
                  key={lens}
                  onClick={() => toggleLens(lens)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    selectedLenses.includes(lens)
                      ? "bg-sense-600 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  <Eye className="w-3 h-3 inline mr-1" />
                  {lens}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button
          onClick={handleStart}
          disabled={!selectedRoom || launching}
          className="flex items-center gap-2 px-4 py-2 bg-sense-600 hover:bg-sense-700
                     text-white text-sm rounded-lg transition-colors disabled:opacity-50"
        >
          <Play className="w-4 h-4" />
          {launching ? "Launching…" : "Launch Agent"}
        </button>

        {result && (
          <div className={`mt-3 px-3 py-2 rounded-lg text-sm ${
            result.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"
          }`}>
            {result}
          </div>
        )}
      </div>

      {/* Rooms status */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-900">Room Status</h2>
        </div>
        {loading ? (
          <div className="py-10 text-center text-sm text-gray-400">Loading…</div>
        ) : rooms.length === 0 ? (
          <div className="py-10 text-center">
            <Bot className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No rooms found. Create a room first.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Room</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Participants</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((room) => (
                <tr key={room.room_id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3 font-medium text-gray-900">{room.room_id}</td>
                  <td className="px-5 py-3 text-gray-700">{room.num_participants}</td>
                  <td className="px-5 py-3">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                      idle
                    </span>
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
