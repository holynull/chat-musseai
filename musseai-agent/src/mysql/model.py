# 文件: /musseai-agent/src/mysql/model.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    JSON,
    TIMESTAMP,
    Enum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
import enum


class SourceType(enum.Enum):
    """资产来源类型枚举"""

    WALLET = "WALLET"
    EXCHANGE = "EXCHANGE"
    DEFI = "DEFI"


class TransactionType(enum.Enum):
    """交易类型枚举"""

    BUY = "BUY"
    SELL = "SELL"
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    TRANSFER = "TRANSFER"


class PortfolioSourceModel(Base):
    """用户资产来源表"""

    __tablename__ = "portfolio_sources"

    source_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, comment="用户标识")
    source_type = Column(Enum(SourceType), nullable=False, comment="来源类型")
    source_name = Column(String(100), nullable=False, comment="来源名称")
    source_config = Column(
        JSON, nullable=False, comment="配置信息（地址、交易所信息等）"
    )
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    last_sync_at = Column(TIMESTAMP, nullable=True, comment="最后同步时间")

    # 关系映射
    positions = relationship(
        "PositionModel", back_populates="source", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "TransactionModel", back_populates="source", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_user_type", "user_id", "source_type"),
        Index("idx_user_active", "user_id", "is_active"),
        Index("idx_active", "is_active"),
        {"comment": "用户资产来源表"},
    )


class AssetModel(Base):
    """资产定义表"""

    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, comment="资产符号")
    name = Column(String(100), nullable=False, comment="资产名称")
    chain = Column(String(20), nullable=False, default="GENERAL", comment="所属链")
    contract_address = Column(String(100), nullable=True, comment="合约地址")
    decimals = Column(Integer, default=18, comment="精度")
    logo_url = Column(String(255), nullable=True, comment="Logo图片URL")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")

    # 关系映射 - 修复：明确指定foreign_keys
    positions = relationship("PositionModel", back_populates="asset")
    transactions = relationship(
        "TransactionModel",
        foreign_keys="[TransactionModel.asset_id]",
        back_populates="asset",
    )
    fee_transactions = relationship(
        "TransactionModel",
        foreign_keys="[TransactionModel.fee_asset_id]",
        back_populates="fee_asset",
    )
    price_snapshots = relationship(
        "PriceSnapshotModel", back_populates="asset", cascade="all, delete-orphan"
    )

    # 约束和索引
    __table_args__ = (
        UniqueConstraint("symbol", "chain", name="unique_asset"),
        Index("idx_symbol", "symbol"),
        Index("idx_chain", "chain"),
        {"comment": "资产定义表"},
    )


class PositionModel(Base):
    """持仓表"""

    __tablename__ = "positions"

    position_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(
        Integer,
        ForeignKey("portfolio_sources.source_id", ondelete="CASCADE"),
        nullable=False,
        comment="来源ID",
    )
    asset_id = Column(
        Integer,
        ForeignKey("assets.asset_id", ondelete="RESTRICT"),
        nullable=False,
        comment="资产ID",
    )
    quantity = Column(Numeric(30, 18), nullable=False, default=0, comment="持仓数量")
    avg_cost = Column(Numeric(20, 8), nullable=True, comment="平均成本")
    last_price = Column(Numeric(20, 8), nullable=True, comment="最新价格")
    updated_at = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    # 关系映射
    source = relationship("PortfolioSourceModel", back_populates="positions")
    asset = relationship("AssetModel", back_populates="positions")

    # 约束和索引
    __table_args__ = (
        UniqueConstraint("source_id", "asset_id", name="unique_position"),
        Index("idx_source", "source_id"),
        Index("idx_asset", "asset_id"),
        Index("idx_updated", "updated_at"),
        {"comment": "持仓表"},
    )


class TransactionModel(Base):
    """交易记录表"""

    __tablename__ = "transactions"

    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(
        Integer,
        ForeignKey("portfolio_sources.source_id", ondelete="CASCADE"),
        nullable=False,
        comment="来源ID",
    )
    transaction_type = Column(Enum(TransactionType), nullable=False, comment="交易类型")
    asset_id = Column(
        Integer,
        ForeignKey("assets.asset_id", ondelete="RESTRICT"),
        nullable=False,
        comment="资产ID",
    )
    quantity = Column(Numeric(30, 18), nullable=False, comment="交易数量")
    price = Column(Numeric(20, 8), nullable=True, comment="交易价格")
    fee = Column(Numeric(20, 8), default=0, comment="手续费")
    fee_asset_id = Column(
        Integer,
        ForeignKey("assets.asset_id", ondelete="RESTRICT"),
        nullable=True,
        comment="手续费资产ID",
    )
    external_tx_id = Column(String(200), nullable=True, comment="外部交易ID")
    transaction_time = Column(TIMESTAMP, nullable=False, comment="交易时间")
    notes = Column(Text, nullable=True, comment="备注")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="记录创建时间")

    # 关系映射 - 修复：明确指定关系
    source = relationship("PortfolioSourceModel", back_populates="transactions")
    asset = relationship(
        "AssetModel", foreign_keys=[asset_id], back_populates="transactions"
    )
    fee_asset = relationship(
        "AssetModel", foreign_keys=[fee_asset_id], back_populates="fee_transactions"
    )

    # 索引
    __table_args__ = (
        Index("idx_source_time", "source_id", "transaction_time"),
        Index("idx_asset", "asset_id"),
        Index("idx_type_time", "transaction_type", "transaction_time"),
        Index("idx_external", "external_tx_id"),
        {"comment": "交易记录表"},
    )


class PriceSnapshotModel(Base):
    """价格快照表"""

    __tablename__ = "price_snapshots"

    snapshot_id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(
        Integer,
        ForeignKey("assets.asset_id", ondelete="CASCADE"),
        nullable=False,
        comment="资产ID",
    )
    price = Column(Numeric(20, 8), nullable=False, comment="价格")
    timestamp = Column(TIMESTAMP, nullable=False, comment="时间戳")

    # 关系映射
    asset = relationship("AssetModel", back_populates="price_snapshots")

    # 约束和索引
    __table_args__ = (
        UniqueConstraint("asset_id", "timestamp", name="unique_asset_time"),
        Index("idx_asset_time", "asset_id", "timestamp", postgresql_using="btree"),
        {"comment": "价格快照表"},
    )

# ========================================
# Alert Types and Models
# ========================================

class AlertType(enum.Enum):
    """Alert type enumeration"""
    PRICE = "PRICE"
    PORTFOLIO_VALUE = "PORTFOLIO_VALUE"
    RISK = "RISK"
    PERFORMANCE = "PERFORMANCE"
    REBALANCING = "REBALANCING"
    VOLUME = "VOLUME"
    VOLATILITY = "VOLATILITY"

class AlertStatus(enum.Enum):
    """Alert status enumeration"""
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"

class NotificationMethod(enum.Enum):
    """Notification method enumeration"""
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    WEBHOOK = "WEBHOOK"

class PortfolioAlertModel(Base):
    """Portfolio alert configuration model"""
    __tablename__ = "portfolio_alerts"
    
    alert_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, comment="User identifier")
    alert_type = Column(Enum(AlertType), nullable=False, comment="Alert type")
    alert_name = Column(String(200), nullable=False, comment="User-defined alert name")
    conditions = Column(JSON, nullable=False, comment="Alert conditions")
    notification_methods = Column(JSON, nullable=False, comment="Notification methods")
    status = Column(Enum(AlertStatus), default=AlertStatus.ACTIVE, comment="Alert status")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="Creation time")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="Update time")
    last_checked_at = Column(TIMESTAMP, nullable=True, comment="Last check time")
    last_triggered_at = Column(TIMESTAMP, nullable=True, comment="Last trigger time")
    trigger_count = Column(Integer, default=0, comment="Total trigger count")
    expiry_date = Column(TIMESTAMP, nullable=True, comment="Alert expiry date")


class AlertHistoryModel(Base):
    """Alert trigger history model"""
    __tablename__ = "alert_history"
    
    history_id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("portfolio_alerts.alert_id", ondelete="CASCADE"), nullable=False)
    triggered_at = Column(TIMESTAMP, nullable=False, comment="Trigger time")
    trigger_value = Column(JSON, nullable=False, comment="Values that triggered the alert")
    message = Column(Text, nullable=False, comment="Alert message")
    notification_sent = Column(Boolean, default=False, comment="Whether notification was sent")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="Record creation time")