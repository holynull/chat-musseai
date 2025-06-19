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
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
import datetime


class AssetSourceTypeModel(Base):
    __tablename__ = "asset_source_types"

    source_type_id = Column(Integer, primary_key=True, autoincrement=True)
    type_name = Column(String(50), nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    status = Column(Integer, default=1)


class AssetSourceModel(Base):
    __tablename__ = "asset_sources"

    source_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)
    source_type_id = Column(
        Integer, ForeignKey("asset_source_types.source_type_id"), nullable=False
    )
    source_name = Column(String(100), nullable=False)
    source_details = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_sync_time = Column(TIMESTAMP)

    source_type = relationship("AssetSourceTypeModel")
    positions = relationship("AssetPositionModel", back_populates="source")


class SupportedExchangeModel(Base):
    __tablename__ = "supported_exchanges"

    exchange_id = Column(Integer, primary_key=True, autoincrement=True)
    exchange_name = Column(String(50), nullable=False)
    display_name = Column(String(100), nullable=False)
    api_base_url = Column(String(200), nullable=False)
    logo_url = Column(String(200))
    supported_features = Column(JSON)
    status = Column(Integer, default=1)
    created_at = Column(TIMESTAMP, server_default=func.now())


class ExchangeApiCredentialModel(Base):
    __tablename__ = "exchange_api_credentials"

    credential_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)
    exchange_name = Column(String(50), nullable=False)
    api_key = Column(String(200), nullable=False)
    api_secret = Column(String(500), nullable=False)
    api_passphrase = Column(String(200))
    description = Column(String(200))
    is_active = Column(Integer, default=1)
    permissions = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_used_at = Column(TIMESTAMP)


class CryptoAssetModel(Base):
    __tablename__ = "crypto_assets"

    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    asset_symbol = Column(String(20), nullable=False)
    asset_name = Column(String(50), nullable=False)
    chain_type = Column(String(20), nullable=False)
    contract_address = Column(String(100))
    decimals = Column(Integer, default=18)
    created_at = Column(TIMESTAMP, server_default=func.now())
    status = Column(Integer, default=1)


class AssetPositionModel(Base):
    __tablename__ = "asset_positions"

    position_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("asset_sources.source_id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("crypto_assets.asset_id"), nullable=False)
    quantity = Column(Numeric(65, 18), nullable=False)
    cost_basis = Column(Numeric(20, 8))
    last_updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    last_sync_time = Column(TIMESTAMP)
    additional_data = Column(JSON)

    source = relationship("AssetSourceModel", back_populates="positions")
    asset = relationship("CryptoAssetModel")


class PositionHistoryNewModel(Base):
    __tablename__ = "position_history_new"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("asset_sources.source_id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("crypto_assets.asset_id"), nullable=False)
    quantity = Column(Numeric(65, 18), nullable=False)
    change_amount = Column(Numeric(65, 18), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    agent_id = Column(String(50))
    conversation_id = Column(String(100))
    sync_type = Column(String(30))
    operation_type = Column(String(30))
    operation_details = Column(JSON)

    source = relationship("AssetSourceModel")
    asset = relationship("CryptoAssetModel")


class AssetTransactionModel(Base):
    __tablename__ = "asset_transactions"

    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)
    source_id = Column(Integer, ForeignKey("asset_sources.source_id"), nullable=False)
    transaction_type = Column(String(30), nullable=False)
    base_asset_id = Column(
        Integer, ForeignKey("crypto_assets.asset_id"), nullable=False
    )
    quote_asset_id = Column(Integer, ForeignKey("crypto_assets.asset_id"))
    base_amount = Column(Numeric(65, 18), nullable=False)
    quote_amount = Column(Numeric(65, 18))
    fee_asset_id = Column(Integer, ForeignKey("crypto_assets.asset_id"))
    fee_amount = Column(Numeric(65, 18))
    price = Column(Numeric(65, 18))
    transaction_time = Column(TIMESTAMP, nullable=False)
    external_id = Column(String(200))
    status = Column(String(20), default="COMPLETED", nullable=False)
    additional_info = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

    source = relationship("AssetSourceModel")
    base_asset = relationship("CryptoAssetModel", foreign_keys=[base_asset_id])
    quote_asset = relationship("CryptoAssetModel", foreign_keys=[quote_asset_id])
    fee_asset = relationship("CryptoAssetModel", foreign_keys=[fee_asset_id])
