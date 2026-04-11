import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship

load_dotenv()

DB_PATH = Path(__file__).resolve().parent / "portfolio.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


class Base(DeclarativeBase):
    pass


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_value = Column(Float, nullable=False)
    total_profit_loss = Column(Float, nullable=False)
    total_profit_loss_rate = Column(Float, nullable=False)

    assets = relationship("AssetSnapshot", back_populates="snapshot", cascade="all, delete-orphan")


class AssetSnapshot(Base):
    __tablename__ = "asset_snapshots"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("portfolio_snapshots.id"), nullable=False)
    name = Column(String(50), nullable=False)
    ticker = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    total_value = Column(Float, nullable=False)
    profit_loss = Column(Float, nullable=False)
    profit_loss_rate = Column(Float, nullable=False)
    asset_type = Column(String(20), nullable=False, default="crypto")

    snapshot = relationship("PortfolioSnapshot", back_populates="assets")


class NewsReport(Base):
    __tablename__ = "news_reports"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    category = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    source = Column(String(100))
    url = Column(Text)


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False)
    condition = Column(String(10), nullable=False)   # "above" | "below"
    threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    with Session(engine) as session:
        yield session
