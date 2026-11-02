from sense_gate.config import Settings


def test_client_url_defaults_to_internal_url():
    assert Settings(relay_url="ws://relay:7880").relay_client_url == "ws://relay:7880"


def test_client_url_prefers_public_url():
    s = Settings(relay_url="ws://sense-relay:7880", relay_public_url="wss://relay.example.com")
    assert s.relay_client_url == "wss://relay.example.com"
