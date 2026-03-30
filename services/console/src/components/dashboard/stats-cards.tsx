"use client";

import { Video, Bot, Zap, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCard {
  label: string;
  value: string | number;
  change?: string;
  positive?: boolean;
  icon: React.ElementType;
  color: string;
}

function StatCard({ label, value, change, positive, icon: Icon, color }: StatCard) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
          {change && (
            <p className={cn("text-xs mt-1", positive ? "text-green-600" : "text-red-500")}>
              {positive ? "↑" : "↓"} {change}
            </p>
          )}
        </div>
        <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", color)}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );
}

interface StatsCardsProps {
  rooms: number;
  agents: number;
  apiCalls: number;
  uptime: string;
}

export function StatsCards({ rooms, agents, apiCalls, uptime }: StatsCardsProps) {
  const cards: StatCard[] = [
    { label: "Active Rooms",  value: rooms,    icon: Video,     color: "bg-blue-500" },
    { label: "Running Agents", value: agents,  icon: Bot,       color: "bg-sense-600" },
    { label: "API Calls Today", value: apiCalls, icon: Zap,     color: "bg-amber-500" },
    { label: "Gate Uptime",   value: uptime,   icon: Activity,  color: "bg-green-500" },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {cards.map((card) => (
        <StatCard key={card.label} {...card} />
      ))}
    </div>
  );
}
