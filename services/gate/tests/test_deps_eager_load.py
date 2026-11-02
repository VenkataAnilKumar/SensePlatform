"""Regression: the tenant must be eager-loaded; async SQLAlchemy cannot lazy-load."""
import inspect

from sense_gate import deps


def test_api_key_lookup_eager_loads_tenant():
    assert "selectinload(ApiKey.tenant)" in inspect.getsource(deps.get_tenant_from_api_key)
