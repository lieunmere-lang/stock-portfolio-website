import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine, event, text,
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
    total_investment = Column(Float, nullable=True)   # 투자 원금
    today_profit_loss = Column(Float, nullable=True)  # 오늘의 손익 (24h 대비)

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
    first_purchase_date = Column(DateTime, nullable=True)  # 최초 매수일
    signed_change_price = Column(Float, nullable=True, default=0.0)
    signed_change_rate = Column(Float, nullable=True, default=0.0)

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


class ManualAsset(Base):
    """업비트 API로 조회되지 않는 수동 등록 자산 (스테이킹 대기, OTC 등)."""
    __tablename__ = "manual_assets"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)           # 표시 이름 (예: 이더리움 스테이킹)
    ticker = Column(String(20), nullable=False)          # 표시용 티커 (예: KRW-ETH2)
    price_ticker = Column(String(20), nullable=False)    # 현재가 조회 티커 (예: KRW-ETH)
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    first_purchase_date = Column(DateTime, nullable=True)
    asset_type = Column(String(20), nullable=False, default="crypto")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StockHolding(Base):
    """미국 주식 보유 정보 (수동 등록)."""
    __tablename__ = "stock_holdings"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False, unique=True)   # 예: AAPL
    name = Column(String(100), nullable=False)                  # 예: Apple Inc.
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)                   # USD
    first_purchase_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
    # 기존 DB에 새 컬럼 추가 (이미 존재하면 무시)
    migration_stmts = [
        "ALTER TABLE portfolio_snapshots ADD COLUMN total_investment REAL",
        "ALTER TABLE portfolio_snapshots ADD COLUMN today_profit_loss REAL",
        "ALTER TABLE asset_snapshots ADD COLUMN first_purchase_date TEXT",
        "ALTER TABLE asset_snapshots ADD COLUMN signed_change_price REAL DEFAULT 0",
        "ALTER TABLE asset_snapshots ADD COLUMN signed_change_rate REAL DEFAULT 0",
    ]
    with engine.connect() as conn:
        for stmt in migration_stmts:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # 이미 컬럼이 존재하는 경우 무시


def get_db():
    with Session(engine) as session:
        yield session
