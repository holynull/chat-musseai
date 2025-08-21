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
        from tools.tools_quote import getLatestQuote
        import json

        # 调用 getLatestQuote 获取价格数据
        quote_data = getLatestQuote.invoke({"symbol": symbol})

        # 如果返回的是字符串，解析 JSON
        if isinstance(quote_data, str):
            data = json.loads(quote_data)

            # 从 CoinMarketCap API 响应中提取价格
            if "data" in data and symbol.upper() in data["data"]:
                token_data = data["data"][symbol.upper()][0]  # 取第一个匹配项
                price = token_data["quote"]["USD"]["price"]
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
