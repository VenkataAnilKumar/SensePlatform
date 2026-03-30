import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_GATE_URL: process.env.NEXT_PUBLIC_GATE_URL ?? "http://localhost:3000",
    NEXT_PUBLIC_WIRE_URL: process.env.NEXT_PUBLIC_WIRE_URL ?? "ws://localhost:3001",
  },
};

export default nextConfig;
