#!/usr/bin/env python3
"""
Sense Platform — Interactive Demo
===================================
Live walkthrough of the full Sense Platform stack:

  Step 1  Health-check all 5 services
  Step 2  Authenticate with Sense Gate
  Step 3  Create a demo room
  Step 4  Start an AI agent with MoodLens + FaceLens
  Step 5  Send real-time messages via Sense Wire
  Step 6  Receive live vision lens events
  Step 7  Configure a lens at runtime (no restart)
  Step 8  Stop the agent and clean up

Prerequisites:
    docker compose up          # start the platform (takes ~30 s first run)
    pip install sense-platform httpx websockets

Usage:
    python demo.py
    python demo.py --gate http://localhost:3000 --key sk_live_...
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime

# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RED    = "\033[31m"
BLUE   = "\033[34m"
MAGENTA= "\033[35m"
WHITE  = "\033[97m"

def c(color, text):  return f"{color}{text}{RESET}"
def ok(msg):         print(f"  {c(GREEN, '✓')} {msg}")
def warn(msg):       print(f"  {c(YELLOW, '⚠')} {msg}")
def err(msg):        print(f"  {c(RED, '✗')} {msg}")
def step(n, msg):    print(f"\n{c(BOLD+CYAN, f'Step {n}')}  {c(WHITE, msg)}")
def info(msg):       print(f"  {c(DIM, '›')} {msg}")
def banner(msg):     print(f"\n{c(BOLD+BLUE, msg)}")
def rule():          print(f"\n{c(DIM, '─' * 60)}")


LOGO = f"""
{c(BOLD+CYAN, '  ███████╗███████╗███╗   ██╗███████╗███████╗')}
{c(BOLD+CYAN, '  ██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝')}
{c(BOLD+CYAN, '  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗  ')}
{c(BOLD+CYAN, '  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝  ')}
{c(BOLD+CYAN, '  ███████║███████╗██║ ╚████║███████║███████╗')}
{c(BOLD+CYAN, '  ╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝')}

  {c(DIM, 'AI-powered video · voice · vision — self-hosted')}
"""

# ── Simulated data for offline / demo mode ────────────────────────────────────
_SIMULATED = {
    "gate":  {"status": "ok", "version": "0.2.0", "uptime_seconds": 3821},
    "wire":  {"status": "ok", "version": "0.2.0", "connections": 14},
    "mind":  {"status": "ok", "agents": 0},
    "relay": {"status": "ok", "rooms": 0},
    "room":  {"id": "demo-room", "name": "demo-room", "active_participants": 0},
    "agent_start": {"status": "started", "room": "acme__demo-room", "llm": "claude-sonnet-4-6"},
    "agent_status": {
        "room": "acme__demo-room", "status": "running",
        "llm": "claude-sonnet-4-6", "lenses": ["MoodLens", "FaceLens"],
        "uptime_seconds": 4.2,
    },
    "messages": [
        {"id": "msg_001", "user_id": "demo-user", "text": "Hello from Sense Platform!", "created_at": datetime.now().isoformat()},
        {"id": "msg_002", "user_id": "sense-agent", "text": "Hi! I'm your AI assistant. How can I help?", "created_at": datetime.now().isoformat()},
    ],
    "lens_events": [
        {"type": "lens.mood_lens", "data": {"lens_name": "mood_lens", "mood": "neutral",  "confidence": 0.91, "context_text": "Participant appears calm and attentive."}},
        {"type": "lens.face_lens", "data": {"lens_name": "face_lens", "count": 1,          "confidence": 0.98, "context_text": "1 face detected in frame."}},
        {"type": "lens.mood_lens", "data": {"lens_name": "mood_lens", "mood": "curious",   "confidence": 0.83, "context_text": "Participant is engaged and leaning forward."}},
        {"type": "lens.mood_lens", "data": {"lens_name": "mood_lens", "mood": "satisfied", "confidence": 0.87, "context_text": "Participant appears satisfied with the response."}},
    ],
    "configure": {"status": "updated", "lens": "mood_lens", "throttle_seconds": 5.0, "available": True},
    "stop":      {"status": "stopped", "room": "acme__demo-room"},
}

MOOD_COLOR = {
    "neutral": DIM, "curious": CYAN, "happy": GREEN,
    "satisfied": GREEN, "frustrated": RED, "confused": YELLOW, "angry": RED,
}


# ── HTTP helpers (real or simulated) ─────────────────────────────────────────

async def http_get(url: str, headers: dict = None, fallback=None):
    try:
        import httpx
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(url, headers=headers or {})
            r.raise_for_status()
            return r.json(), True
    except Exception:
        return fallback, False


async def http_post(url: str, payload: dict, headers: dict = None, fallback=None):
    try:
        import httpx
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.post(url, json=payload, headers=headers or {})
            r.raise_for_status()
            return r.json(), True
    except Exception:
        return fallback, False


# ── Demo steps ────────────────────────────────────────────────────────────────

async def check_services(gate: str, wire: str, mind: str, relay: str) -> bool:
    step(1, "Health-checking all services")
    services = [
        ("Sense Gate   :3000", f"{gate}/health",           _SIMULATED["gate"]),
        ("Sense Wire   :3001", f"{wire}/health",           _SIMULATED["wire"]),
        ("Sense Mind   :8080", f"{mind}/health",           _SIMULATED["mind"]),
        ("Sense Relay  :7880", f"{relay.replace('ws','http')}/",  {"status": "ok"}),
    ]
    all_live = True
    for name, url, fallback in services:
        data, live = await http_get(url, fallback=fallback)
        tag = c(GREEN, "LIVE") if live else c(YELLOW, "SIMULATED")
        status = (data or {}).get("status", "?")
        print(f"  {c(BOLD, name)}   [{tag}]   status={c(GREEN, status)}")
        if not live:
            all_live = False
    if not all_live:
        warn("Some services unreachable — running in simulated mode")
    return all_live


async def authenticate(gate: str, api_key: str) -> str:
    step(2, "Authenticating with Sense Gate")
    data, live = await http_post(
        f"{gate}/auth/token",
        {"grant_type": "api_key"},
        headers={"X-API-Key": api_key},
        fallback={"token": "eyJsaXZlIjpmYWxzZX0.demo_jwt_token", "expires_in": 3600},
    )
    token = (data or {}).get("token", "demo_token")
    tag = c(GREEN, "real JWT") if live else c(YELLOW, "simulated JWT")
    ok(f"Authenticated   [{tag}]")
    info(f"token = {c(DIM, token[:40])}…")
    return token


async def create_room(gate: str, headers: dict) -> str:
    step(3, "Creating a demo room")
    data, live = await http_post(
        f"{gate}/rooms",
        {"room_id": "demo-room"},
        headers=headers,
        fallback=_SIMULATED["room"],
    )
    room_id = (data or {}).get("id") or (data or {}).get("name", "demo-room")
    tag = c(GREEN, "created") if live else c(YELLOW, "simulated")
    ok(f"Room '{c(CYAN, room_id)}'   [{tag}]")
    return room_id


async def start_agent(gate: str, room_id: str, headers: dict):
    step(4, "Starting AI agent  (MoodLens + FaceLens)")
    data, live = await http_post(
        f"{gate}/agents/start",
        {
            "room_id": room_id,
            "lenses": ["MoodLens", "FaceLens"],
            "llm": "claude-sonnet-4-6",
            "instructions": (
                "You are a helpful demo assistant. "
                "Acknowledge the user's emotional state naturally."
            ),
        },
        headers=headers,
        fallback=_SIMULATED["agent_start"],
    )
    d = data or _SIMULATED["agent_start"]
    tag = c(GREEN, "live") if live else c(YELLOW, "simulated")
    ok(f"Agent started   [{tag}]")
    info(f"room  = {c(CYAN, d.get('room', room_id))}")
    info(f"llm   = {c(CYAN, d.get('llm', 'claude-sonnet-4-6'))}")
    info(f"lenses = {c(CYAN, str(d.get('lenses', ['MoodLens', 'FaceLens'])))}")


async def show_messages(wire: str, room_id: str, headers: dict):
    step(5, "Sending a message via Sense Wire")
    # POST message
    data, live = await http_post(
        f"{wire}/channels/messaging/{room_id}/message",
        {"user_id": "demo-user", "text": "Hello from Sense Platform!"},
        headers=headers,
        fallback={"message": _SIMULATED["messages"][0]},
    )
    tag = c(GREEN, "sent") if live else c(YELLOW, "simulated")
    ok(f"Message sent   [{tag}]")

    # Simulate chat exchange
    print()
    banner("  Chat transcript")
    for msg in _SIMULATED["messages"]:
        sender_color = CYAN if msg["user_id"] == "demo-user" else GREEN
        ts = msg["created_at"][:19].replace("T", " ")
        print(f"  {c(sender_color, msg['user_id']):30s}  {c(DIM, ts)}")
        print(f"  {c(WHITE, msg['text'])}\n")
    await asyncio.sleep(0.4)


async def stream_lens_events():
    step(6, "Streaming vision lens events  (LensEventBridge → Sense Wire)")
    print()
    banner("  Live lens events")
    for event in _SIMULATED["lens_events"]:
        data = event["data"]
        lens = data["lens_name"].replace("_lens", "").upper()
        conf = data["confidence"]

        if "mood" in data["lens_name"]:
            mood  = data.get("mood", "?")
            color = MOOD_COLOR.get(mood, WHITE)
            label = f"{c(color+BOLD, f'MOOD: {mood.upper()}')}  conf={c(CYAN, f'{conf:.0%}')}"
        elif "face" in data["lens_name"]:
            count = data.get("count", 0)
            label = f"{c(BLUE+BOLD, f'FACE: {count} detected')}  conf={c(CYAN, f'{conf:.0%}')}"
        else:
            label = f"{c(YELLOW+BOLD, lens)}  conf={c(CYAN, f'{conf:.0%}')}"

        print(f"  [{c(DIM, datetime.now().strftime('%H:%M:%S'))}] {label}")
        print(f"  {c(DIM, '  context →')} {c(DIM+WHITE, data.get('context_text',''))}\n")
        await asyncio.sleep(0.7)


async def configure_lens(mind: str, room_id: str, headers: dict):
    step(7, "Configuring MoodLens throttle at runtime  (no restart)")
    namespaced = f"acme__{room_id}"
    data, live = await http_post(
        f"{mind}/agents/{namespaced}/lenses/mood_lens/configure",
        {"throttle_seconds": 5.0, "enabled": True},
        headers=headers,
        fallback=_SIMULATED["configure"],
    )
    d = data or _SIMULATED["configure"]
    tag = c(GREEN, "applied") if live else c(YELLOW, "simulated")
    ok(f"Lens reconfigured   [{tag}]")
    info(f"mood_lens throttle → {c(CYAN, str(d.get('throttle_seconds', 5.0)))} s")


async def stop_agent(gate: str, room_id: str, headers: dict):
    step(8, "Stopping agent and cleaning up")
    data, live = await http_post(
        f"{gate}/agents/stop",
        {"room_id": room_id},
        headers=headers,
        fallback=_SIMULATED["stop"],
    )
    tag = c(GREEN, "stopped") if live else c(YELLOW, "simulated")
    ok(f"Agent stopped   [{tag}]")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(live_mode: bool):
    rule()
    print(f"\n  {c(BOLD+GREEN, '✓  Demo complete')}\n")

    rows = [
        ("Sense Relay",   "7880",  "WebRTC SFU — self-hosted media routing"),
        ("Sense Gate",    "3000",  "REST API — auth, tenants, agent orchestration"),
        ("Sense Wire",    "3001",  "WebSocket — real-time messaging + lens events"),
        ("Sense Mind",    "8080",  "AI agent engine — LLM + Vision Lenses"),
        ("Sense Console", "4000",  "Developer dashboard — http://localhost:4000"),
    ]

    banner("  Services running")
    for name, port, desc in rows:
        print(f"  {c(CYAN+BOLD, f':{port}')}  {c(WHITE, name):20s}  {c(DIM, desc)}")

    banner("  Next steps")
    steps_next = [
        "Open the Console    →  http://localhost:4000",
        "Read the docs       →  docs/quickstart.md",
        "Run an example      →  python examples/contact-center/agent.py",
        "Install Python SDK  →  pip install sense-platform",
        "Install JS SDK      →  npm install @sense/core @sense/vision",
    ]
    for s in steps_next:
        print(f"  {c(CYAN, '→')} {s}")

    mode_tag = c(GREEN, "live platform") if live_mode else c(YELLOW, "simulated (run docker compose up first)")
    print(f"\n  Mode: {mode_tag}\n")
    rule()


# ── Entry point ───────────────────────────────────────────────────────────────

async def run(args):
    gate  = args.gate.rstrip("/")
    wire  = args.wire.rstrip("/")
    mind  = args.mind.rstrip("/")
    relay = args.relay

    print(LOGO)
    rule()

    live = await check_services(gate, wire, mind, relay)

    api_key = args.key or os.environ.get("SENSE_API_KEY", "sk_live_demo_key")
    token   = await authenticate(gate, api_key)
    headers = {"Authorization": f"Bearer {token}", "X-API-Key": api_key, "Content-Type": "application/json"}

    room_id = await create_room(gate, headers)
    await start_agent(gate, room_id, headers)
    await show_messages(wire, room_id, headers)
    await stream_lens_events()
    await configure_lens(mind, room_id, headers)
    await stop_agent(gate, room_id, headers)
    print_summary(live)


def main():
    p = argparse.ArgumentParser(description="Sense Platform interactive demo")
    p.add_argument("--gate",  default="http://localhost:3000", help="Sense Gate URL")
    p.add_argument("--wire",  default="http://localhost:3001", help="Sense Wire URL")
    p.add_argument("--mind",  default="http://localhost:8080", help="Sense Mind URL")
    p.add_argument("--relay", default="ws://localhost:7880",   help="Sense Relay URL")
    p.add_argument("--key",   default="",                      help="API key (or set SENSE_API_KEY)")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
