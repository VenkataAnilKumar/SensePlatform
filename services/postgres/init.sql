-- Sense Platform — Postgres initialization
-- Creates all databases needed by Sense Gate and Sense Wire

CREATE DATABASE sense_gate;
CREATE DATABASE sense_wire;

GRANT ALL PRIVILEGES ON DATABASE sense_gate TO sense;
GRANT ALL PRIVILEGES ON DATABASE sense_wire TO sense;
