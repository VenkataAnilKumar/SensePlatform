import httpx
import pytest

from sense_gate.services.agent_service import AgentService, AgentServiceError


def service(handler):
    svc = AgentService()
    svc._client = httpx.AsyncClient(base_url="http://mind", transport=httpx.MockTransport(handler))
    return svc


@pytest.mark.asyncio
async def test_start_forwards_routing_and_namespaces_room():
    seen = {}

    def handler(request):
        import json
        seen.update(json.loads(request.read()))
        return httpx.Response(200, json={"status": "started"})

    out = await service(handler).start_agent("acme", "r1", tenant_id="tid", lenses=["MoodLens"])
    assert out["status"] == "started"
    assert seen["room"] == "acme__r1" and seen["tenant_id"] == "tid" and seen["room_id"] == "r1"


@pytest.mark.asyncio
async def test_mind_error_is_propagated_not_faked():
    svc = service(lambda r: httpx.Response(502, json={"detail": {"status": "failed", "error": "relay down"}}))
    with pytest.raises(AgentServiceError) as exc:
        await svc.start_agent("acme", "r1")
    assert exc.value.status_code == 502 and exc.value.detail["error"] == "relay down"


@pytest.mark.asyncio
async def test_unreachable_mind_is_503():
    def boom(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(AgentServiceError) as exc:
        await service(boom).get_agent_status("acme", "r1")
    assert exc.value.status_code == 503
