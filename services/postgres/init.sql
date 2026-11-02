-- Sense Platform — Postgres initialization
-- The compose file creates `sense_gate` via POSTGRES_DB; add the other databases here.

CREATE DATABASE sense_wire;

GRANT ALL PRIVILEGES ON DATABASE sense_wire TO sense;
