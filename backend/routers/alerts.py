from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session as SASession

from database import PriceAlert, engine

router = APIRouter(prefix="/api/alerts")


class AlertCreate(BaseModel):
    ticker: str
    condition: str
    threshold: float


class AlertOut(BaseModel):
    id: int
    ticker: str
    condition: str
    threshold: float
    is_active: bool
    created_at: datetime
    last_triggered_at: Optional[datetime] = None


@router.get("/", response_model=list[AlertOut])
def list_alerts():
    with SASession(engine) as session:
        alerts = session.query(PriceAlert).filter_by(is_active=True).all()
        return [AlertOut(
            id=a.id, ticker=a.ticker, condition=a.condition,
            threshold=a.threshold, is_active=a.is_active,
            created_at=a.created_at, last_triggered_at=a.last_triggered_at,
        ) for a in alerts]


@router.post("/", response_model=AlertOut)
def create_alert(body: AlertCreate):
    with SASession(engine) as session:
        alert = PriceAlert(
            ticker=body.ticker.upper(),
            condition=body.condition,
            threshold=body.threshold,
            is_active=True,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return AlertOut(
            id=alert.id, ticker=alert.ticker, condition=alert.condition,
            threshold=alert.threshold, is_active=alert.is_active,
            created_at=alert.created_at, last_triggered_at=alert.last_triggered_at,
        )


@router.delete("/{alert_id}")
def delete_alert(alert_id: int):
    with SASession(engine) as session:
        alert = session.query(PriceAlert).filter_by(id=alert_id, is_active=True).first()
        if not alert:
            return {"status": "not_found"}
        alert.is_active = False
        session.commit()
        return {"status": "deleted", "id": alert_id}
