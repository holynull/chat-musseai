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


def fetch_price_from_api(symbols: str, chain: str = None) -> Dict:
    """
    Fetch cryptocurrency prices from external API
    """
    try:
        from utils.api.cryptocompare import getLatestQuote
        import json

        if not symbols or not symbols.strip():
            logger.error("Empty symbols parameter provided")
            return {}

        clean_symbols = ",".join([s.strip().upper() for s in symbols.split(",")])
        logger.info(f"Fetching prices for symbols: {clean_symbols}")

        quote_data = getLatestQuote(symbols=clean_symbols)
        prices = {}

        # Parse JSON response if returned as string
        if isinstance(quote_data, str):
            try:
                data = json.loads(quote_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return {}

            # Handle error response
            if data.get("error", False):
                logger.error(f"API error: {data.get('message', 'Unknown error')}")
                return {}

            # Extract prices from CryptoCompare API response (CORRECTED)
            if "data" in data and isinstance(data["data"], dict):
                for symbol in clean_symbols.split(","):
                    symbol = symbol.strip().upper()
                    if symbol in data["data"]:
                        symbol_data = data["data"][symbol]
                        
                        # Check if this is an error entry
                        if "error" in symbol_data:
                            logger.warning(f"Error for symbol {symbol}: {symbol_data['error']}")
                            prices[symbol] = None
                            continue

                        try:
                            # CORRECT path for CryptoCompare: data[symbol].prices.USD.price_raw
                            if "prices" in symbol_data and "USD" in symbol_data["prices"]:
                                price_raw = symbol_data["prices"]["USD"]["price_raw"]
                                prices[symbol] = float(price_raw)
                                logger.info(f"Successfully fetched price for {symbol}: ${price_raw}")
                            else:
                                logger.warning(f"USD price not available for {symbol}")
                                prices[symbol] = None
                        except (KeyError, TypeError, ValueError) as e:
                            logger.warning(f"Failed to extract price for {symbol}: {e}")
                            prices[symbol] = None
                    else:
                        logger.warning(f"No data found for symbol: {symbol}")
                        prices[symbol] = None
            else:
                logger.error("Invalid API response structure - missing or invalid 'data' field")
                return {}

        elif isinstance(quote_data, dict):
            # Handle direct dictionary response (same logic as above)
            if quote_data.get("error", False):
                logger.error(f"API error: {quote_data.get('message', 'Unknown error')}")
                return {}

            if "data" in quote_data:
                for symbol in clean_symbols.split(","):
                    symbol = symbol.strip().upper()
                    if symbol in quote_data["data"]:
                        symbol_data = quote_data["data"][symbol]
                        
                        if "error" in symbol_data:
                            logger.warning(f"Error for symbol {symbol}: {symbol_data['error']}")
                            prices[symbol] = None
                            continue

                        try:
                            # CORRECT path for CryptoCompare
                            if "prices" in symbol_data and "USD" in symbol_data["prices"]:
                                price_raw = symbol_data["prices"]["USD"]["price_raw"]
                                prices[symbol] = float(price_raw)
                                logger.info(f"Successfully fetched price for {symbol}: ${price_raw}")
                            else:
                                logger.warning(f"USD price not available for {symbol}")
                                prices[symbol] = None
                        except (KeyError, TypeError, ValueError) as e:
                            logger.warning(f"Failed to extract price for {symbol}: {e}")
                            prices[symbol] = None
                    else:
                        logger.warning(f"No data found for symbol: {symbol}")
                        prices[symbol] = None
            else:
                logger.error("Invalid response structure - missing 'data' field")
                return {}
        else:
            logger.error(f"Unexpected response type: {type(quote_data)}")
            return {}

        return prices

    except Exception as e:
        logger.error(f"Failed to fetch prices for {symbols}: {e}")
        return {}



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

            # Collect all unique symbols
            symbols_to_fetch = list(set(asset.symbol for asset in user_assets))
            symbols_string = ",".join(symbols_to_fetch)

            # Batch fetch all prices at once
            all_prices = fetch_price_from_api(symbols_string)

            price_updates = []
            for asset in user_assets:
                current_price = all_prices.get(asset.symbol) if all_prices else None
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
