import logging
import traceback
import json
from datetime import datetime
from typing import List, Dict, Optional, Union, Any
from langchain.agents import tool
from sqlalchemy.sql import func, text
from mysql.db import get_db
from mysql.model import (
    AssetSourceTypeModel,
    AssetSourceModel,
    SupportedExchangeModel,
    CryptoAssetModel,
    AssetPositionModel,
    PositionHistoryNewModel,
    AssetTransactionModel,
)


@tool
def get_user_asset_sources(user_id: str) -> Dict:
    """
    Get all asset sources for a user (wallets, exchanges, etc.).

    Args:
        user_id (str): The user ID

    Returns:
        Dict: Returns a dictionary containing user's asset sources
    """
    try:
        with get_db() as db:
            # Get all asset sources for the user
            sources = (
                db.query(AssetSourceModel, AssetSourceTypeModel)
                .join(
                    AssetSourceTypeModel,
                    AssetSourceModel.source_type_id
                    == AssetSourceTypeModel.source_type_id,
                )
                .filter(AssetSourceModel.user_id == user_id)
                .all()
            )

            result = {
                "user_id": user_id,
                "source_count": len(sources),
                "sources": [
                    {
                        "source_id": source.source_id,
                        "source_name": source.source_name,
                        "source_type": source_type.type_name,
                        "source_details": source.source_details,
                        "created_at": (
                            source.created_at.isoformat() if source.created_at else None
                        ),
                        "last_sync_time": (
                            source.last_sync_time.isoformat()
                            if source.last_sync_time
                            else None
                        ),
                    }
                    for source, source_type in sources
                ],
            }

            return result
    except Exception as e:
        logging.error(
            f"Failed to get user asset sources: {str(e)}\n{traceback.format_exc()}"
        )
        return {"error": f"Failed to get user asset sources: {str(e)}"}


@tool
def add_wallet_source(
    user_id: str,
    wallet_address: str,
    chain_type: str,
    source_name: Optional[str] = None,
) -> Dict:
    """
    Add a new wallet as an asset source for a user.

    Args:
        user_id (str): The user ID
        wallet_address (str): The wallet address
        chain_type (str): Chain type, such as ETH, BSC, SOL, etc.
        source_name (str, optional): Name for this source, defaults to last 6 chars of address

    Returns:
        Dict: Returns the operation result
    """
    try:
        with get_db() as db:
            # Get the WALLET source type
            wallet_type = (
                db.query(AssetSourceTypeModel)
                .filter(AssetSourceTypeModel.type_name == "WALLET")
                .first()
            )

            if not wallet_type:
                # Create the WALLET source type if it doesn't exist
                wallet_type = AssetSourceTypeModel(
                    type_name="WALLET", description="Blockchain wallet addresses"
                )
                db.add(wallet_type)
                db.flush()

            # Set default source name if not provided
            if not source_name:
                source_name = f"{wallet_address[-6:]} ({chain_type})"

            # Check if the wallet already exists for this user
            existing_source = (
                db.query(AssetSourceModel)
                .filter(
                    AssetSourceModel.user_id == user_id,
                    AssetSourceModel.source_type_id == wallet_type.source_type_id,
                )
                .filter(
                    AssetSourceModel.source_details.contains(
                        {"address": wallet_address, "chain": chain_type}
                    )
                )
                .first()
            )

            if existing_source:
                return {"error": "This wallet address already exists"}

            # Create new asset source for wallet
            new_source = AssetSourceModel(
                user_id=user_id,
                source_type_id=wallet_type.source_type_id,
                source_name=source_name,
                source_details={"address": wallet_address, "chain": chain_type},
            )

            db.add(new_source)
            db.commit()
            db.refresh(new_source)

            return {
                "success": True,
                "source_id": new_source.source_id,
                "message": f"Successfully added wallet {wallet_address} as asset source for user {user_id}",
            }
    except Exception as e:
        logging.error(
            f"Failed to add wallet source: {str(e)}\n{traceback.format_exc()}"
        )
        return {"error": f"Failed to add wallet source: {str(e)}"}


@tool
def add_exchange_source(
    user_id: str,
    exchange_name: str,
    source_name: Optional[str] = None,
    account_description: Optional[str] = None,
) -> Dict:
    """
    Add a new exchange account as an asset source for a user.

    Args:
        user_id (str): The user ID
        exchange_name (str): Exchange name (e.g., Binance, Coinbase)
        source_name (str, optional): Name for this source, defaults to "Exchange Name Account"
        account_description (str, optional): Account description

    Returns:
        Dict: Returns the operation result
    """
    try:
        with get_db() as db:
            # Check if the exchange is supported
            exchange = (
                db.query(SupportedExchangeModel)
                .filter(
                    SupportedExchangeModel.exchange_name == exchange_name,
                    SupportedExchangeModel.status == 1,
                )
                .first()
            )

            if not exchange:
                return {"error": f"Exchange {exchange_name} is not supported"}

            # Get the EXCHANGE source type
            exchange_type = (
                db.query(AssetSourceTypeModel)
                .filter(AssetSourceTypeModel.type_name == "EXCHANGE")
                .first()
            )

            if not exchange_type:
                # Create the EXCHANGE source type if it doesn't exist
                exchange_type = AssetSourceTypeModel(
                    type_name="EXCHANGE", description="Cryptocurrency exchanges"
                )
                db.add(exchange_type)
                db.flush()

            # Set default source name
            if not source_name:
                source_name = f"{exchange_name} Account"

            # Create new asset source for exchange
            new_source = AssetSourceModel(
                user_id=user_id,
                source_type_id=exchange_type.source_type_id,
                source_name=source_name,
                source_details={
                    "exchange": exchange_name,
                    "description": account_description or f"{exchange_name} Account",
                },
            )

            db.add(new_source)
            db.commit()
            db.refresh(new_source)

            return {
                "success": True,
                "source_id": new_source.source_id,
                "message": f"Successfully added {exchange_name} exchange account as asset source for user {user_id}",
            }
    except Exception as e:
        logging.error(
            f"Failed to add exchange account: {str(e)}\n{traceback.format_exc()}"
        )
        return {"error": f"Failed to add exchange account: {str(e)}"}


@tool
def add_defi_source(
    user_id: str,
    protocol_name: str,
    chain_type: str,
    wallet_address: str,
    protocol_contract: Optional[str] = None,
    source_name: Optional[str] = None,
    protocol_details: Optional[Dict] = None,
) -> Dict:
    """Add a DeFi protocol as an asset source for a user.

    Args:
        user_id (str): The user ID
        protocol_name (str): DeFi protocol name (e.g., Uniswap, Aave, Curve)
        chain_type (str): Chain type where the protocol is deployed (e.g., ETH, BSC)
        wallet_address (str): User's wallet address interacting with the protocol
        protocol_contract (str, optional): Main contract address of the protocol
        source_name (str, optional): Custom name for this source
        protocol_details (Dict, optional): Additional protocol-specific details such as:
            - pool_id: Specific pool or market identifier
            - asset_types: Types of assets involved (LP tokens, debt positions, etc.)
            - protocol_version: Version of the protocol
            - strategy_type: Type of strategy (lending, liquidity provision, etc.)

    Returns:
        Dict: Returns the operation result
    """
    try:
        with get_db() as db:
            # Get the DEFI source type
            defi_type = (
                db.query(AssetSourceTypeModel)
                .filter(AssetSourceTypeModel.type_name == "DEFI")
                .first()
            )

            if not defi_type:
                # Create the DEFI source type if it doesn't exist
                defi_type = AssetSourceTypeModel(
                    type_name="DEFI",
                    description="Decentralized Finance protocols and positions",
                )
                db.add(defi_type)
                db.flush()

            # Set default source name if not provided
            if not source_name:
                source_name = f"{protocol_name} on {chain_type}"

            # Prepare protocol details
            source_details = {
                "protocol_name": protocol_name,
                "chain_type": chain_type,
                "wallet_address": wallet_address,
                "protocol_contract": protocol_contract,
                "created_at": datetime.utcnow().isoformat(),
            }

            # Add additional protocol details if provided
            if protocol_details:
                source_details.update(protocol_details)

            # Check if a similar DeFi source already exists
            existing_source = (
                db.query(AssetSourceModel)
                .filter(
                    AssetSourceModel.user_id == user_id,
                    AssetSourceModel.source_type_id == defi_type.source_type_id,
                )
                .filter(
                    AssetSourceModel.source_details.contains(
                        {
                            "protocol_name": protocol_name,
                            "chain_type": chain_type,
                            "wallet_address": wallet_address,
                        }
                    )
                )
                .first()
            )

            if existing_source:
                if (
                    protocol_contract
                    and existing_source.source_details.get("protocol_contract")
                    == protocol_contract
                ):
                    return {
                        "error": "A DeFi source with the same protocol, chain, wallet, and contract already exists"
                    }

            # Create new asset source for DeFi protocol
            new_source = AssetSourceModel(
                user_id=user_id,
                source_type_id=defi_type.source_type_id,
                source_name=source_name,
                source_details=source_details,
            )

            db.add(new_source)
            db.commit()
            db.refresh(new_source)

            # Add default assets for the protocol if needed
            if protocol_details and protocol_details.get("default_assets"):
                for asset_info in protocol_details["default_assets"]:
                    try:
                        # Check if asset exists
                        asset = (
                            db.query(CryptoAssetModel)
                            .filter(
                                CryptoAssetModel.asset_symbol == asset_info["symbol"],
                                CryptoAssetModel.chain_type == chain_type,
                            )
                            .first()
                        )

                        if not asset:
                            # Create new asset
                            asset = CryptoAssetModel(
                                asset_symbol=asset_info["symbol"],
                                asset_name=asset_info.get("name", asset_info["symbol"]),
                                chain_type=chain_type,
                                contract_address=asset_info.get("contract_address"),
                                decimals=asset_info.get("decimals", 18),
                                status=1,
                            )
                            db.add(asset)
                            db.flush()

                        # Create initial position with zero quantity
                        position = AssetPositionModel(
                            source_id=new_source.source_id,
                            asset_id=asset.asset_id,
                            quantity=0,
                            additional_data=asset_info.get("position_details", {}),
                            last_updated_at=func.now(),
                        )
                        db.add(position)

                    except Exception as asset_error:
                        logging.warning(
                            f"Failed to add default asset {asset_info['symbol']}: {str(asset_error)}"
                        )

                db.commit()

            return {
                "success": True,
                "source_id": new_source.source_id,
                "source_name": source_name,
                "message": (
                    f"Successfully added {protocol_name} on {chain_type} "
                    f"as DeFi source for user {user_id}"
                ),
                "details": source_details,
            }

    except Exception as e:
        logging.error(f"Failed to add DeFi source: {str(e)}\n{traceback.format_exc()}")
        return {"error": f"Failed to add DeFi source: {str(e)}"}


@tool
def get_source_positions(source_id: int) -> Dict:
    """Get all asset positions for a specified source.

    Args:
        source_id (int): The source ID

    Returns:
        Dict: Returns a dictionary containing the source's asset positions
    """
    try:
        with get_db() as db:
            # Get the source and its type
            source_data = (
                db.query(AssetSourceModel, AssetSourceTypeModel)
                .join(
                    AssetSourceTypeModel,
                    AssetSourceModel.source_type_id
                    == AssetSourceTypeModel.source_type_id,
                )
                .filter(AssetSourceModel.source_id == source_id)
                .first()
            )

            if not source_data:
                return {"error": f"Source ID {source_id} does not exist"}

            source, source_type = source_data

            # Get all positions for this source
            positions = (
                db.query(AssetPositionModel, CryptoAssetModel)
                .join(
                    CryptoAssetModel,
                    AssetPositionModel.asset_id == CryptoAssetModel.asset_id,
                )
                .filter(AssetPositionModel.source_id == source_id)
                .all()
            )

            result = {
                "source_id": source_id,
                "source_name": source.source_name,
                "source_type": source_type.type_name,
                "source_details": source.source_details,
                "position_count": len(positions),
                "positions": [
                    {
                        "asset_symbol": asset.asset_symbol,
                        "asset_name": asset.asset_name,
                        "chain_type": asset.chain_type,
                        "quantity": float(position.quantity),
                        "cost_basis": (
                            float(position.cost_basis) if position.cost_basis else None
                        ),
                        "last_updated_at": (
                            position.last_updated_at.isoformat()
                            if position.last_updated_at
                            else None
                        ),
                        "additional_data": position.additional_data,
                    }
                    for position, asset in positions
                ],
            }

            return result
    except Exception as e:
        logging.error(
            f"Failed to get source positions: {str(e)}\n{traceback.format_exc()}"
        )
        return {"error": f"Failed to get source positions: {str(e)}"}


@tool
def update_position(
    source_id: int,
    asset_symbol: str,
    quantity: float,
    cost_basis: Optional[float] = None,
    agent_id: str = "crypto_portfolio_agent",
    conversation_id: Optional[str] = None,
    sync_type: str = "MANUAL",
    operation_type: Optional[str] = None,
    additional_data: Optional[Dict] = None,
) -> Dict:
    """Update an asset position for a source.

    Args:
        source_id (int): The source ID
        asset_symbol (str): Asset symbol (e.g., BTC, ETH)
        quantity (float): New quantity
        cost_basis (float, optional): Cost basis per unit
        agent_id (str): Agent identifier
        conversation_id (str, optional): Conversation ID
        sync_type (str): Sync type (MANUAL, API, BLOCKCHAIN)
        operation_type (str, optional): Operation type (DEPOSIT, WITHDRAW, TRADE)
        additional_data (Dict, optional): Additional data for the position

    Returns:
        Dict: Returns the operation result
    """
    try:
        with get_db() as db:
            # Get the source and its type
            source_data = (
                db.query(AssetSourceModel, AssetSourceTypeModel)
                .join(
                    AssetSourceTypeModel,
                    AssetSourceModel.source_type_id
                    == AssetSourceTypeModel.source_type_id,
                )
                .filter(AssetSourceModel.source_id == source_id)
                .first()
            )

            if not source_data:
                return {"error": f"Source ID {source_id} does not exist"}

            source, source_type = source_data

            # Find the asset based on source type
            if source_type.type_name == "WALLET":
                chain_type = source.source_details.get("chain")
                asset = (
                    db.query(CryptoAssetModel)
                    .filter(
                        CryptoAssetModel.asset_symbol == asset_symbol,
                        CryptoAssetModel.chain_type == chain_type,
                    )
                    .first()
                )
            else:
                asset = (
                    db.query(CryptoAssetModel)
                    .filter(CryptoAssetModel.asset_symbol == asset_symbol)
                    .first()
                )

            if not asset:
                # Try to create the asset if it doesn't exist
                try:
                    if source_type.type_name == "WALLET":
                        chain_type = source.source_details.get("chain")
                        asset = CryptoAssetModel(
                            asset_symbol=asset_symbol,
                            asset_name=asset_symbol,  # Use symbol as default name
                            chain_type=chain_type,
                            status=1,
                        )
                    else:
                        # Use general chain type for exchanges
                        asset = CryptoAssetModel(
                            asset_symbol=asset_symbol,
                            asset_name=asset_symbol,
                            chain_type="GENERAL",
                            status=1,
                        )
                    db.add(asset)
                    db.flush()
                except Exception as asset_error:
                    return {
                        "error": f"Asset {asset_symbol} not found and cannot be created: {str(asset_error)}"
                    }

            # Get current position or create new one
            position = (
                db.query(AssetPositionModel)
                .filter(
                    AssetPositionModel.source_id == source_id,
                    AssetPositionModel.asset_id == asset.asset_id,
                )
                .first()
            )

            old_quantity = 0
            if position:
                old_quantity = float(position.quantity)
                position.quantity = quantity
                if cost_basis is not None:
                    position.cost_basis = cost_basis
                if additional_data is not None:
                    position.additional_data = additional_data
                position.last_updated_at = func.now()
                db.add(position)
            else:
                position = AssetPositionModel(
                    source_id=source_id,
                    asset_id=asset.asset_id,
                    quantity=quantity,
                    cost_basis=cost_basis,
                    additional_data=additional_data,
                    last_updated_at=func.now(),
                )
                db.add(position)

            # Record position history
            history = PositionHistoryNewModel(
                source_id=source_id,
                asset_id=asset.asset_id,
                quantity=quantity,
                change_amount=quantity - old_quantity,
                agent_id=agent_id,
                conversation_id=conversation_id,
                sync_type=sync_type,
                operation_type=operation_type
                or ("DEPOSIT" if quantity > old_quantity else "WITHDRAW"),
                operation_details={
                    "cost_basis": cost_basis,
                    "source_type": source_type.type_name,
                    "additional_data": additional_data,
                },
            )
            db.add(history)

            # Record transaction if it's a trade operation
            if operation_type == "TRADE":
                transaction = AssetTransactionModel(
                    user_id=source.user_id,
                    source_id=source_id,
                    transaction_type="TRADE",
                    base_asset_id=asset.asset_id,
                    base_amount=abs(quantity - old_quantity),
                    price=cost_basis if cost_basis is not None else 0,
                    transaction_time=datetime.utcnow(),
                    status="COMPLETED",
                    additional_info={
                        "agent_id": agent_id,
                        "conversation_id": conversation_id,
                        "sync_type": sync_type,
                        "old_quantity": old_quantity,
                        "new_quantity": quantity,
                    },
                )
                db.add(transaction)

            db.commit()

            return {
                "success": True,
                "source_id": source_id,
                "asset_symbol": asset_symbol,
                "old_quantity": old_quantity,
                "new_quantity": quantity,
                "change": quantity - old_quantity,
                "message": "Successfully updated position",
            }

    except Exception as e:
        logging.error(f"Failed to update position: {str(e)}\n{traceback.format_exc()}")
        return {"error": f"Failed to update position: {str(e)}"}


@tool
def get_position_history(
    source_id: int,
    asset_symbol: Optional[str] = None,
    limit: int = 10,
    sync_type: Optional[str] = None,
    operation_type: Optional[str] = None,
) -> Dict:
    """Get position history for a source.

    Args:
        source_id (int): The source ID
        asset_symbol (str, optional): Filter by asset symbol
        limit (int): Maximum number of records to return
        sync_type (str, optional): Filter by sync type
        operation_type (str, optional): Filter by operation type

    Returns:
        Dict: Returns the position history
    """
    try:
        with get_db() as db:
            # Build the query
            query = (
                db.query(PositionHistoryNewModel, CryptoAssetModel)
                .join(
                    CryptoAssetModel,
                    PositionHistoryNewModel.asset_id == CryptoAssetModel.asset_id,
                )
                .filter(PositionHistoryNewModel.source_id == source_id)
            )

            if asset_symbol:
                query = query.filter(CryptoAssetModel.asset_symbol == asset_symbol)
            if sync_type:
                query = query.filter(PositionHistoryNewModel.sync_type == sync_type)
            if operation_type:
                query = query.filter(
                    PositionHistoryNewModel.operation_type == operation_type
                )

            # Get the records
            history_records = (
                query.order_by(PositionHistoryNewModel.created_at.desc())
                .limit(limit)
                .all()
            )

            result = {
                "source_id": source_id,
                "filter_criteria": {
                    "asset_symbol": asset_symbol,
                    "sync_type": sync_type,
                    "operation_type": operation_type,
                },
                "record_count": len(history_records),
                "history": [
                    {
                        "history_id": history.history_id,
                        "asset_symbol": asset.asset_symbol,
                        "asset_name": asset.asset_name,
                        "quantity": float(history.quantity),
                        "change_amount": float(history.change_amount),
                        "sync_type": history.sync_type,
                        "operation_type": history.operation_type,
                        "operation_details": history.operation_details,
                        "created_at": (
                            history.created_at.isoformat()
                            if history.created_at
                            else None
                        ),
                        "agent_id": history.agent_id,
                        "conversation_id": history.conversation_id,
                    }
                    for history, asset in history_records
                ],
            }

            return result
    except Exception as e:
        logging.error(
            f"Failed to get position history: {str(e)}\n{traceback.format_exc()}"
        )
        return {"error": f"Failed to get position history: {str(e)}"}


@tool
def get_user_portfolio_summary(user_id: str) -> Dict:
    """Get a summary of user's portfolio.

    Args:
        user_id (str): The user ID

    Returns:
        Dict: Returns a summary of user's portfolio
    """
    try:
        with get_db() as db:
            # Get all user's asset sources
            sources = (
                db.query(AssetSourceModel, AssetSourceTypeModel)
                .join(
                    AssetSourceTypeModel,
                    AssetSourceModel.source_type_id
                    == AssetSourceTypeModel.source_type_id,
                )
                .filter(AssetSourceModel.user_id == user_id)
                .all()
            )

            portfolio_summary = {
                "user_id": user_id,
                "total_sources": len(sources),
                "source_types": {},
                "assets": {},
                "last_updated": None,
            }

            # Count source types
            for source, source_type in sources:
                if source_type.type_name not in portfolio_summary["source_types"]:
                    portfolio_summary["source_types"][source_type.type_name] = 0
                portfolio_summary["source_types"][source_type.type_name] += 1

                # Get all positions for this source
                positions = (
                    db.query(AssetPositionModel, CryptoAssetModel)
                    .join(
                        CryptoAssetModel,
                        AssetPositionModel.asset_id == CryptoAssetModel.asset_id,
                    )
                    .filter(AssetPositionModel.source_id == source.source_id)
                    .all()
                )

                # Aggregate assets
                for position, asset in positions:
                    asset_key = f"{asset.asset_symbol}_{asset.chain_type}"
                    if asset_key not in portfolio_summary["assets"]:
                        portfolio_summary["assets"][asset_key] = {
                            "asset_symbol": asset.asset_symbol,
                            "asset_name": asset.asset_name,
                            "chain_type": asset.chain_type,
                            "total_quantity": 0,
                            "sources": [],
                        }

                    portfolio_summary["assets"][asset_key]["total_quantity"] += float(
                        position.quantity
                    )
                    portfolio_summary["assets"][asset_key]["sources"].append(
                        {
                            "source_id": source.source_id,
                            "source_name": source.source_name,
                            "source_type": source_type.type_name,
                            "quantity": float(position.quantity),
                            "last_updated_at": (
                                position.last_updated_at.isoformat()
                                if position.last_updated_at
                                else None
                            ),
                        }
                    )

                    # Update last updated time
                    if position.last_updated_at:
                        if not portfolio_summary[
                            "last_updated"
                        ] or position.last_updated_at > datetime.fromisoformat(
                            portfolio_summary["last_updated"]
                        ):
                            portfolio_summary["last_updated"] = (
                                position.last_updated_at.isoformat()
                            )

            return portfolio_summary
    except Exception as e:
        logging.error(
            f"Failed to get user portfolio summary: {str(e)}\n{traceback.format_exc()}"
        )
        return {"error": f"Failed to get user portfolio summary: {str(e)}"}


# Export tools list
tools = [
    get_user_asset_sources,
    add_wallet_source,
    add_exchange_source,
    add_defi_source,
    get_source_positions,
    update_position,
    get_position_history,
    get_user_portfolio_summary,
]
