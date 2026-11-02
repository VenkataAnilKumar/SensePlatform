# Customer Demo Script (15 minutes)

What this demo shows is what has been verified working: tenant/API-key flow, a live camera in a WebRTC room, an AI agent joining it, **vision lenses streaming events to the browser in real time**, and room chat. It does **not** show a spoken conversation unless you have configured and tested Deepgram + ElevenLabs keys.

## Before the call

- [ ] Run the stack on the machine you will present from (`docker compose up -d --build`) and wait for the health checks.
- [ ] Present from `http://localhost:4000` (camera works on localhost) or from an HTTPS deployment — see [self-hosting](self-hosting.md).
- [ ] Create your tenant and save the API key (it is shown once).
- [ ] Do one full dry run; the **first** agent start is slower while YOLO weights load.
- [ ] Have a recording of a successful run as a fallback.

## Script

**1. The pitch (2 min).** "Build video, voice and vision-AI apps on infrastructure you own — no per-minute cloud bill, no data leaving your servers."

**2. Developer experience (3 min).** In a terminal:

```bash
curl -s -X POST localhost:3000/tenants -H 'Content-Type: application/json' \
  -d '{"name":"Demo Co","slug":"demo","email":"demo@example.com"}'   # returns api_key once
```

Sign in to the Console (`localhost:4000`) with the key. Show **API Keys** — only prefixes are listed; raw keys are never stored.

**3. Live demo (6 min).** Open **Live Demo**.
1. Room `demo`, tick **Mood** and **Face**, press **Start demo**, allow the camera.
2. Point out *AI agent in room* — a server-side agent has joined the WebRTC room.
3. Within a few seconds, **vision events** appear: face count / occupancy, mood estimate, each with the sentence that is injected into the agent's LLM context.
4. Bring a second person into frame — FaceLens flags *multiple faces*.
5. Send a chat message to show real-time messaging in the same room.
6. Press **Stop demo** — the agent leaves and is cleaned up.

**4. Use cases (2 min).** Contact center (adapt tone to frustration), sales coach, fitness form correction, telehealth presence, security monitoring — see `examples/`.

**5. Self-hosting and next steps (2 min).** One `docker compose up`, your servers, Apache-2.0. Walk through the [production checklist](self-hosting.md#6-production-checklist).

## Say this, not that

| Say | Don't say |
|-----|-----------|
| "Mood is estimated from body pose — a prototype signal." | "It reads emotions accurately." |
| "Vision events drive the agent's context in real time." | "The agent holds a voice conversation" (unless you tested it) |
| "Agents currently send audio; video from the agent is on the roadmap." | "Agents appear on camera." |

## If something breaks

| Symptom | Fix |
|---------|-----|
| "Start" returns an error | The message shows the reason (e.g. Relay unreachable); check `docker compose logs sense-mind` |
| No camera prompt | Not on HTTPS/localhost |
| No events after 20 s | Make sure a person is in frame; first run downloads YOLO weights (needs internet) |
