"""
Sense Gate — Usage Router
GET /usage — query usage metrics for a tenant.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from sense_gate.deps import DBDep, TenantDep
from sense_gate.models.usage import UsageRecord

router = APIRouter(prefix="/usage", tags=["Usage"])


class UsageSummary(BaseModel):
    event_type: str
    total_quantity: float
    unit: str
    count: int


class UsageResponse(BaseModel):
    tenant_id: str
    from_date: str
    to_date: str
    summary: list[UsageSummary]
    total_records: int


@router.get("", response_model=UsageResponse)
async def get_usage(
    tenant: TenantDep,
    db: DBDep,
    from_date: str = Query(default=None, description="ISO date: 2024-01-01"),
    to_date: str = Query(default=None, description="ISO date: 2024-12-31"),
):
    """
    Get aggregated usage metrics for the authenticated tenant.

    Returns totals per event type (room minutes, API calls, agent minutes, etc.)

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    query = select(
        UsageRecord.event_type,
        func.sum(UsageRecord.quantity).label("total_quantity"),
        UsageRecord.unit,
        func.count(UsageRecord.id).label("count"),
    ).where(UsageRecord.tenant_id == tenant.id)

    if from_date:
        try:
            dt = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
            query = query.where(UsageRecord.recorded_at >= dt)
        except ValueError:
            pass

    if to_date:
        try:
            dt = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc)
            query = query.where(UsageRecord.recorded_at <= dt)
        except ValueError:
            pass

    query = query.group_by(UsageRecord.event_type, UsageRecord.unit)

    result = await db.execute(query)
    rows = result.all()

    summary = [
        UsageSummary(
            event_type=row.event_type,
            total_quantity=float(row.total_quantity or 0),
            unit=row.unit,
            count=row.count,
        )
        for row in rows
    ]

    return UsageResponse(
        tenant_id=str(tenant.id),
        from_date=from_date or "all",
        to_date=to_date or "all",
        summary=summary,
        total_records=sum(s.count for s in summary),
    )
