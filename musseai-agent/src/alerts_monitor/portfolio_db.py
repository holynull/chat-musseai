from datetime import datetime
from typing import  Dict
from mysql.db import get_db
from mysql.model import (
    PortfolioSourceModel,
    AssetModel,
    PositionModel,
    TransactionModel,
    TransactionType,
)
from loggers import logger
import traceback

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
                        "asset_id": asset.asset_id,
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
                        "asset_id": asset_data["asset_id"],
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