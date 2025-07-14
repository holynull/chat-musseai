from typing import List, Dict
from decimal import Decimal
from datetime import datetime, timedelta
from langchain.agents import tool
from sqlalchemy import and_, func
from mysql.db import get_db
from mysql.model import (
    PortfolioSourceModel,
    AssetModel,
    PositionModel,
    TransactionModel,
    PriceSnapshotModel,
    SourceType,
    TransactionType,
)
from loggers import logger
import traceback
from .tools_crypto_portfolios_analysis import tools as tools_analysis


# ========================================
# Asset Source Management Tools
# ========================================


@tool
def get_user_asset_sources(
    user_id: str, source_type: str = None, is_active: bool = True
) -> List[Dict]:
    """
    Get all asset sources for a user, optionally filtered by source type and active status.

    Args:
        user_id (str): User identifier
        source_type (str, optional): Filter by source type ('WALLET', 'EXCHANGE', 'DEFI')
        is_active (bool): Filter by active status (default: True)

    Returns:
        List[Dict]: List of asset sources containing:
            - source_id: Unique source identifier
            - source_type: Type of source (WALLET/EXCHANGE/DEFI)
            - source_name: User-defined name for the source
            - source_config: Configuration details (addresses, API keys, etc.)
            - is_active: Whether the source is active
            - created_at: Creation timestamp
            - last_sync_at: Last synchronization timestamp
            - position_count: Number of positions in this source
    """
    try:
        with get_db() as db:
            # Build query with filters
            query = db.query(PortfolioSourceModel).filter(
                PortfolioSourceModel.user_id == user_id,
                PortfolioSourceModel.is_active == is_active,
            )

            if source_type:
                if source_type.upper() not in ["WALLET", "EXCHANGE", "DEFI"]:
                    return (
                        f"Invalid source_type. Must be one of: WALLET, EXCHANGE, DEFI"
                    )
                query = query.filter(
                    PortfolioSourceModel.source_type == SourceType(source_type.upper())
                )

            sources = query.order_by(PortfolioSourceModel.created_at.desc()).all()

            result = []
            for source in sources:
                # Count positions for this source
                position_count = (
                    db.query(PositionModel)
                    .filter(
                        PositionModel.source_id == source.source_id,
                        PositionModel.quantity > 0,
                    )
                    .count()
                )

                result.append(
                    {
                        "source_id": source.source_id,
                        "source_type": source.source_type.value,
                        "source_name": source.source_name,
                        "source_config": source.source_config,
                        "is_active": source.is_active,
                        "created_at": (
                            source.created_at.isoformat() if source.created_at else None
                        ),
                        "last_sync_at": (
                            source.last_sync_at.isoformat()
                            if source.last_sync_at
                            else None
                        ),
                        "position_count": position_count,
                    }
                )

            return result

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return f"Failed to get user asset sources: {str(e)}"


@tool
def add_wallet_source(
    user_id: str,
    source_name: str,
    wallet_address: str,
    chain: str,
    description: str = None,
) -> Dict:
    """
    Add a new wallet address as an asset source for portfolio tracking.

    Args:
        user_id (str): User identifier
        source_name (str): User-defined name for this wallet source
        wallet_address (str): Blockchain wallet address
        chain (str): Blockchain name (ETH, BSC, SOL, POLYGON, etc.)
        description (str, optional): Additional description for the wallet

    Returns:
        Dict: Created source information or error message
    """
    try:
        with get_db() as db:
            # Check if source name already exists for this user
            existing = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.source_name == source_name,
                )
                .first()
            )

            if existing:
                return {
                    "success": False,
                    "message": f"Source name '{source_name}' already exists for this user",
                }

            # Create source configuration
            source_config = {
                "wallet_address": wallet_address,
                "chain": chain.upper(),
                "description": description or f"{chain.upper()} wallet",
            }

            # Create new source
            new_source = PortfolioSourceModel(
                user_id=user_id,
                source_type=SourceType.WALLET,
                source_name=source_name,
                source_config=source_config,
                is_active=True,
            )

            db.add(new_source)
            db.commit()
            db.refresh(new_source)

            return {
                "success": True,
                "message": "Wallet source added successfully",
                "source": {
                    "source_id": new_source.source_id,
                    "source_type": new_source.source_type.value,
                    "source_name": new_source.source_name,
                    "source_config": new_source.source_config,
                    "created_at": new_source.created_at.isoformat(),
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to add wallet source: {str(e)}"}


@tool
def add_exchange_source(
    user_id: str,
    source_name: str,
    exchange_name: str,
    api_key: str = None,
    description: str = None,
) -> Dict:
    """
    Add a new exchange account as an asset source for portfolio tracking.

    Args:
        user_id (str): User identifier
        source_name (str): User-defined name for this exchange source
        exchange_name (str): Exchange name (Binance, Coinbase, Kraken, etc.)
        api_key (str, optional): Exchange API key for automated sync
        description (str, optional): Additional description

    Returns:
        Dict: Created source information or error message
    """
    try:
        with get_db() as db:
            # Check if source name already exists for this user
            existing = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.source_name == source_name,
                )
                .first()
            )

            if existing:
                return {
                    "success": False,
                    "message": f"Source name '{source_name}' already exists for this user",
                }

            # Create source configuration
            source_config = {
                "exchange_name": exchange_name,
                "api_key": api_key,  # In production, this should be encrypted
                "description": description or f"{exchange_name} exchange account",
            }

            # Create new source
            new_source = PortfolioSourceModel(
                user_id=user_id,
                source_type=SourceType.EXCHANGE,
                source_name=source_name,
                source_config=source_config,
                is_active=True,
            )

            db.add(new_source)
            db.commit()
            db.refresh(new_source)

            return {
                "success": True,
                "message": "Exchange source added successfully",
                "source": {
                    "source_id": new_source.source_id,
                    "source_type": new_source.source_type.value,
                    "source_name": new_source.source_name,
                    "source_config": new_source.source_config,
                    "created_at": new_source.created_at.isoformat(),
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to add exchange source: {str(e)}"}


@tool
def add_defi_source(
    user_id: str,
    source_name: str,
    protocol_name: str,
    wallet_address: str,
    chain: str,
    description: str = None,
) -> Dict:
    """
    Add a new DeFi protocol position as an asset source for portfolio tracking.

    Args:
        user_id (str): User identifier
        source_name (str): User-defined name for this DeFi source
        protocol_name (str): DeFi protocol name (Uniswap, Aave, Curve, etc.)
        wallet_address (str): Wallet address used in the protocol
        chain (str): Blockchain name where the protocol operates
        description (str, optional): Additional description

    Returns:
        Dict: Created source information or error message
    """
    try:
        with get_db() as db:
            # Check if source name already exists for this user
            existing = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.source_name == source_name,
                )
                .first()
            )

            if existing:
                return {
                    "success": False,
                    "message": f"Source name '{source_name}' already exists for this user",
                }

            # Create source configuration
            source_config = {
                "protocol_name": protocol_name,
                "wallet_address": wallet_address,
                "chain": chain.upper(),
                "description": description or f"{protocol_name} on {chain.upper()}",
            }

            # Create new source
            new_source = PortfolioSourceModel(
                user_id=user_id,
                source_type=SourceType.DEFI,
                source_name=source_name,
                source_config=source_config,
                is_active=True,
            )

            db.add(new_source)
            db.commit()
            db.refresh(new_source)

            return {
                "success": True,
                "message": "DeFi source added successfully",
                "source": {
                    "source_id": new_source.source_id,
                    "source_type": new_source.source_type.value,
                    "source_name": new_source.source_name,
                    "source_config": new_source.source_config,
                    "created_at": new_source.created_at.isoformat(),
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to add DeFi source: {str(e)}"}


@tool
def update_asset_source(
    source_id: int,
    user_id: str,
    source_name: str = None,
    source_config: Dict = None,
    is_active: bool = None,
) -> Dict:
    """
    Update an existing asset source configuration.

    Args:
        source_id (int): Source identifier to update
        user_id (str): User identifier (for security check)
        source_name (str, optional): New source name
        source_config (Dict, optional): New configuration data
        is_active (bool, optional): New active status

    Returns:
        Dict: Update result and updated source information
    """
    try:
        with get_db() as db:
            # Get existing source and verify ownership
            source = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.source_id == source_id,
                    PortfolioSourceModel.user_id == user_id,
                )
                .first()
            )

            if not source:
                return {
                    "success": False,
                    "message": "Source not found or access denied",
                }

            # Update fields if provided
            if source_name is not None:
                # Check if new name conflicts with existing names
                existing = (
                    db.query(PortfolioSourceModel)
                    .filter(
                        PortfolioSourceModel.user_id == user_id,
                        PortfolioSourceModel.source_name == source_name,
                        PortfolioSourceModel.source_id != source_id,
                    )
                    .first()
                )

                if existing:
                    return {
                        "success": False,
                        "message": f"Source name '{source_name}' already exists",
                    }

                source.source_name = source_name

            if source_config is not None:
                source.source_config = source_config

            if is_active is not None:
                source.is_active = is_active

            db.commit()
            db.refresh(source)

            return {
                "success": True,
                "message": "Asset source updated successfully",
                "source": {
                    "source_id": source.source_id,
                    "source_type": source.source_type.value,
                    "source_name": source.source_name,
                    "source_config": source.source_config,
                    "is_active": source.is_active,
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to update asset source: {str(e)}"}


@tool
def delete_asset_source(source_id: int, user_id: str) -> Dict:
    """
    Delete an asset source and all associated positions and transactions.

    Args:
        source_id (int): Source identifier to delete
        user_id (str): User identifier (for security check)

    Returns:
        Dict: Deletion result with counts of affected records
    """
    try:
        with get_db() as db:
            # Get existing source and verify ownership
            source = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.source_id == source_id,
                    PortfolioSourceModel.user_id == user_id,
                )
                .first()
            )

            if not source:
                return {
                    "success": False,
                    "message": "Source not found or access denied",
                }

            # Count associated records before deletion
            position_count = (
                db.query(PositionModel)
                .filter(PositionModel.source_id == source_id)
                .count()
            )

            transaction_count = (
                db.query(TransactionModel)
                .filter(TransactionModel.source_id == source_id)
                .count()
            )

            source_name = source.source_name

            # Delete source (cascade will handle positions and transactions)
            db.delete(source)
            db.commit()

            return {
                "success": True,
                "message": f"Asset source '{source_name}' deleted successfully",
                "deleted_counts": {
                    "positions": position_count,
                    "transactions": transaction_count,
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to delete asset source: {str(e)}"}


# ========================================
# Asset Management Tools
# ========================================


@tool
def search_assets(
    symbol: str = None, chain: str = None, name_contains: str = None, limit: int = 50
) -> List[Dict]:
    """Search for assets in the system by various criteria.
    Args:
    symbol (str, optional): Asset symbol (exact match)
    chain (str, optional): Blockchain name (ETH, BSC, SOL, etc.)
    name_contains (str, optional): Partial asset name match
    limit (int): Maximum number of results (default: 50)

    Returns:
        List[Dict]: List of matching assets containing:
            - asset_id: Unique asset identifier
            - symbol: Asset symbol
            - name: Asset full name
            - chain: Blockchain name
            - contract_address: Smart contract address
            - decimals: Token decimals
            - logo_url: Logo image URL
    """
    try:
        with get_db() as db:
            query = db.query(AssetModel).filter(AssetModel.is_active == True)

            if symbol:
                query = query.filter(AssetModel.symbol == symbol.upper())

            if chain:
                query = query.filter(AssetModel.chain == chain.upper())

            if name_contains:
                query = query.filter(AssetModel.name.ilike(f"%{name_contains}%"))

            assets = query.limit(limit).all()

            result = []
            for asset in assets:
                result.append(
                    {
                        "asset_id": asset.asset_id,
                        "symbol": asset.symbol,
                        "name": asset.name,
                        "chain": asset.chain,
                        "contract_address": asset.contract_address,
                        "decimals": asset.decimals,
                        "logo_url": asset.logo_url,
                    }
                )

            return result

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return f"Failed to search assets: {str(e)}"


@tool
def add_custom_asset(
    symbol: str,
    name: str,
    chain: str,
    contract_address: str = None,
    decimals: int = 18,
    logo_url: str = None,
) -> Dict:
    """Add a custom asset to the system (for tokens not in the default list).
    Args:
    symbol (str): Asset symbol (e.g., 'CUSTOM')
    name (str): Asset full name
    chain (str): Blockchain name (ETH, BSC, SOL, etc.)
    contract_address (str, optional): Smart contract address
    decimals (int): Token decimals (default: 18)
    logo_url (str, optional): Logo image URL

    Returns:
        Dict: Created asset information or error message
    """
    try:
        with get_db() as db:
            # Check if asset already exists
            existing = (
                db.query(AssetModel)
                .filter(
                    AssetModel.symbol == symbol.upper(),
                    AssetModel.chain == chain.upper(),
                )
                .first()
            )

            if existing:
                return {
                    "success": False,
                    "message": f"Asset {symbol} on {chain} already exists",
                    "asset_id": existing.asset_id,
                }

            # Create new asset
            new_asset = AssetModel(
                symbol=symbol.upper(),
                name=name,
                chain=chain.upper(),
                contract_address=contract_address,
                decimals=decimals,
                logo_url=logo_url,
                is_active=True,
            )

            db.add(new_asset)
            db.commit()
            db.refresh(new_asset)

            return {
                "success": True,
                "message": "Custom asset added successfully",
                "asset": {
                    "asset_id": new_asset.asset_id,
                    "symbol": new_asset.symbol,
                    "name": new_asset.name,
                    "chain": new_asset.chain,
                    "contract_address": new_asset.contract_address,
                    "decimals": new_asset.decimals,
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to add custom asset: {str(e)}"}


# ========================================
# Position Management Tools
# ========================================


@tool
def update_position(
    source_id: int,
    user_id: str,
    symbol: str,
    chain: str,
    quantity: float,
    avg_cost: float = None,
    transaction_type: str = "BUY",
    notes: str = None,
) -> Dict:
    """Update or create a position in a portfolio source. This also records the transaction.
    Args:
        source_id (int): Source identifier where the position belongs
        user_id (str): User identifier (for security check)
        symbol (str): Asset symbol
        chain (str): Blockchain name
        quantity (float): New total quantity (not delta)
        avg_cost (float, optional): Average cost per unit in USD
        transaction_type (str): Transaction type (BUY, SELL, DEPOSIT, WITHDRAW, TRANSFER)
        notes (str, optional): Transaction notes

    Returns:
        Dict: Updated position information and transaction record
    """
    try:
        with get_db() as db:
            # Verify source ownership
            source = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.source_id == source_id,
                    PortfolioSourceModel.user_id == user_id,
                )
                .first()
            )

            if not source:
                return {
                    "success": False,
                    "message": "Source not found or access denied",
                }

            # Find or create asset
            asset = (
                db.query(AssetModel)
                .filter(
                    AssetModel.symbol == symbol.upper(),
                    AssetModel.chain == chain.upper(),
                )
                .first()
            )

            if not asset:
                return {
                    "success": False,
                    "message": f"Asset {symbol} on {chain} not found. Please add it first.",
                }

            # Get existing position
            position = (
                db.query(PositionModel)
                .filter(
                    PositionModel.source_id == source_id,
                    PositionModel.asset_id == asset.asset_id,
                )
                .first()
            )

            # Calculate transaction quantity (delta)
            if position:
                tx_quantity = Decimal(str(quantity)) - position.quantity
                old_quantity = position.quantity
            else:
                tx_quantity = Decimal(str(quantity))
                old_quantity = Decimal("0")

                # Create new position
                position = PositionModel(
                    source_id=source_id,
                    asset_id=asset.asset_id,
                    quantity=Decimal(str(quantity)),
                    avg_cost=Decimal(str(avg_cost)) if avg_cost else None,
                )
                db.add(position)

            # Update position
            position.quantity = Decimal(str(quantity))
            if avg_cost is not None:
                position.avg_cost = Decimal(str(avg_cost))

            # Create transaction record
            transaction = TransactionModel(
                source_id=source_id,
                transaction_type=TransactionType(transaction_type.upper()),
                asset_id=asset.asset_id,
                quantity=abs(tx_quantity),
                price=Decimal(str(avg_cost)) if avg_cost else None,
                transaction_time=datetime.utcnow(),
                notes=notes,
            )
            db.add(transaction)

            db.commit()
            db.refresh(position)
            db.refresh(transaction)

            return {
                "success": True,
                "message": "Position updated successfully",
                "position": {
                    "position_id": position.position_id,
                    "source_name": source.source_name,
                    "asset": f"{asset.symbol} ({asset.chain})",
                    "old_quantity": float(old_quantity),
                    "new_quantity": float(position.quantity),
                    "avg_cost": float(position.avg_cost) if position.avg_cost else None,
                    "updated_at": position.updated_at.isoformat(),
                },
                "transaction": {
                    "transaction_id": transaction.transaction_id,
                    "type": transaction.transaction_type.value,
                    "quantity": float(transaction.quantity),
                    "price": float(transaction.price) if transaction.price else None,
                    "transaction_time": transaction.transaction_time.isoformat(),
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to update position: {str(e)}"}


@tool
def get_source_positions(source_id: int, user_id: str) -> List[Dict]:
    """Get all positions for a specific asset source.
    Args:
        source_id (int): Source identifier
        user_id (str): User identifier (for security check)

    Returns:
        List[Dict]: List of positions containing:
            - position_id: Position identifier
            - asset: Asset information (symbol, name, chain)
            - quantity: Current quantity
            - avg_cost: Average cost per unit
            - last_price: Latest market price
            - current_value: Current value in USD
            - pnl: Profit/loss amount
            - pnl_percentage: Profit/loss percentage
    """
    try:
        with get_db() as db:
            # Verify source ownership
            source = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.source_id == source_id,
                    PortfolioSourceModel.user_id == user_id,
                )
                .first()
            )

            if not source:
                return []

            # Get positions with asset information
            positions = (
                db.query(PositionModel)
                .join(AssetModel)
                .filter(
                    PositionModel.source_id == source_id, PositionModel.quantity > 0
                )
                .all()
            )

            result = []
            for position in positions:
                asset = position.asset

                # Calculate values
                current_value = None
                pnl = None
                pnl_percentage = None

                if position.last_price:
                    current_value = float(position.quantity * position.last_price)

                    if position.avg_cost:
                        cost_basis = float(position.quantity * position.avg_cost)
                        pnl = current_value - cost_basis
                        pnl_percentage = (
                            (pnl / cost_basis * 100) if cost_basis > 0 else 0
                        )

                result.append(
                    {
                        "position_id": position.position_id,
                        "asset": {
                            "asset_id": asset.asset_id,
                            "symbol": asset.symbol,
                            "name": asset.name,
                            "chain": asset.chain,
                            "contract_address": asset.contract_address,
                            "logo_url": asset.logo_url,
                        },
                        "quantity": float(position.quantity),
                        "avg_cost": (
                            float(position.avg_cost) if position.avg_cost else None
                        ),
                        "last_price": (
                            float(position.last_price) if position.last_price else None
                        ),
                        "current_value": current_value,
                        "pnl": pnl,
                        "pnl_percentage": pnl_percentage,
                        "updated_at": position.updated_at.isoformat(),
                    }
                )

            return result

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return f"Failed to get source positions: {str(e)}"


@tool
def get_user_portfolio_summary(user_id: str) -> Dict:
    """Get a comprehensive summary of user's entire portfolio across all sources.
    Args:
        user_id (str): User identifier

    Returns:
        Dict: Portfolio summary containing:
            - total_value: Total portfolio value in USD
            - total_cost: Total cost basis
            - total_pnl: Total profit/loss
            - total_pnl_percentage: Overall profit/loss percentage
            - source_count: Number of asset sources
            - asset_count: Number of unique assets
            - positions_by_source: Breakdown by source
            - positions_by_asset: Aggregated positions by asset
            - allocation: Portfolio allocation percentages
    """
    try:
        with get_db() as db:
            # Get all active sources for user
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            if not sources:
                return {
                    "total_value": 0,
                    "total_cost": 0,
                    "total_pnl": 0,
                    "total_pnl_percentage": 0,
                    "source_count": 0,
                    "asset_count": 0,
                    "positions_by_source": [],
                    "positions_by_asset": [],
                    "allocation": [],
                }

            source_ids = [s.source_id for s in sources]

            # Get all positions
            positions = (
                db.query(PositionModel)
                .join(AssetModel)
                .filter(
                    PositionModel.source_id.in_(source_ids), PositionModel.quantity > 0
                )
                .all()
            )

            # Calculate totals and group by asset
            total_value = 0
            total_cost = 0
            positions_by_source = {}
            positions_by_asset = {}

            for position in positions:
                asset = position.asset
                source = next(s for s in sources if s.source_id == position.source_id)

                # Calculate position value
                position_value = 0
                position_cost = 0

                if position.last_price:
                    position_value = float(position.quantity * position.last_price)
                    total_value += position_value

                if position.avg_cost:
                    position_cost = float(position.quantity * position.avg_cost)
                    total_cost += position_cost

                # Group by source
                if source.source_id not in positions_by_source:
                    positions_by_source[source.source_id] = {
                        "source_name": source.source_name,
                        "source_type": source.source_type.value,
                        "total_value": 0,
                        "position_count": 0,
                    }

                positions_by_source[source.source_id]["total_value"] += position_value
                positions_by_source[source.source_id]["position_count"] += 1

                # Group by asset
                asset_key = f"{asset.symbol}_{asset.chain}"
                if asset_key not in positions_by_asset:
                    positions_by_asset[asset_key] = {
                        "symbol": asset.symbol,
                        "name": asset.name,
                        "chain": asset.chain,
                        "total_quantity": 0,
                        "total_value": 0,
                        "total_cost": 0,
                        "sources": [],
                    }

                positions_by_asset[asset_key]["total_quantity"] += float(
                    position.quantity
                )
                positions_by_asset[asset_key]["total_value"] += position_value
                positions_by_asset[asset_key]["total_cost"] += position_cost
                positions_by_asset[asset_key]["sources"].append(source.source_name)

            # Calculate overall P&L
            total_pnl = total_value - total_cost
            total_pnl_percentage = (
                (total_pnl / total_cost * 100) if total_cost > 0 else 0
            )

            # Calculate allocation
            allocation = []
            if total_value > 0:
                for asset_key, asset_data in positions_by_asset.items():
                    if asset_data["total_value"] > 0:
                        allocation.append(
                            {
                                "asset": f"{asset_data['symbol']} ({asset_data['chain']})",
                                "value": asset_data["total_value"],
                                "percentage": (
                                    asset_data["total_value"] / total_value * 100
                                ),
                                "quantity": asset_data["total_quantity"],
                            }
                        )

                # Sort allocation by value
                allocation.sort(key=lambda x: x["value"], reverse=True)

            # Convert dictionaries to lists
            positions_by_source_list = list(positions_by_source.values())
            positions_by_asset_list = []

            for asset_key, asset_data in positions_by_asset.items():
                pnl = asset_data["total_value"] - asset_data["total_cost"]
                pnl_percentage = (
                    (pnl / asset_data["total_cost"] * 100)
                    if asset_data["total_cost"] > 0
                    else 0
                )

                positions_by_asset_list.append(
                    {
                        "symbol": asset_data["symbol"],
                        "name": asset_data["name"],
                        "chain": asset_data["chain"],
                        "total_quantity": asset_data["total_quantity"],
                        "total_value": asset_data["total_value"],
                        "total_cost": asset_data["total_cost"],
                        "pnl": pnl,
                        "pnl_percentage": pnl_percentage,
                        "sources": list(set(asset_data["sources"])),
                    }
                )

            return {
                "total_value": total_value,
                "total_cost": total_cost,
                "total_pnl": total_pnl,
                "total_pnl_percentage": total_pnl_percentage,
                "source_count": len(sources),
                "asset_count": len(positions_by_asset),
                "positions_by_source": positions_by_source_list,
                "positions_by_asset": positions_by_asset_list,
                "allocation": allocation,
            }
    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to get portfolio summary: {str(e)}"}


@tool
def get_position_history(
    source_id: int, user_id: str, asset_id: int = None, days: int = 30
) -> List[Dict]:
    """
    Get position value history for a source or specific asset.

    Args:
        source_id (int): Source identifier
        user_id (str): User identifier (for security check)
        asset_id (int, optional): Specific asset to filter by
        days (int): Number of days of history (default: 30)

    Returns:
        List[Dict]: List of historical snapshots containing:
            - date: Snapshot date
            - positions: List of position values at that date
            - total_value: Total value at that date
    """
    try:
        with get_db() as db:
            # Verify source ownership
            source = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.source_id == source_id,
                    PortfolioSourceModel.user_id == user_id,
                )
                .first()
            )

            if not source:
                return []

            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get transactions in date range
            query = db.query(TransactionModel).filter(
                TransactionModel.source_id == source_id,
                TransactionModel.transaction_time >= start_date,
            )

            if asset_id:
                query = query.filter(TransactionModel.asset_id == asset_id)

            transactions = query.order_by(TransactionModel.transaction_time).all()

            # Build history from transactions
            history = []
            current_positions = {}

            # Get initial positions at start date
            initial_positions = db.query(PositionModel).filter(
                PositionModel.source_id == source_id
            )

            if asset_id:
                initial_positions = initial_positions.filter(
                    PositionModel.asset_id == asset_id
                )

            for position in initial_positions.all():
                if position.quantity > 0:
                    current_positions[position.asset_id] = {
                        "asset_id": position.asset_id,
                        "symbol": position.asset.symbol,
                        "chain": position.asset.chain,
                        "quantity": float(position.quantity),
                        "avg_cost": (
                            float(position.avg_cost) if position.avg_cost else None
                        ),
                    }

            # Process transactions to build history
            for tx in transactions:
                date_key = tx.transaction_time.date().isoformat()

                # Update position based on transaction
                if tx.asset_id not in current_positions:
                    current_positions[tx.asset_id] = {
                        "asset_id": tx.asset_id,
                        "symbol": tx.asset.symbol,
                        "chain": tx.asset.chain,
                        "quantity": 0,
                        "avg_cost": None,
                    }

                if tx.transaction_type in [
                    TransactionType.BUY,
                    TransactionType.DEPOSIT,
                ]:
                    current_positions[tx.asset_id]["quantity"] += float(tx.quantity)
                elif tx.transaction_type in [
                    TransactionType.SELL,
                    TransactionType.WITHDRAW,
                ]:
                    current_positions[tx.asset_id]["quantity"] -= float(tx.quantity)

                # Add snapshot for this date
                snapshot = {
                    "date": date_key,
                    "positions": list(current_positions.values()),
                    "total_value": 0,  # Would need price data to calculate
                }

                history.append(snapshot)

            return history

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return f"Failed to get position history: {str(e)}"
        db.close()


# ========================================
# Transaction Management Tools
# ========================================


@tool
def record_transaction(
    source_id: int,
    user_id: str,
    transaction_type: str,
    symbol: str,
    chain: str,
    quantity: float,
    price: float = None,
    fee: float = None,
    fee_symbol: str = None,
    fee_chain: str = None,
    external_tx_id: str = None,
    transaction_time: str = None,
    notes: str = None,
) -> Dict:
    """
    Record a transaction without updating positions (for historical imports).

    Args:
        source_id (int): Source identifier
        user_id (str): User identifier (for security check)
        transaction_type (str): Type (BUY, SELL, DEPOSIT, WITHDRAW, TRANSFER)
        symbol (str): Asset symbol
        chain (str): Blockchain name
        quantity (float): Transaction quantity
        price (float, optional): Price per unit in USD
        fee (float, optional): Transaction fee amount
        fee_symbol (str, optional): Fee asset symbol
        fee_chain (str, optional): Fee asset chain
        external_tx_id (str, optional): External transaction ID/hash
        transaction_time (str, optional): Transaction time (ISO format)
        notes (str, optional): Additional notes

    Returns:
        Dict: Created transaction information
    """
    try:
        with get_db() as db:
            # Verify source ownership
            source = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.source_id == source_id,
                    PortfolioSourceModel.user_id == user_id,
                )
                .first()
            )

            if not source:
                return {
                    "success": False,
                    "message": "Source not found or access denied",
                }

            # Find asset
            asset = (
                db.query(AssetModel)
                .filter(
                    AssetModel.symbol == symbol.upper(),
                    AssetModel.chain == chain.upper(),
                )
                .first()
            )

            if not asset:
                return {
                    "success": False,
                    "message": f"Asset {symbol} on {chain} not found",
                }

            # Find fee asset if specified
            fee_asset_id = None
            if fee_symbol and fee_chain:
                fee_asset = (
                    db.query(AssetModel)
                    .filter(
                        AssetModel.symbol == fee_symbol.upper(),
                        AssetModel.chain == fee_chain.upper(),
                    )
                    .first()
                )

                if fee_asset:
                    fee_asset_id = fee_asset.asset_id

            # Parse transaction time
            tx_time = datetime.utcnow()
            if transaction_time:
                try:
                    tx_time = datetime.fromisoformat(
                        transaction_time.replace("Z", "+00:00")
                    )
                except:
                    pass

            # Create transaction
            transaction = TransactionModel(
                source_id=source_id,
                transaction_type=TransactionType(transaction_type.upper()),
                asset_id=asset.asset_id,
                quantity=Decimal(str(quantity)),
                price=Decimal(str(price)) if price else None,
                fee=Decimal(str(fee)) if fee else Decimal("0"),
                fee_asset_id=fee_asset_id,
                external_tx_id=external_tx_id,
                transaction_time=tx_time,
                notes=notes,
            )

            db.add(transaction)
            db.commit()
            db.refresh(transaction)

            return {
                "success": True,
                "message": "Transaction recorded successfully",
                "transaction": {
                    "transaction_id": transaction.transaction_id,
                    "source_name": source.source_name,
                    "type": transaction.transaction_type.value,
                    "asset": f"{asset.symbol} ({asset.chain})",
                    "quantity": float(transaction.quantity),
                    "price": float(transaction.price) if transaction.price else None,
                    "fee": float(transaction.fee) if transaction.fee else None,
                    "transaction_time": transaction.transaction_time.isoformat(),
                    "external_tx_id": transaction.external_tx_id,
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to record transaction: {str(e)}"}


@tool
def get_transactions(
    user_id: str,
    source_id: int = None,
    asset_id: int = None,
    transaction_type: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict:
    """
    Get transaction history with various filters.

    Args:
        user_id (str): User identifier
        source_id (int, optional): Filter by source
        asset_id (int, optional): Filter by asset
        transaction_type (str, optional): Filter by type (BUY, SELL, etc.)
        start_date (str, optional): Start date (ISO format)
        end_date (str, optional): End date (ISO format)
        limit (int): Maximum results (default: 100)
        offset (int): Pagination offset (default: 0)

    Returns:
        Dict: Transaction list with pagination info
    """
    try:
        with get_db() as db:
            # Get user's source IDs for security
            user_sources = (
                db.query(PortfolioSourceModel.source_id)
                .filter(PortfolioSourceModel.user_id == user_id)
                .all()
            )

            user_source_ids = [s[0] for s in user_sources]

            if not user_source_ids:
                return {
                    "transactions": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                }

            # Build query
            query = db.query(TransactionModel).filter(
                TransactionModel.source_id.in_(user_source_ids)
            )

            if source_id and source_id in user_source_ids:
                query = query.filter(TransactionModel.source_id == source_id)

            if asset_id:
                query = query.filter(TransactionModel.asset_id == asset_id)

            if transaction_type:
                try:
                    query = query.filter(
                        TransactionModel.transaction_type
                        == TransactionType(transaction_type.upper())
                    )
                except:
                    pass

            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                    query = query.filter(TransactionModel.transaction_time >= start_dt)
                except:
                    pass

            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    query = query.filter(TransactionModel.transaction_time <= end_dt)
                except:
                    pass

            # Get total count
            total = query.count()

            # Get paginated results
            transactions = (
                query.order_by(TransactionModel.transaction_time.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Format results
            result = []
            for tx in transactions:
                result.append(
                    {
                        "transaction_id": tx.transaction_id,
                        "source": {
                            "source_id": tx.source.source_id,
                            "source_name": tx.source.source_name,
                            "source_type": tx.source.source_type.value,
                        },
                        "type": tx.transaction_type.value,
                        "asset": {
                            "asset_id": tx.asset.asset_id,
                            "symbol": tx.asset.symbol,
                            "name": tx.asset.name,
                            "chain": tx.asset.chain,
                        },
                        "quantity": float(tx.quantity),
                        "price": float(tx.price) if tx.price else None,
                        "fee": float(tx.fee) if tx.fee else None,
                        "fee_asset": (
                            {"symbol": tx.fee_asset.symbol, "chain": tx.fee_asset.chain}
                            if tx.fee_asset
                            else None
                        ),
                        "transaction_time": tx.transaction_time.isoformat(),
                        "external_tx_id": tx.external_tx_id,
                        "notes": tx.notes,
                        "created_at": tx.created_at.isoformat(),
                    }
                )

            return {
                "transactions": result,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to get transactions: {str(e)}"}


@tool
def delete_transaction(transaction_id: int, user_id: str) -> Dict:
    """
    Delete a transaction record (does not affect current positions).

    Args:
        transaction_id (int): Transaction identifier
        user_id (str): User identifier (for security check)

    Returns:
        Dict: Deletion result
    """
    try:
        with get_db() as db:
            # Get transaction and verify ownership
            transaction = (
                db.query(TransactionModel)
                .join(PortfolioSourceModel)
                .filter(
                    TransactionModel.transaction_id == transaction_id,
                    PortfolioSourceModel.user_id == user_id,
                )
                .first()
            )

            if not transaction:
                return {
                    "success": False,
                    "message": "Transaction not found or access denied",
                }

            # Store info for response
            tx_info = {
                "type": transaction.transaction_type.value,
                "asset": f"{transaction.asset.symbol} ({transaction.asset.chain})",
                "quantity": float(transaction.quantity),
                "transaction_time": transaction.transaction_time.isoformat(),
            }

            # Delete transaction
            db.delete(transaction)
            db.commit()

            return {
                "success": True,
                "message": "Transaction deleted successfully",
                "deleted_transaction": tx_info,
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to delete transaction: {str(e)}"}


# ========================================
# Price Management Tools
# ========================================


@tool
def update_asset_prices(price_updates: List[Dict]) -> Dict:
    """
    Update prices for multiple assets and update position values.

    Args:
        price_updates (List[Dict]): List of price updates, each containing:
            - symbol: Asset symbol
            - chain: Blockchain name
            - price: Current price in USD

    Returns:
        Dict: Update results with success count and errors
    """
    try:
        with get_db() as db:
            success_count = 0
            errors = []
            updated_positions = 0

            for update in price_updates:
                try:
                    # Find asset
                    asset = (
                        db.query(AssetModel)
                        .filter(
                            AssetModel.symbol == update["symbol"].upper(),
                            AssetModel.chain == update["chain"].upper(),
                        )
                        .first()
                    )

                    if not asset:
                        errors.append(
                            f"Asset {update['symbol']} on {update['chain']} not found"
                        )
                        continue

                    price = Decimal(str(update["price"]))

                    # Create price snapshot
                    snapshot = PriceSnapshotModel(
                        asset_id=asset.asset_id,
                        price=price,
                        timestamp=datetime.utcnow(),
                    )
                    db.add(snapshot)

                    # Update all positions for this asset
                    positions = (
                        db.query(PositionModel)
                        .filter(PositionModel.asset_id == asset.asset_id)
                        .all()
                    )

                    for position in positions:
                        position.last_price = price
                        updated_positions += 1

                    success_count += 1

                except Exception as e:
                    logger.error(f"Exception:{e}\n{traceback.format_exc()}")
                    errors.append(
                        f"Error updating {update.get('symbol', 'unknown')}: {str(e)}"
                    )

            db.commit()

            return {
                "success": True,
                "message": f"Updated {success_count} asset prices",
                "success_count": success_count,
                "updated_positions": updated_positions,
                "errors": errors if errors else None,
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to update asset prices: {str(e)}"}


@tool
def get_asset_price_history(symbol: str, chain: str, days: int = 7) -> List[Dict]:
    """
    Get historical price data for an asset.

    Args:
        symbol (str): Asset symbol
        chain (str): Blockchain name
        days (int): Number of days of history (default: 7)

    Returns:
        List[Dict]: Price history containing:
            - timestamp: Price timestamp
            - price: Price in USD
    """
    try:
        with get_db() as db:
            # Find asset
            asset = (
                db.query(AssetModel)
                .filter(
                    AssetModel.symbol == symbol.upper(),
                    AssetModel.chain == chain.upper(),
                )
                .first()
            )

            if not asset:
                return []

            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get price snapshots
            snapshots = (
                db.query(PriceSnapshotModel)
                .filter(
                    PriceSnapshotModel.asset_id == asset.asset_id,
                    PriceSnapshotModel.timestamp >= start_date,
                )
                .order_by(PriceSnapshotModel.timestamp)
                .all()
            )

            result = []
            for snapshot in snapshots:
                result.append(
                    {
                        "timestamp": snapshot.timestamp.isoformat(),
                        "price": float(snapshot.price),
                    }
                )

            return result

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return f"Failed to get price history: {str(e)}"


@tool
def get_latest_prices(asset_ids: List[int] = None) -> Dict:
    """
    Get latest prices for assets.

    Args:
        asset_ids (List[int], optional): Specific asset IDs to query

    Returns:
        Dict: Latest prices keyed by asset_id
    """
    try:
        with get_db() as db:
            # Subquery to get latest price timestamp for each asset
            latest_prices_subq = (
                db.query(
                    PriceSnapshotModel.asset_id,
                    func.max(PriceSnapshotModel.timestamp).label("latest_timestamp"),
                )
                .group_by(PriceSnapshotModel.asset_id)
                .subquery()
            )

            # Main query to get actual prices
            query = db.query(PriceSnapshotModel).join(
                latest_prices_subq,
                and_(
                    PriceSnapshotModel.asset_id == latest_prices_subq.c.asset_id,
                    PriceSnapshotModel.timestamp
                    == latest_prices_subq.c.latest_timestamp,
                ),
            )

            if asset_ids:
                query = query.filter(PriceSnapshotModel.asset_id.in_(asset_ids))

            snapshots = query.all()

            result = {}
            for snapshot in snapshots:
                result[snapshot.asset_id] = {
                    "price": float(snapshot.price),
                    "timestamp": snapshot.timestamp.isoformat(),
                    "asset": {
                        "symbol": snapshot.asset.symbol,
                        "chain": snapshot.asset.chain,
                        "name": snapshot.asset.name,
                    },
                }

            return result

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to get latest prices: {str(e)}"}

def fetch_price_from_api(symbol: str, chain: str = None) -> float:
    """
    从外部API获取加密货币价格
    
    Args:
        symbol (str): 加密货币符号
        chain (str, optional): 区块链名称（暂时未使用）
    
    Returns:
        float: 价格（美元），如果获取失败返回 None
    """
    try:
        # 导入 getLatestQuote 函数
        from .tools_quote import getLatestQuote
        import json
        
        # 调用 getLatestQuote 获取价格数据
        quote_data = getLatestQuote(symbol)
        
        # 如果返回的是字符串，解析 JSON
        if isinstance(quote_data, str):
            data = json.loads(quote_data)
            
            # 从 CoinMarketCap API 响应中提取价格
            if 'data' in data and symbol.upper() in data['data']:
                token_data = data['data'][symbol.upper()][0]  # 取第一个匹配项
                price = token_data['quote']['USD']['price']
                return float(price)
        
        return None
        
    except Exception as e:
        logger.error(f"获取 {symbol} 价格失败: {e}")
        return None

@tool
def refresh_all_portfolio_asset_prices(user_id: str) -> Dict:
    """
    自动刷新用户投资组合中所有资产的最新价格

    Args:
        user_id (str): 用户标识符

    Returns:
        Dict: 价格更新结果
    """
    try:
        with get_db() as db:
            # 获取用户所有活跃资产
            user_assets = (
                db.query(AssetModel)
                .join(PositionModel)
                .join(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                    PositionModel.quantity > 0,
                )
                .distinct()
                .all()
            )

            price_updates = []

            # 这里需要集成实际的价格数据源
            for asset in user_assets:
                # 示例：从外部 API 获取价格
                current_price = fetch_price_from_api(asset.symbol, asset.chain)
                if current_price:
                    price_updates.append(
                        {
                            "symbol": asset.symbol,
                            "chain": asset.chain,
                            "price": current_price,
                        }
                    )

            # 批量更新价格
            if price_updates:
                result = update_asset_prices.invoke({"price_updates": price_updates})
                return {
                    "success": True,
                    "message": f"Updated prices for {len(price_updates)} assets",
                    "updated_assets": price_updates,
                    "update_result": result,
                }
            else:
                return {"success": False, "message": "No assets found to update"}

    except Exception as e:
        logger.error(f"Exception:{e}\\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to refresh prices: {str(e)}"}

# ========================================
# Portfolio Analysis Tools
# ========================================


@tool
def calculate_portfolio_performance(
    user_id: str, start_date: str, end_date: str = None, source_id: int = None
) -> Dict:
    """
    Calculate portfolio performance metrics over a time period.

    Args:
        user_id (str): User identifier
        start_date (str): Start date for calculation (ISO format)
        end_date (str, optional): End date (default: now)
        source_id (int, optional): Specific source to analyze

    Returns:
        Dict: Performance metrics including:
            - starting_value: Portfolio value at start
            - ending_value: Portfolio value at end
            - net_deposits: Net deposits/withdrawals
            - realized_pnl: Realized profit/loss from sells
            - unrealized_pnl: Unrealized profit/loss
            - total_return: Total return percentage
            - time_weighted_return: Time-weighted return
    """
    try:
        with get_db() as db:
            # Parse dates
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end_dt = datetime.utcnow()
            if end_date:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

            # Get user sources
            query = db.query(PortfolioSourceModel).filter(
                PortfolioSourceModel.user_id == user_id,
                PortfolioSourceModel.is_active == True,
            )

            if source_id:
                query = query.filter(PortfolioSourceModel.source_id == source_id)

            sources = query.all()
            source_ids = [s.source_id for s in sources]

            if not source_ids:
                return {"error": "No active sources found"}

            # Get transactions in period
            transactions = (
                db.query(TransactionModel)
                .filter(
                    TransactionModel.source_id.in_(source_ids),
                    TransactionModel.transaction_time >= start_dt,
                    TransactionModel.transaction_time <= end_dt,
                )
                .order_by(TransactionModel.transaction_time)
                .all()
            )

            # Calculate metrics
            net_deposits = Decimal("0")
            realized_pnl = Decimal("0")

            for tx in transactions:
                if tx.transaction_type in [TransactionType.DEPOSIT]:
                    net_deposits += tx.quantity * (tx.price or Decimal("0"))
                elif tx.transaction_type in [TransactionType.WITHDRAW]:
                    net_deposits -= tx.quantity * (tx.price or Decimal("0"))
                elif tx.transaction_type == TransactionType.SELL and tx.price:
                    # Calculate realized P&L (simplified - would need cost basis tracking)
                    realized_pnl += tx.quantity * tx.price

            # Get current positions and values
            positions = (
                db.query(PositionModel)
                .filter(PositionModel.source_id.in_(source_ids))
                .all()
            )

            ending_value = Decimal("0")
            unrealized_pnl = Decimal("0")

            for position in positions:
                if position.last_price and position.quantity > 0:
                    position_value = position.quantity * position.last_price
                    ending_value += position_value

                    if position.avg_cost:
                        cost_basis = position.quantity * position.avg_cost
                        unrealized_pnl += position_value - cost_basis

            # Simplified starting value calculation
            # In production, would need historical position snapshots
            starting_value = ending_value - net_deposits - realized_pnl - unrealized_pnl

            # Calculate returns
            total_return = Decimal("0")
            if starting_value > 0:
                total_return = (
                    (ending_value - starting_value - net_deposits) / starting_value
                ) * 100

            return {
                "period": {
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "days": (end_dt - start_dt).days,
                },
                "starting_value": float(starting_value),
                "ending_value": float(ending_value),
                "net_deposits": float(net_deposits),
                "realized_pnl": float(realized_pnl),
                "unrealized_pnl": float(unrealized_pnl),
                "total_pnl": float(realized_pnl + unrealized_pnl),
                "total_return": float(total_return),
                "source_count": len(sources),
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to calculate performance: {str(e)}"}


@tool
def get_portfolio_allocation(user_id: str, group_by: str = "asset") -> List[Dict]:
    """
    Get portfolio allocation breakdown.

    Args:
        user_id (str): User identifier
        group_by (str): Grouping method ('asset', 'chain', 'source_type')

    Returns:
        List[Dict]: Allocation breakdown with percentages
    """
    try:
        with get_db() as db:
            # Get user's active sources
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            source_ids = [s.source_id for s in sources]

            if not source_ids:
                return []

            # Get all positions with values
            positions = (
                db.query(PositionModel)
                .filter(
                    PositionModel.source_id.in_(source_ids), PositionModel.quantity > 0
                )
                .all()
            )

            # Calculate allocations based on grouping
            allocations = {}
            total_value = Decimal("0")

            for position in positions:
                if not position.last_price:
                    continue

                value = position.quantity * position.last_price
                total_value += value

                # Determine grouping key
                if group_by == "asset":
                    key = f"{position.asset.symbol} ({position.asset.chain})"
                    metadata = {
                        "symbol": position.asset.symbol,
                        "chain": position.asset.chain,
                        "name": position.asset.name,
                    }
                elif group_by == "chain":
                    key = position.asset.chain
                    metadata = {"chain": position.asset.chain}
                elif group_by == "source_type":
                    source = next(
                        s for s in sources if s.source_id == position.source_id
                    )
                    key = source.source_type.value
                    metadata = {"source_type": source.source_type.value}
                else:
                    key = "Unknown"
                    metadata = {}

                if key not in allocations:
                    allocations[key] = {
                        "key": key,
                        "value": Decimal("0"),
                        "quantity": Decimal("0"),
                        "metadata": metadata,
                    }

                allocations[key]["value"] += value
                allocations[key]["quantity"] += position.quantity

            # Convert to list with percentages
            result = []
            if total_value > 0:
                for key, data in allocations.items():
                    result.append(
                        {
                            "group": key,
                            "value": float(data["value"]),
                            "percentage": float((data["value"] / total_value) * 100),
                            "metadata": data["metadata"],
                        }
                    )

            # Sort by value descending
            result.sort(key=lambda x: x["value"], reverse=True)

            return result

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return f"Failed to get portfolio allocation: {str(e)}"


# ========================================
# Integration and Sync Tools
# ========================================


@tool
def sync_wallet_balances(source_id: int, user_id: str) -> Dict:
    """
    Sync wallet balances from blockchain (requires external API integration).

    Args:
        source_id (int): Wallet source identifier
        user_id (str): User identifier (for security check)

    Returns:
        Dict: Sync results with updated positions
    """
    try:
        with get_db() as db:
            # Verify source ownership and type
            source = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.source_id == source_id,
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.source_type == SourceType.WALLET,
                )
                .first()
            )

            if not source:
                return {
                    "success": False,
                    "message": "Wallet source not found or access denied",
                }

            # Extract wallet info from config
            wallet_address = source.source_config.get("wallet_address")
            chain = source.source_config.get("chain")

            if not wallet_address or not chain:
                return {"success": False, "message": "Invalid wallet configuration"}

            # Here you would integrate with blockchain APIs to get actual balances
            # For now, returning a placeholder response

            # Update last sync timestamp
            source.last_sync_at = datetime.utcnow()
            db.commit()

            return {
                "success": True,
                "message": "Wallet sync completed",
                "source": {
                    "source_id": source.source_id,
                    "source_name": source.source_name,
                    "wallet_address": wallet_address,
                    "chain": chain,
                },
                "last_sync_at": source.last_sync_at.isoformat(),
                "note": "This is a placeholder. Actual blockchain integration required.",
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to sync wallet: {str(e)}"}


@tool
def import_transactions_csv(
    source_id: int, user_id: str, csv_data: str, date_format: str = "%Y-%m-%d %H:%M:%S"
) -> Dict:
    """
    Import transactions from CSV data.

    Args:
        source_id (int): Source identifier
        user_id (str): User identifier (for security check)
        csv_data (str): CSV formatted transaction data
        date_format (str): Date format in CSV (default: "%Y-%m-%d %H:%M:%S")

    Expected CSV columns:
        - date: Transaction date
        - type: Transaction type (BUY, SELL, etc.)
        - symbol: Asset symbol
        - chain: Blockchain name
        - quantity: Transaction quantity
        - price: Price per unit (optional)
        - fee: Transaction fee (optional)
        - notes: Additional notes (optional)

    Returns:
        Dict: Import results with success/error counts
    """
    try:
        with get_db() as db:
            import csv
            from io import StringIO

            # Verify source ownership
            source = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.source_id == source_id,
                    PortfolioSourceModel.user_id == user_id,
                )
                .first()
            )

            if not source:
                return {
                    "success": False,
                    "message": "Source not found or access denied",
                }

            # Parse CSV
            csv_file = StringIO(csv_data)
            reader = csv.DictReader(csv_file)

            success_count = 0
            error_count = 0
            errors = []

            for row_num, row in enumerate(
                reader, start=2
            ):  # Start at 2 to account for header
                try:
                    # Parse transaction data
                    tx_date = datetime.strptime(row["date"], date_format)
                    tx_type = row["type"].upper()
                    symbol = row["symbol"].upper()
                    chain = row["chain"].upper()
                    quantity = Decimal(row["quantity"])
                    price = Decimal(row["price"]) if row.get("price") else None
                    fee = Decimal(row["fee"]) if row.get("fee") else Decimal("0")
                    notes = row.get("notes", "")

                    # Find asset
                    asset = (
                        db.query(AssetModel)
                        .filter(AssetModel.symbol == symbol, AssetModel.chain == chain)
                        .first()
                    )

                    if not asset:
                        errors.append(
                            f"Row {row_num}: Asset {symbol} on {chain} not found"
                        )
                        error_count += 1
                        continue

                    # Create transaction
                    transaction = TransactionModel(
                        source_id=source_id,
                        transaction_type=TransactionType(tx_type),
                        asset_id=asset.asset_id,
                        quantity=quantity,
                        price=price,
                        fee=fee,
                        transaction_time=tx_date,
                        notes=f"CSV Import: {notes}" if notes else "CSV Import",
                    )

                    db.add(transaction)
                    success_count += 1

                except Exception as e:
                    logger.error(f"Exception:{e}\n{traceback.format_exc()}")
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1

            db.commit()

            return {
                "success": True,
                "message": f"Import completed: {success_count} transactions imported",
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors[:10] if errors else None,  # Limit errors shown
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to import transactions: {str(e)}"}


@tool
def export_portfolio_report(
    user_id: str,
    format: str = "summary",
    include_transactions: bool = False,
    include_performance: bool = False,
) -> Dict:
    """
    Export portfolio report in various formats.

    Args:
        user_id (str): User identifier
        format (str): Report format ('summary', 'detailed', 'tax')
        include_transactions (bool): Include transaction history
        include_performance (bool): Include performance metrics

    Returns:
        Dict: Portfolio report data
    """
    try:
        report = {
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat(),
            "format": format,
        }

        # Get portfolio summary
        summary = get_user_portfolio_summary.invoke({"user_id": user_id})
        if not isinstance(summary, dict) or "error" in summary:
            return {"error": "Failed to generate portfolio summary"}

        report["summary"] = summary

        # Add performance metrics if requested
        if include_performance:
            # Calculate YTD performance
            year_start = datetime(datetime.utcnow().year, 1, 1).isoformat()
            performance = calculate_portfolio_performance.invoke(
                {"user_id": user_id, "start_date": year_start}
            )

            if isinstance(performance, dict) and "error" not in performance:
                report["performance"] = performance

        # Add transactions if requested
        if include_transactions:
            transactions = get_transactions.invoke(
                {"user_id": user_id, "limit": 1000}  # Reasonable limit for export
            )

            if isinstance(transactions, dict) and "error" not in transactions:
                report["transactions"] = transactions["transactions"]

        # Add format-specific data
        if format == "tax":
            # Add tax-specific calculations
            report["tax_summary"] = {
                "realized_gains": 0,  # Would need proper calculation
                "realized_losses": 0,
                "net_gain_loss": 0,
                "note": "Consult a tax professional for accurate tax reporting",
            }

        return report

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to export portfolio report: {str(e)}"}


# ========================================
# Helper Tools
# ========================================


@tool
def validate_portfolio_data(user_id: str) -> Dict:
    """
    Validate portfolio data integrity and identify issues.

    Args:
        user_id (str): User identifier

    Returns:
        Dict: Validation results with any issues found
    """
    try:
        with get_db() as db:
            issues = []

            # Get user's sources
            sources = (
                db.query(PortfolioSourceModel)
                .filter(PortfolioSourceModel.user_id == user_id)
                .all()
            )

            source_ids = [s.source_id for s in sources]

            # Check for orphaned positions
            orphaned_positions = (
                db.query(PositionModel)
                .filter(
                    PositionModel.source_id.in_(source_ids), PositionModel.quantity <= 0
                )
                .count()
            )

            if orphaned_positions > 0:
                issues.append(
                    {
                        "type": "ZERO_POSITIONS",
                        "severity": "LOW",
                        "message": f"Found {orphaned_positions} positions with zero or negative quantity",
                    }
                )

            # Check for missing prices
            positions_without_prices = (
                db.query(PositionModel)
                .filter(
                    PositionModel.source_id.in_(source_ids),
                    PositionModel.quantity > 0,
                    PositionModel.last_price == None,
                )
                .count()
            )

            if positions_without_prices > 0:
                issues.append(
                    {
                        "type": "MISSING_PRICES",
                        "severity": "MEDIUM",
                        "message": f"Found {positions_without_prices} positions without price data",
                    }
                )

            # Check for inactive sources with positions
            inactive_with_positions = (
                db.query(PortfolioSourceModel)
                .join(PositionModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == False,
                    PositionModel.quantity > 0,
                )
                .distinct()
                .count()
            )

            if inactive_with_positions > 0:
                issues.append(
                    {
                        "type": "INACTIVE_SOURCES",
                        "severity": "HIGH",
                        "message": f"Found {inactive_with_positions} inactive sources with active positions",
                    }
                )

            # Check for duplicate transactions
            duplicate_check = (
                db.query(
                    TransactionModel.external_tx_id,
                    func.count(TransactionModel.transaction_id).label("count"),
                )
                .filter(
                    TransactionModel.source_id.in_(source_ids),
                    TransactionModel.external_tx_id != None,
                )
                .group_by(TransactionModel.external_tx_id)
                .having(func.count(TransactionModel.transaction_id) > 1)
                .all()
            )

            if duplicate_check:
                issues.append(
                    {
                        "type": "DUPLICATE_TRANSACTIONS",
                        "severity": "MEDIUM",
                        "message": f"Found {len(duplicate_check)} potential duplicate transactions",
                    }
                )

            return {
                "validation_complete": True,
                "issues_found": len(issues),
                "issues": issues,
                "recommendation": (
                    "Address HIGH severity issues first"
                    if issues
                    else "No issues found"
                ),
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to validate portfolio data: {str(e)}"}


# Export all tools
tools = [
    # Asset Source Management
    get_user_asset_sources,
    add_wallet_source,
    add_exchange_source,
    add_defi_source,
    update_asset_source,
    delete_asset_source,
    # Asset Management
    search_assets,
    add_custom_asset,
    # Position Management
    update_position,
    get_source_positions,
    get_user_portfolio_summary,
    get_position_history,
    # Transaction Management
    record_transaction,
    get_transactions,
    delete_transaction,
    # Price Management
    update_asset_prices,
    get_asset_price_history,
    get_latest_prices,
	refresh_all_portfolio_asset_prices,
    # Portfolio Analysis
    calculate_portfolio_performance,
    get_portfolio_allocation,
    # Integration and Sync
    sync_wallet_balances,
    import_transactions_csv,
    export_portfolio_report,
    # Helper Tools
    validate_portfolio_data,
] + tools_analysis
