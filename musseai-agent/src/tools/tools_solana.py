import base64
import logging
import os
from typing import List, Dict, Union
from langchain.agents import tool
from solders.pubkey import Pubkey  # 使用 solders 替代 solana.publickey
import httpx
from loggers import logger

# Solana network configurations with endpoints and clusters
SOLANA_NETWORK_CONFIG = {
    "mainnet-beta": {
        "endpoint": "https://api.mainnet-beta.solana.com",
        "name": "Solana Mainnet Beta",
        "symbol": "SOL",
        "explorer": "https://explorer.solana.com",
    },
    "testnet": {
        "endpoint": "https://api.testnet.solana.com",
        "name": "Solana Testnet",
        "symbol": "SOL",
        "explorer": "https://explorer.solana.com/?cluster=testnet",
    },
    "devnet": {
        "endpoint": "https://api.devnet.solana.com",
        "name": "Solana Devnet",
        "symbol": "SOL",
        "explorer": "https://explorer.solana.com/?cluster=devnet",
    },
}

# Get Solana RPC API key from environment variable
SOLANA_RPC_API_KEY = os.environ.get("SOLANA_RPC_API_KEY", "")


def get_solana_rpc_url(cluster: str = "mainnet-beta") -> str:
    """Get RPC URL for specified Solana cluster"""
    if cluster.lower() not in SOLANA_NETWORK_CONFIG:
        raise ValueError(f"Unsupported Solana cluster: {cluster}")

    # If API key is provided, use custom RPC provider
    if SOLANA_RPC_API_KEY:
        if cluster.lower() == "mainnet-beta":
            return f"https://solana-mainnet.g.alchemy.com/v2/{SOLANA_RPC_API_KEY}"
        elif cluster.lower() == "devnet":
            return f"https://solana-devnet.g.alchemy.com/v2/{SOLANA_RPC_API_KEY}"

    # Otherwise use public endpoints
    return SOLANA_NETWORK_CONFIG[cluster.lower()]["endpoint"]


class SolanaRpcClient:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.session = httpx.Client(timeout=30.0)

    def _send_request(self, method: str, params: list = None) -> Dict:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        response = self.session.post(self.endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    def get_balance(self, pubkey: Pubkey) -> Dict:
        params = [str(pubkey), {"commitment": "confirmed"}]
        return self._send_request("getBalance", params)

    def get_token_accounts_by_owner(self, owner: Pubkey, mint: Pubkey) -> Dict:
        params = [str(owner), {"mint": str(mint)}, {"encoding": "base64"}]
        return self._send_request("getTokenAccountsByOwner", params)


def _make_solana_request(
    method: str,
    params: List = None,
    cluster: str = "mainnet-beta",
) -> Dict:
    """Send JSON-RPC request to Solana node"""
    try:
        solana_url = get_solana_rpc_url(cluster)
        client = SolanaRpcClient(solana_url)
        result = client._send_request(method, params)

        if "error" in result:
            return {"error": result["error"]["message"]}

        return {
            "result": result["result"],
            "method": method,
            "cluster": cluster,
        }
    except Exception as e:
        logger.error(e)
        return {"error": f"RPC request failed: {str(e)}"}


@tool
def get_supported_solana_clusters() -> List[Dict]:
    """
    Get all supported Solana clusters.

    Returns:
        List[Dict]: Returns a list of supported clusters, each containing:
            - cluster: Cluster name
            - name: Full cluster name
            - symbol: Native token symbol
            - explorer: Block explorer URL
    """
    clusters = []
    for cluster, config in SOLANA_NETWORK_CONFIG.items():
        clusters.append(
            {
                "cluster": cluster,
                "name": config["name"],
                "symbol": config["symbol"],
                "explorer": config["explorer"],
            }
        )
    return clusters


@tool
def get_sol_balance(address: str, cluster: str = "mainnet-beta") -> Dict:
    """
    Get SOL balance for specified address on specified cluster.

    Args:
        address (str): Solana address to query balance for
        cluster (str, optional): Solana cluster (mainnet-beta, testnet, devnet). Defaults to "mainnet-beta".

    Returns:
        Dict: Returns a dictionary containing:
            - address: Queried address
            - balance_lamports: Balance in lamports
            - balance: Balance in SOL
            - cluster: Requested cluster
    """
    try:
        client = SolanaRpcClient(get_solana_rpc_url(cluster))

        # Validate address format
        try:
            pubkey = Pubkey.from_string(address)
        except ValueError:
            return f"Invalid Solana address: {address}"

        # Get balance in lamports
        response = client.get_balance(pubkey)
        if "error" in response:
            return f"Error getting balance: {response['error']}"

        balance_lamports = response["result"]["value"]
        balance_sol = balance_lamports / 1_000_000_000  # Convert lamports to SOL

        return {
            "address": address,
            "balance_lamports": balance_lamports,
            "balance": balance_sol,
            "cluster": cluster,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting balance: {str(e)}"


@tool
def get_solana_block(slot: Union[int, str], cluster: str = "mainnet-beta") -> Dict:
    """
    Get information about a specific block.

    Args:
        slot (Union[int, str]): Block slot number or commitment level ('finalized', 'confirmed')
        cluster (str, optional): Solana cluster. Defaults to "mainnet-beta".

    Returns:
        Dict: Returns a dictionary containing block information
    """
    try:
        # If slot is a string like 'finalized', get the slot number first
        if isinstance(slot, str) and slot in ["finalized", "confirmed"]:
            slot_info = _make_solana_request("getSlot", [{"commitment": slot}], cluster)
            if "error" in slot_info:
                return f"Error getting slot: {slot_info['error']}"
            slot = slot_info["result"]

        # Get block details
        params = [
            slot,
            {
                "encoding": "json",
                "transactionDetails": "full",
                "rewards": True,
                "commitment": "confirmed",
            },
        ]

        block_info = _make_solana_request("getBlock", params, cluster)
        if "error" in block_info:
            return f"Error getting block: {block_info['error']}"

        # Add explorer link
        explorer_base = SOLANA_NETWORK_CONFIG[cluster.lower()]["explorer"]
        explorer_url = f"{explorer_base}/block/{slot}"

        # Add the explorer URL to the result
        if isinstance(block_info["result"], dict):
            block_info["result"]["explorer_url"] = explorer_url
            block_info["result"]["cluster"] = cluster

        return block_info
    except Exception as e:
        logger.error(e)
        return f"Error getting block: {str(e)}"


@tool
def get_solana_transaction(signature: str, cluster: str = "mainnet-beta") -> Dict:
    """
    Get transaction details for specified transaction signature on specified cluster.

    Args:
        signature (str): Transaction signature
        cluster (str, optional): Solana cluster. Defaults to "mainnet-beta".

    Returns:
        Dict: Returns a dictionary containing transaction information
    """
    try:
        params = [
            signature,
            {
                "encoding": "json",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            },
        ]

        tx_info = _make_solana_request("getTransaction", params, cluster)
        if "error" in tx_info:
            return f"Error getting transaction: {tx_info['error']}"

        # Add explorer link
        explorer_base = SOLANA_NETWORK_CONFIG[cluster.lower()]["explorer"]
        explorer_url = f"{explorer_base}/tx/{signature}"

        # Add the explorer URL to the result
        if isinstance(tx_info["result"], dict):
            tx_info["result"]["explorer_url"] = explorer_url
            tx_info["result"]["cluster"] = cluster

        return tx_info
    except Exception as e:
        logger.error(e)
        return f"Error getting transaction: {str(e)}"


@tool
def get_solana_block_time(slot: int, cluster: str = "mainnet-beta") -> Dict:
    """
    Get the estimated production time of a block.

    Args:
        slot (int): Block slot number
        cluster (str, optional): Solana cluster. Defaults to "mainnet-beta".

    Returns:
        Dict: Returns a dictionary containing:
            - unix_timestamp: Unix timestamp (seconds since epoch)
            - human_readable: Human-readable date and time
            - slot: Requested slot
            - cluster: Requested cluster
    """
    try:
        params = [slot]

        result = _make_solana_request("getBlockTime", params, cluster)
        if "error" in result:
            return f"Error getting block time: {result['error']}"

        unix_timestamp = result["result"]

        # Convert to human-readable format
        from datetime import datetime

        human_readable = datetime.utcfromtimestamp(unix_timestamp).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        return {
            "unix_timestamp": unix_timestamp,
            "human_readable": human_readable,
            "slot": slot,
            "cluster": cluster,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting block time: {str(e)}"


@tool
def get_solana_block_height(cluster: str = "mainnet-beta") -> Dict:
    """
    Get the current block height.

    Args:
        cluster (str, optional): Solana cluster. Defaults to "mainnet-beta".

    Returns:
        Dict: Returns a dictionary containing:
            - block_height: Current block height
            - cluster: Requested cluster
    """
    try:
        params = [{"commitment": "finalized"}]

        result = _make_solana_request("getBlockHeight", params, cluster)
        if "error" in result:
            return f"Error getting block height: {result['error']}"

        return {
            "block_height": result["result"],
            "cluster": cluster,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting block height: {str(e)}"


@tool
def get_solana_slot(cluster: str = "mainnet-beta") -> Dict:
    """
    Get the current slot.

    Args:
        cluster (str, optional): Solana cluster. Defaults to "mainnet-beta".

    Returns:
        Dict: Returns a dictionary containing:
            - slot: Current slot
            - cluster: Requested cluster
    """
    try:
        params = [{"commitment": "finalized"}]

        result = _make_solana_request("getSlot", params, cluster)
        if "error" in result:
            return f"Error getting slot: {result['error']}"

        return {
            "slot": result["result"],
            "cluster": cluster,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting slot: {str(e)}"


@tool
def get_spl_token_balance(
    token_address: str, wallet_address: str, cluster: str = "mainnet-beta"
) -> Dict:
    """
    Get SPL token balance for specified address.

    Args:
        token_address (str): SPL token mint address
        wallet_address (str): Wallet address to query balance for
        cluster (str, optional): Solana cluster. Defaults to "mainnet-beta".

    Returns:
        Dict: Returns a dictionary containing:
            - token_address: Token mint address
            - wallet_address: Wallet address
            - balance: Token balance
            - decimals: Token decimals
            - cluster: Requested cluster
    """
    try:
        client = SolanaRpcClient(get_solana_rpc_url(cluster))

        # Validate addresses
        try:
            token_pubkey = Pubkey.from_string(token_address)
            wallet_pubkey = Pubkey.from_string(wallet_address)
        except ValueError as e:
            return f"Invalid address: {str(e)}"

        # Get token account
        response = client.get_token_accounts_by_owner(wallet_pubkey, token_pubkey)

        if "error" in response:
            return f"Error getting token accounts: {response['error']}"

        accounts = response["result"]["value"]

        if not accounts:
            return {
                "token_address": token_address,
                "wallet_address": wallet_address,
                "balance": 0,
                "decimals": None,
                "cluster": cluster,
            }

        # Get balance from the first token account
        account = accounts[0]
        account_data = base64.b64decode(account["account"]["data"][0])

        # Parse token account data
        decimals = account_data[44]
        raw_balance = int.from_bytes(account_data[64:72], byteorder="little")
        balance = raw_balance / (10**decimals)

        return {
            "token_address": token_address,
            "wallet_address": wallet_address,
            "balance": balance,
            "decimals": decimals,
            "cluster": cluster,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting token balance: {str(e)}"


tools = [
    get_supported_solana_clusters,
    get_sol_balance,
    get_solana_block,
    get_solana_transaction,
    get_solana_block_time,
    get_solana_block_height,
    get_solana_slot,
    get_spl_token_balance,
]
