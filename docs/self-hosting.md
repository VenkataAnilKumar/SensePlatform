# Self-Hosting Guide

How to run Sense Platform on your own server. Everything runs from `docker compose`; no cloud service is required except the LLM / speech providers you choose.

> **Status:** the services and the vision pipeline were verified end to end in a development sandbox. The Docker images are built by the CI smoke test; validate a fresh deployment (section 7) before putting customers on it.

## 1. What you need

| | Minimum |
|--|--|
| Host | Linux, 4 vCPU, 8 GB RAM (the Mind image bundles PyTorch; YOLO runs on CPU) |
| Software | Docker with Compose v2 |
| Network | A domain name and TLS certificate if anything is reached from outside `localhost` |
| Keys | Anthropic (LLM). Optional: Deepgram (STT), ElevenLabs (TTS) for spoken conversation |

## 2. Install

```bash
git clone https://github.com/VenkataAnilKumar/SensePlatform
cd SensePlatform
cp .env.example .env      # then edit — see section 3
docker compose up -d --build
```

Check health: `curl localhost:3000/health`, `:3001/health`, `:8080/health`.

## 3. Configuration

Set these in `.env` (compose reads it):

| Variable | Purpose |
|----------|---------|
| `SENSE_ENV` | `production` makes Gate, Wire and Mind **refuse to start with default secrets** and disables open tenant creation |
| `SENSE_ADMIN_KEY` | Required `X-Admin-Key` header for `POST /tenants` in production |
| `SENSE_JWT_SECRET` | Signs user tokens (shared by Gate and Wire) |
| `SENSE_RELAY_SECRET` | LiveKit API secret (Relay, Gate and Mind) |
| `SENSE_SERVICE_KEY` | Shared secret for Mind → Wire lens events |
| `SENSE_PUBLIC_RELAY_URL` | Address **browsers** use for WebRTC, e.g. `wss://relay.example.com` |
| `SENSE_CORS_ORIGINS` | Browser origins allowed to call Gate (comma-separated) |
| `SENSE_PUBLIC_GATE_URL`, `SENSE_PUBLIC_WIRE_URL` | Addresses the Console uses; baked in at build time — rebuild the Console after changing |
| `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY` | Provider keys; STT/TTS are enabled automatically when their key is set |

Generate strong secrets with `openssl rand -hex 32`.

## 4. TLS and reverse proxy

Browsers only allow camera and microphone on HTTPS (or `localhost`), and a page served over HTTPS cannot open plain `ws://` sockets. Put a reverse proxy in front and expose:

| Public host | Proxies to | Notes |
|-------------|-----------|-------|
| `console.example.com` | `localhost:4000` | |
| `api.example.com` | `localhost:3000` | Gate REST |
| `wire.example.com` | `localhost:3001` | must allow WebSocket upgrade |
| `relay.example.com` | `localhost:7880` | LiveKit signalling over `wss://` |

Example with [Caddy](https://caddyserver.com) (automatic certificates):

```
console.example.com { reverse_proxy localhost:4000 }
api.example.com     { reverse_proxy localhost:3000 }
wire.example.com    { reverse_proxy localhost:3001 }
relay.example.com   { reverse_proxy localhost:7880 }
```

Then set `SENSE_PUBLIC_RELAY_URL=wss://relay.example.com`, `SENSE_PUBLIC_GATE_URL=https://api.example.com`, `SENSE_PUBLIC_WIRE_URL=wss://wire.example.com` and rebuild: `docker compose up -d --build`.

Also restrict CORS on Gate: set `SENSE_CORS_ORIGINS=https://console.example.com` in `.env` (default `*`, which disables credentialed requests).

**Media ports.** WebRTC media does not go through the proxy. Open `7881/tcp` and the UDP range `50000-50020` on your firewall. Compose publishes only 21 UDP ports, which limits concurrent participants — widen the range in `docker-compose.yml` (and keep it within the `rtc` range in `services/relay/sense-relay.yaml`) for larger deployments.

## 5. Operations

**Backups.** State lives in Postgres (`sense_gate`, `sense_wire`). Redis holds only ephemeral room/pub-sub state.

```bash
docker compose exec postgres pg_dump -U sense sense_gate > gate-$(date +%F).sql
docker compose exec postgres pg_dump -U sense sense_wire > wire-$(date +%F).sql
```

**Upgrades.** `git pull && docker compose up -d --build`. Gate applies its Alembic migrations on start; Wire creates missing tables on start. Take a backup first.

**Logs.** `docker compose logs -f sense-gate sense-wire sense-mind`.

**Scaling.**
- *Wire* can run several instances: events fan out through Redis pub/sub.
- *Gate* is stateless apart from Postgres/Redis and can run behind a load balancer.
- *Mind* holds running agents in memory and Gate talks to a single `MIND_URL`; scale it vertically for now. Vision inference is CPU-bound — budget roughly one core per few active lenses.

## 6. Production checklist

- [ ] `SENSE_ENV=production`
- [ ] `SENSE_ADMIN_KEY`, `SENSE_JWT_SECRET`, `SENSE_RELAY_SECRET`, `SENSE_SERVICE_KEY` set to random values
- [ ] TLS in front of Console, Gate, Wire and Relay; `SENSE_PUBLIC_*` URLs use `https`/`wss`
- [ ] `SENSE_CORS_ORIGINS` limited to your Console origin
- [ ] Postgres port `5432` and Redis `6379` not exposed publicly (remove the `ports:` entries or firewall them)
- [ ] Mind's port `8080` not exposed publicly — Gate is the only intended client
- [ ] Backups scheduled and a restore tested
- [ ] Provider API keys stored outside version control (`.env` is git-ignored)

## 7. Validate a new deployment

1. Health endpoints return `ok`.
2. Create a tenant: `curl -X POST https://api.example.com/tenants -H "X-Admin-Key: $SENSE_ADMIN_KEY" -H 'Content-Type: application/json' -d '{"name":"Acme","slug":"acme","email":"you@example.com"}'` and save the `api_key` (shown once).
3. Sign in to the Console, open **Live Demo**, press **Start demo**, allow the camera, and confirm lens events appear.

## 8. Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Join succeeds but video never connects | `SENSE_PUBLIC_RELAY_URL` not reachable from the browser, or UDP/TCP media ports blocked |
| Camera prompt never appears | Page not served over HTTPS / localhost |
| Lens cards never appear | Agent started without lenses, YOLO weights could not download (Mind needs internet on first use), or `SENSE_SERVICE_KEY` differs between Mind and Wire |
| `502` on agent start | Mind could not join Relay or build the agent — the response body has the reason |
| Agent in room but silent / deaf | No STT/TTS key configured (`DEEPGRAM_API_KEY` / `ELEVENLABS_API_KEY`) |
| Service exits at start in production | A default secret is still set — the log names which |
