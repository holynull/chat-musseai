import logging
import traceback
from types import TracebackType
import requests
import json
from typing import List, Dict, Optional, Any, Union
from langchain.agents import tool
from web3 import Web3
import os
from loggers import logger

# Network configurations with Infura endpoints and chain IDs
NETWORK_CONFIG = {
    "ethereum": {
        "mainnet": {
            "chain_id": 1,
            "name": "Ethereum Mainnet",
            "symbol": "ETH",
            "explorer": "https://etherscan.io",
        },
        "goerli": {
            "chain_id": 5,
            "name": "Goerli Testnet",
            "symbol": "ETH",
            "explorer": "https://goerli.etherscan.io",
        },
        "sepolia": {
            "chain_id": 11155111,
            "name": "Sepolia Testnet",
            "symbol": "ETH",
            "explorer": "https://sepolia.etherscan.io",
        },
    },
    "polygon": {
        "mainnet": {
            "chain_id": 137,
            "name": "Polygon Mainnet",
            "symbol": "MATIC",
            "explorer": "https://polygonscan.com",
        },
        "mumbai": {
            "chain_id": 80001,
            "name": "Mumbai Testnet",
            "symbol": "MATIC",
            "explorer": "https://mumbai.polygonscan.com",
        },
    },
    "optimism": {
        "mainnet": {
            "chain_id": 10,
            "name": "Optimism Mainnet",
            "symbol": "ETH",
            "explorer": "https://optimistic.etherscan.io",
        },
        "goerli": {
            "chain_id": 420,
            "name": "Optimism Goerli",
            "symbol": "ETH",
            "explorer": "https://goerli-optimism.etherscan.io",
        },
    },
    "arbitrum": {
        "mainnet": {
            "chain_id": 42161,
            "name": "Arbitrum One",
            "symbol": "ETH",
            "explorer": "https://arbiscan.io",
        },
        "goerli": {
            "chain_id": 421613,
            "name": "Arbitrum Goerli",
            "symbol": "ETH",
            "explorer": "https://goerli.arbiscan.io",
        },
    },
    # 新增网络
    "avalanche": {
        "mainnet": {
            "chain_id": 43114,
            "name": "Avalanche C-Chain",
            "symbol": "AVAX",
            "explorer": "https://snowtrace.io",
        },
        "testnet": {
            "chain_id": 43113,
            "name": "Avalanche Fuji Testnet",
            "symbol": "AVAX",
            "explorer": "https://testnet.snowtrace.io",
        },
    },
    "base": {
        "mainnet": {
            "chain_id": 8453,
            "name": "Base Mainnet",
            "symbol": "ETH",
            "explorer": "https://basescan.org",
        },
        "sepolia": {
            "chain_id": 84532,
            "name": "Base Sepolia Testnet",
            "symbol": "ETH",
            "explorer": "https://sepolia.basescan.org",
        },
    },
    "blast": {
        "mainnet": {
            "chain_id": 81457,  # 请根据实际情况调整
            "name": "Blast Mainnet",
            "symbol": "ETH",
            "explorer": "https://blastscan.io",  # 请根据实际情况调整
        },
    },
    "bsc": {
        "mainnet": {
            "chain_id": 56,
            "name": "Binance Smart Chain",
            "symbol": "BNB",
            "explorer": "https://bscscan.com",
        },
        "testnet": {
            "chain_id": 97,
            "name": "BSC Testnet",
            "symbol": "BNB",
            "explorer": "https://testnet.bscscan.com",
        },
    },
    "celo": {
        "mainnet": {
            "chain_id": 42220,
            "name": "Celo Mainnet",
            "symbol": "CELO",
            "explorer": "https://explorer.celo.org",
        },
        "alfajores": {
            "chain_id": 44787,
            "name": "Celo Alfajores Testnet",
            "symbol": "CELO",
            "explorer": "https://alfajores-blockscout.celo-testnet.org",
        },
    },
    "linea": {
        "mainnet": {
            "chain_id": 59144,
            "name": "Linea Mainnet",
            "symbol": "ETH",
            "explorer": "https://lineascan.build",
        },
        "testnet": {
            "chain_id": 59140,
            "name": "Linea Goerli Testnet",
            "symbol": "ETH",
            "explorer": "https://goerli.lineascan.build",
        },
    },
    "mantle": {
        "mainnet": {
            "chain_id": 5000,
            "name": "Mantle Mainnet",
            "symbol": "MNT",
            "explorer": "https://explorer.mantle.xyz",
        },
        "testnet": {
            "chain_id": 5001,
            "name": "Mantle Testnet",
            "symbol": "MNT",
            "explorer": "https://explorer.testnet.mantle.xyz",
        },
    },
    "opbnb": {
        "mainnet": {
            "chain_id": 204,  # 请根据实际情况调整
            "name": "opBNB Mainnet",
            "symbol": "BNB",
            "explorer": "https://opbnbscan.com",  # 请根据实际情况调整
        },
    },
    "palm": {
        "mainnet": {
            "chain_id": 11297108109,
            "name": "Palm Mainnet",
            "symbol": "PALM",
            "explorer": "https://explorer.palm.io",
        },
        "testnet": {
            "chain_id": 11297108099,
            "name": "Palm Testnet",
            "symbol": "PALM",
            "explorer": "https://testnet.explorer.palm.io",
        },
    },
    "polygon_pos": {
        "mainnet": {
            "chain_id": 137,
            "name": "Polygon POS Mainnet",
            "symbol": "MATIC",
            "explorer": "https://polygonscan.com",
        },
        "testnet": {
            "chain_id": 80001,
            "name": "Mumbai Testnet",
            "symbol": "MATIC",
            "explorer": "https://mumbai.polygonscan.com",
        },
    },
    "scroll": {
        "mainnet": {
            "chain_id": 534352,
            "name": "Scroll Mainnet",
            "symbol": "ETH",
            "explorer": "https://scrollscan.com",
        },
        "testnet": {
            "chain_id": 534351,
            "name": "Scroll Sepolia Testnet",
            "symbol": "ETH",
            "explorer": "https://sepolia.scrollscan.com",
        },
    },
    "starknet": {
        "mainnet": {
            "chain_id": 9,  # StarkNet 使用不同的链ID机制，这是参考值
            "name": "StarkNet Mainnet",
            "symbol": "ETH",
            "explorer": "https://voyager.online",
        },
        "testnet": {
            "chain_id": 1,  # StarkNet 测试网ID，参考值
            "name": "StarkNet Goerli Testnet",
            "symbol": "ETH",
            "explorer": "https://goerli.voyager.online",
        },
    },
    "swellchain": {
        "mainnet": {
            "chain_id": 30000,  # 参考值，根据实际情况调整
            "name": "Swell Chain Mainnet",
            "symbol": "SWELL",
            "explorer": "https://explorer.swellchain.io",  # 参考值，根据实际情况调整
        },
        "testnet": {
            "chain_id": 30001,  # 参考值，根据实际情况调整
            "name": "Swell Chain Testnet",
            "symbol": "SWELL",
            "explorer": "https://testnet.explorer.swellchain.io",  # 参考值，根据实际情况调整
        },
    },
    "unichain": {
        "mainnet": {
            "chain_id": 29,  # 参考值，根据实际情况调整
            "name": "UniChain Mainnet",
            "symbol": "UNI",
            "explorer": "https://explorer.unichain.network",  # 参考值，根据实际情况调整
        },
        "testnet": {
            "chain_id": 30,  # 参考值，根据实际情况调整
            "name": "UniChain Testnet",
            "symbol": "UNI",
            "explorer": "https://testnet.explorer.unichain.network",  # 参考值，根据实际情况调整
        },
    },
    "zksync": {
        "mainnet": {
            "chain_id": 324,
            "name": "ZKsync Era Mainnet",
            "symbol": "ETH",
            "explorer": "https://explorer.zksync.io",
        },
        "testnet": {
            "chain_id": 280,
            "name": "ZKsync Era Testnet",
            "symbol": "ETH",
            "explorer": "https://goerli.explorer.zksync.io",
        },
    },
}

# Get Infura API key from environment variable
INFURA_API_KEY = os.environ.get("INFURA_API_KEY", "")


def get_rpc_url(network: str, network_type: str = "mainnet") -> str:
    """Get RPC URL for specified network"""
    if not INFURA_API_KEY:
        raise ValueError("INFURA_API_KEY environment variable is not set")

    if network.lower() not in NETWORK_CONFIG:
        raise ValueError(f"Unsupported network: {network}")

    if network_type.lower() not in NETWORK_CONFIG[network.lower()]:
        raise ValueError(f"Unsupported network type: {network_type} for {network}")

    # 针对不同网络使用适当的RPC提供商
    network = network.lower()
    network_type = network_type.lower()
    # Infura支持的网络
    infura_supported = [
        "arbitrum",
        "avalanche",
        "base",
        "blast",
        "bsc",
        "celo",
        "ethereum",
        "linea",
        "mantle",
        "opbnb",
        "optimism",
        "palm",
        "polygon",
        "scroll",
        "starknet",
        "swellchain",
        "unichain",
        "zksync",
    ]

    if network in infura_supported:
        # 特殊处理某些网络的URL格式
        if network == "ethereum":
            return f"https://mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "arbitrum":
            return f"https://arbitrum-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "avalanche":
            return f"https://avalanche-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "base" and network_type == "sepolia":
            return f"https://base-sepolia.infura.io/v3/{INFURA_API_KEY}"
        elif network == "blast":
            return f"https://blast-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "bsc":
            return f"https://bsc-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "celo":
            return f"https://celo-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "linea":
            return f"https://linea-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "mantle":
            return f"https://mantle-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "opbnb":
            return f"https://opbnb-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "optimism":
            return f"https://optimism-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "palm":
            return f"https://palm-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "polygon":
            return f"https://polygon-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "scroll":
            return f"https://scroll-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "starknet":
            return f"https://starknet-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "swellchain":
            return f"https://swellchain-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "unichain":
            return f"https://unichain-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "zksync":
            return f"https://zksync-mainnet.infura.io/v3/{INFURA_API_KEY}"
        else:
            # 通用格式，适用于其他网络
            return f"https://{network}-{network_type}.infura.io/v3/{INFURA_API_KEY}"
    # 如果没有找到适当的RPC端点，返回错误
    raise ValueError(f"No RPC endpoint configured for {network} {network_type}")


@tool
def get_supported_networks() -> List[Dict]:
    """
    Get all supported blockchain networks and network types.

    Returns:
        List[Dict]: Returns a list of supported networks, each containing:
            - network: Network name
            - network_type: Network type (e.g., mainnet, testnet)
            - chain_id: Chain ID
            - name: Full network name
            - symbol: Native token symbol
            - explorer: Block explorer URL
    """
    networks = []
    for network, network_types in NETWORK_CONFIG.items():
        for network_type, config in network_types.items():
            networks.append(
                {
                    "network": network,
                    "network_type": network_type,
                    "chain_id": config["chain_id"],
                    "name": config["name"],
                    "symbol": config["symbol"],
                    "explorer": config["explorer"],
                }
            )
    return networks


@tool
def get_eth_block_number(network: str, network_type: str = "mainnet") -> Dict:
    """
    Get the latest block number for the specified network.

    Args:
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".

    Returns:
        Dict: Returns a dictionary containing:
            - block_number: Latest block number
            - network: Requested network
            - network_type: Requested network type
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        # Get latest block number
        block_number = w3.eth.block_number

        return {
            "block_number": block_number,
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting block number: {str(e)}"


@tool
def get_eth_balance(address: str, network: str, network_type: str = "mainnet") -> Dict:
    """
    Get native token balance for specified address on specified network.

    Args:
        address (str): Ethereum address to query balance for
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".

    Returns:
        Dict: Returns a dictionary containing:
            - address: Queried address
            - balance_wei: Balance in Wei
            - balance: Balance in native token units
            - symbol: Native token symbol
            - network: Requested network
            - network_type: Requested network type
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        # Check address format
        if not w3.is_address(address):
            return f"Invalid Ethereum address: {address}"

        # Get balance
        balance_wei = w3.eth.get_balance(address)
        balance = w3.from_wei(balance_wei, "ether")

        # Get native token symbol
        symbol = NETWORK_CONFIG[network.lower()][network_type.lower()]["symbol"]

        return {
            "address": address,
            "balance_wei": balance_wei,
            "balance": float(balance),
            "symbol": symbol,
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting balance: {str(e)}"


@tool
def get_eth_transaction(
    tx_hash: str, network: str, network_type: str = "mainnet"
) -> Dict:
    """
    Get transaction details for specified transaction hash on specified network.

    Args:
        tx_hash (str): Transaction hash
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".

    Returns:
        Dict: Returns a dictionary containing:
            - hash: Transaction hash
            - blockNumber: Block number
            - from: Sender address
            - to: Receiver address
            - value: Transaction amount (Wei)
            - gas: Gas limit
            - gasPrice: Gas price (Wei)
            - nonce: Sender's nonce
            - transactionIndex: Transaction index in block
            - network: Requested network
            - network_type: Requested network type
            - explorer_url: Transaction URL in block explorer
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        # Get transaction
        tx = w3.eth.get_transaction(tx_hash)
        if tx is None:
            return f"Transaction not found: {tx_hash}"

        # Build explorer URL
        explorer_base = NETWORK_CONFIG[network.lower()][network_type.lower()][
            "explorer"
        ]
        explorer_url = f"{explorer_base}/tx/{tx_hash}"

        # Convert to serializable dictionary
        tx_dict = {
            "hash": tx_hash,
            "blockNumber": tx.blockNumber,
            "from": tx["from"],
            "to": tx["to"],
            "value": tx.value,
            "gas": tx.gas,
            "gasPrice": tx.gasPrice,
            "nonce": tx.nonce,
            "transactionIndex": tx.transactionIndex,
            "network": network,
            "network_type": network_type,
            "explorer_url": explorer_url,
        }

        return tx_dict
    except Exception as e:
        logger.error(e)
        return f"Error getting transaction: {str(e)}"


@tool
def get_eth_block(
    block_identifier: Union[str, int],
    network: str,
    network_type: str = "mainnet",
    tx_limit: int = 3,
) -> Dict:
    """
    Get basic block details for specified block on specified network.

    Args:
        block_identifier (Union[str, int]): Block number or block hash or special tag (e.g., "latest")
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".
        tx_limit (int, optional): Maximum number of transactions to return. Defaults to 3.

    Returns:
        Dict: Returns a dictionary containing block information
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        # 使用自定义的请求头，忽略 PoA 校验
        provider = Web3.HTTPProvider(
            infura_url,
            request_kwargs={
                "headers": {
                    "content-type": "application/json",
                    "user-agent": "Mozilla/5.0",
                }
            },
        )
        w3 = Web3(provider)

        # 为POA链添加中间件
        if network.lower() == "bsc" or network.lower() in [
            "avalanche",
            "polygon",
            "optimism",
            "arbitrum",
        ]:
            from web3.middleware import ExtraDataToPOAMiddleware

            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        try:
            # 获取区块信息，强制关闭 extraData 校验
            block = w3.eth.get_block(block_identifier, full_transactions=False)

            # 构建响应数据
            response = {
                "basic_info": {
                    "number": block.number,
                    "timestamp": block.timestamp,
                    "tx_count": (
                        len(block.transactions) if hasattr(block, "transactions") else 0
                    ),
                },
                "gas_info": {
                    "gas_used": block.gasUsed,
                    "gas_limit": block.gasLimit,
                    "used_percentage": (
                        round((block.gasUsed / block.gasLimit) * 100, 2)
                        if block.gasLimit > 0
                        else 0
                    ),
                    "base_fee_gwei": (
                        w3.from_wei(block.baseFeePerGas, "gwei")
                        if hasattr(block, "baseFeePerGas")
                        else None
                    ),
                },
                "miner": block.miner if hasattr(block, "miner") else None,
                "network_info": {
                    "network": network,
                    "network_type": network_type,
                    "explorer_url": f"{NETWORK_CONFIG[network.lower()][network_type.lower()]['explorer']}/block/{block.number}",
                },
                "transactions": {
                    "preview": (
                        [tx.hex() for tx in block.transactions[:tx_limit]]
                        if hasattr(block, "transactions")
                        else []
                    ),
                    "total": (
                        len(block.transactions) if hasattr(block, "transactions") else 0
                    ),
                },
            }

            # 在文件顶部导入：
            from decimal import Decimal

            # 添加编码器类：
            class DecimalEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, Decimal):
                        return float(obj)
                    return super(DecimalEncoder, self).default(obj)

            # 修改 get_eth_block 函数中的 return 语句（第621行）：
            return json.dumps(response, cls=DecimalEncoder)

        except ValueError as e:
            logger.warning(f"Error getting block with full data: {e}")
            return f"Error: Could not retrieve block data. The block might not exist or network issues occurred."

    except Exception as e:
        logger.error(f"Error in get_eth_block: {str(e)}")
        return f"Error getting block: {str(e)}"


@tool
def call_eth_method(
    method: str, params: List, network: str, network_type: str = "mainnet"
) -> Any:
    """
    Call any Ethereum JSON-RPC method.

    Args:
        method (str): JSON-RPC method name (e.g., "eth_gasPrice", "net_version")
        params (List): List of method parameters
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".

    Returns:
        Any: Returns the RPC call result
    """
    try:
        infura_url = get_rpc_url(network, network_type)

        # Build JSON-RPC request
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}

        # Send request
        response = requests.post(infura_url, json=payload)
        response.raise_for_status()

        # Parse response
        result = response.json()

        if "error" in result:
            return f"RPC error: {result['error']['message']}"

        return {
            "result": result["result"],
            "method": method,
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        logger.error(e)
        return f"Error calling RPC method: {str(e)}"


@tool
def get_token_balance(
    token_address: str, wallet_address: str, network: str, network_type: str = "mainnet"
) -> Dict:
    """
    Get ERC20 token balance for specified address.

    Args:
        token_address (str): ERC20 token contract address
        wallet_address (str): Wallet address to query balance for
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".

    Returns:
        Dict: Returns a dictionary containing:
            - token_address: Token contract address
            - wallet_address: Wallet address
            - balance_wei: Balance in smallest unit
            - balance: Balance in token units
            - decimals: Token decimals
            - symbol: Token symbol
            - name: Token name
            - network: Requested network
            - network_type: Requested network type
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        # ERC20 token ABI
        ERC20_ABI = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function",
            },
        ]

        # Create contract instance
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
        )

        # Get token information
        decimals = token_contract.functions.decimals().call()
        symbol = token_contract.functions.symbol().call()
        name = token_contract.functions.name().call()

        # Get balance
        balance_wei = token_contract.functions.balanceOf(
            Web3.to_checksum_address(wallet_address)
        ).call()

        # Convert to token units
        balance = balance_wei / (10**decimals)

        return {
            "token_address": token_address,
            "wallet_address": wallet_address,
            "balance_wei": balance_wei,
            "balance": balance,
            "decimals": decimals,
            "symbol": symbol,
            "name": name,
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        logger.error(
            f"Failed to get token balance of an address: {str(e)}\n{traceback.format_exc()}"
        )
        return f"Error getting token balance: {str(e)}"


@tool
def estimate_gas(
    from_address: str,
    to_address: str,
    value: int,
    data: str = "",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """
    Estimate gas cost for a transaction.

    Args:
        from_address (str): Sender address
        to_address (str): Recipient address
        value (int): Transaction value in Wei
        data (str, optional): Transaction data hexstring. Defaults to empty string.
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type. Defaults to "mainnet".

    Returns:
        Dict: Returns a dictionary containing:
            - estimated_gas: Estimated gas amount
            - gas_price: Current gas price in Wei
            - total_cost_wei: Total estimated cost in Wei
            - total_cost_eth: Total estimated cost in network's native token
            - network: Requested network
            - network_type: Requested network type
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        # Create transaction dictionary
        transaction = {
            "from": Web3.to_checksum_address(from_address),
            "to": Web3.to_checksum_address(to_address),
            "value": value,
            "data": data,
        }

        # Estimate gas
        estimated_gas = w3.eth.estimate_gas(transaction)

        # Get current gas price
        gas_price = w3.eth.gas_price

        # Calculate total cost
        total_cost_wei = estimated_gas * gas_price
        total_cost_eth = w3.from_wei(total_cost_wei, "ether")

        return {
            "estimated_gas": estimated_gas,
            "gas_price": gas_price,
            "total_cost_wei": total_cost_wei,
            "total_cost_eth": float(total_cost_eth),
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        logger.error(e)
        return f"Error estimating gas: {str(e)}"


@tool
def get_contract_events(
    contract_address: str,
    event_name: str,
    from_block: Union[int, str],
    to_block: Union[int, str] = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """
    Get events emitted by a smart contract.

    Args:
        contract_address (str): Smart contract address
        event_name (str): Name of the event to fetch
        from_block (Union[int, str]): Starting block number or "earliest"
        to_block (Union[int, str], optional): Ending block number or "latest". Defaults to "latest".
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type. Defaults to "mainnet".

    Returns:
        Dict: Returns a dictionary containing:
            - events: List of events
            - contract_address: Contract address
            - event_name: Event name
            - from_block: Starting block
            - to_block: Ending block
            - network: Requested network
            - network_type: Requested network type
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        # Call eth_getLogs RPC method
        filter_params = {
            "address": Web3.to_checksum_address(contract_address),
            "fromBlock": from_block,
            "toBlock": to_block,
            "topics": [w3.keccak(text=f"{event_name}()")],
        }

        logs = w3.eth.get_logs(filter_params)

        # Convert logs to serializable format
        events = []
        for log in logs:
            event = {
                "blockNumber": log.blockNumber,
                "transactionHash": log.transactionHash.hex(),
                "logIndex": log.logIndex,
                "address": log.address,
                "topics": [topic.hex() for topic in log.topics],
                "data": log.data,
            }
            events.append(event)

        return {
            "events": events,
            "contract_address": contract_address,
            "event_name": event_name,
            "from_block": from_block,
            "to_block": to_block,
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting contract events: {str(e)}"


@tool
def get_network_info(network: str, network_type: str = "mainnet") -> Dict:
    """
    Get general information about the specified network.

    Args:
        network (str): Blockchain network name, in the `NETWORK_CONFIG`
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".

    Returns:
        Dict: Returns a dictionary containing:
            - chain_id: Network chain ID
            - name: Network name
            - native_currency: Native currency symbol
            - network_version: Network version
            - latest_block: Latest block number
            - gas_price: Current gas price
            - is_listening: Node connection status
            - peer_count: Number of connected peers
            - network: Requested network
            - network_type: Requested network type
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        return {
            "chain_id": NETWORK_CONFIG[network.lower()][network_type.lower()][
                "chain_id"
            ],
            "name": NETWORK_CONFIG[network.lower()][network_type.lower()]["name"],
            "native_currency": NETWORK_CONFIG[network.lower()][network_type.lower()][
                "symbol"
            ],
            "network_version": w3.net.version,
            "latest_block": w3.eth.block_number,
            "gas_price": w3.eth.gas_price,
            "is_listening": w3.net.listening,
            "peer_count": w3.net.peer_count,
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        logger.error(e)
        return f"Error getting network info: {str(e)}"


def _make_request(
    method: str,
    params: List = None,
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """
    发送 JSON-RPC 请求

    Args:
        method: RPC 方法名
        params: 方法参数列表
        network: 网络名称
        network_type: 网络类型

    Returns:
        JSON-RPC 响应
    """
    try:
        infura_url = get_rpc_url(network, network_type)

        # Build JSON-RPC request
        payload = {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}

        # Send request
        headers = {"Content-Type": "application/json"}
        response = requests.post(infura_url, headers=headers, json=payload)
        response.raise_for_status()

        # Parse response
        result = response.json()

        if "error" in result:
            return {"error": result["error"]["message"]}

        return {
            "result": result["result"],
            "method": method,
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        logger.error(e)
        return {"error": f"RPC request failed: {str(e)}"}


# @tool
# def eth_accounts(network: str, network_type: str = "mainnet") -> Dict:
#     """Returns a list of addresses owned by client."""
#     return _make_request("eth_accounts", [], network, network_type)


@tool
def eth_blockNumber(network: str, network_type: str = "mainnet") -> Dict:
    """Returns the number of most recent block."""
    return _make_request("eth_blockNumber", [], network, network_type)


@tool
def eth_call(
    tx_object: Dict,
    block_parameter: str = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Executes a new message call immediately without creating a transaction."""
    return _make_request(
        "eth_call", [tx_object, block_parameter], network, network_type
    )


@tool
def eth_chainId(network: str, network_type: str = "mainnet") -> Dict:
    """Returns the chain ID of the current network."""
    return _make_request("eth_chainId", [], network, network_type)


@tool
def eth_coinbase(network: str, network_type: str = "mainnet") -> Dict:
    """Returns the client coinbase address."""
    return _make_request("eth_coinbase", [], network, network_type)


@tool
def eth_createAccessList(
    tx_object: Dict,
    block_parameter: str = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Creates an access list for a transaction."""
    return _make_request(
        "eth_createAccessList", [tx_object, block_parameter], network, network_type
    )


@tool
def eth_estimateGas(
    tx_object: Dict,
    block_parameter: str = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Generates and returns an estimate of how much gas is necessary to allow the transaction to complete."""
    return _make_request(
        "eth_estimateGas", [tx_object, block_parameter], network, network_type
    )


@tool
def eth_feeHistory(
    block_count: int,
    newest_block: str = "latest",
    reward_percentiles: List[float] = None,
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns a collection of historical gas information."""
    params = [hex(block_count), newest_block]
    if reward_percentiles:
        params.append(reward_percentiles)
    return _make_request("eth_feeHistory", params, network, network_type)


@tool
def eth_gasPrice(network: str, network_type: str = "mainnet") -> Dict:
    """Returns the current price per gas in wei."""
    return _make_request("eth_gasPrice", [], network, network_type)


@tool
def eth_getBalance(
    address: str,
    block_parameter: str = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns the balance of the account of given address."""
    return _make_request(
        "eth_getBalance",
        [Web3.to_checksum_address(address), block_parameter],
        network,
        network_type,
    )


@tool
def eth_getBlockByHash(
    block_hash: str,
    full_transactions: bool = True,
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns information about a block by hash."""
    return _make_request(
        "eth_getBlockByHash", [block_hash, full_transactions], network, network_type
    )


@tool
def eth_getBlockByNumber(
    block_parameter: Union[str, int],
    full_transactions: bool = True,
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns information about a block by block number."""
    if isinstance(block_parameter, int):
        block_parameter = hex(block_parameter)
    return _make_request(
        "eth_getBlockByNumber",
        [block_parameter, full_transactions],
        network,
        network_type,
    )


@tool
def eth_getBlockReceipts(
    block_parameter: Union[str, int],
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns all transaction receipts for a block."""
    if isinstance(block_parameter, int):
        block_parameter = hex(block_parameter)
    return _make_request(
        "eth_getBlockReceipts", [block_parameter], network, network_type
    )


@tool
def eth_getBlockTransactionCountByHash(
    block_hash: str, network: str = "ethereum", network_type: str = "mainnet"
) -> Dict:
    """Returns the number of transactions in a block from a block matching the given block hash."""
    return _make_request(
        "eth_getBlockTransactionCountByHash", [block_hash], network, network_type
    )


@tool
def eth_getBlockTransactionCountByNumber(
    block_parameter: Union[str, int],
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns the number of transactions in a block matching the given block number."""
    if isinstance(block_parameter, int):
        block_parameter = hex(block_parameter)
    return _make_request(
        "eth_getBlockTransactionCountByNumber", [block_parameter], network, network_type
    )


@tool
def eth_getCode(
    address: str,
    block_parameter: str = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns code at a given address."""
    return _make_request(
        "eth_getCode",
        [Web3.to_checksum_address(address), block_parameter],
        network,
        network_type,
    )


@tool
def eth_getLogs(
    filter_params: Dict, network: str = "ethereum", network_type: str = "mainnet"
) -> Dict:
    """Returns an array of all logs matching a given filter object."""
    return _make_request("eth_getLogs", [filter_params], network, network_type)


@tool
def eth_getProof(
    address: str,
    storage_keys: List[str],
    block_parameter: str = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns the account and storage values of the specified account including the Merkle-proof."""
    return _make_request(
        "eth_getProof",
        [Web3.to_checksum_address(address), storage_keys, block_parameter],
        network,
        network_type,
    )


@tool
def eth_getStorageAt(
    address: str,
    position: str,
    block_parameter: str = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns the value from a storage position at a given address."""
    return _make_request(
        "eth_getStorageAt",
        [Web3.to_checksum_address(address), position, block_parameter],
        network,
        network_type,
    )


@tool
def eth_getTransactionByBlockHashAndIndex(
    block_hash: str,
    index: int,
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns information about a transaction by block hash and transaction index position."""
    return _make_request(
        "eth_getTransactionByBlockHashAndIndex",
        [block_hash, hex(index)],
        network,
        network_type,
    )


@tool
def eth_getTransactionByBlockNumberAndIndex(
    block_parameter: Union[str, int],
    index: int,
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns information about a transaction by block number and transaction index position."""
    if isinstance(block_parameter, int):
        block_parameter = hex(block_parameter)
    return _make_request(
        "eth_getTransactionByBlockNumberAndIndex",
        [block_parameter, hex(index)],
        network,
        network_type,
    )


@tool
def eth_getTransactionByHash(
    tx_hash: str, network: str = "ethereum", network_type: str = "mainnet"
) -> Dict:
    """Returns the information about a transaction requested by transaction hash."""
    return _make_request("eth_getTransactionByHash", [tx_hash], network, network_type)


@tool
def eth_getTransactionCount(
    address: str,
    block_parameter: str = "latest",
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns the number of transactions sent from an address."""
    return _make_request(
        "eth_getTransactionCount",
        [Web3.to_checksum_address(address), block_parameter],
        network,
        network_type,
    )


@tool
def eth_getTransactionReceipt(
    tx_hash: str, network: str = "ethereum", network_type: str = "mainnet"
) -> Dict:
    """Returns the receipt of a transaction by transaction hash."""
    return _make_request("eth_getTransactionReceipt", [tx_hash], network, network_type)


@tool
def eth_getUncleByBlockHashAndIndex(
    block_hash: str,
    index: int,
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns information about an uncle of a block by hash and uncle index position."""
    return _make_request(
        "eth_getUncleByBlockHashAndIndex",
        [block_hash, hex(index)],
        network,
        network_type,
    )


@tool
def eth_getUncleByBlockNumberAndIndex(
    block_parameter: Union[str, int],
    index: int,
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns information about an uncle of a block by number and uncle index position."""
    if isinstance(block_parameter, int):
        block_parameter = hex(block_parameter)
    return _make_request(
        "eth_getUncleByBlockNumberAndIndex",
        [block_parameter, hex(index)],
        network,
        network_type,
    )


@tool
def eth_getUncleCountByBlockHash(
    block_hash: str, network: str = "ethereum", network_type: str = "mainnet"
) -> Dict:
    """Returns the number of uncles in a block from a block matching the given block hash."""
    return _make_request(
        "eth_getUncleCountByBlockHash", [block_hash], network, network_type
    )


@tool
def eth_getUncleCountByBlockNumber(
    block_parameter: Union[str, int],
    network: str = "ethereum",
    network_type: str = "mainnet",
) -> Dict:
    """Returns the number of uncles in a block from a block matching the given block number."""
    if isinstance(block_parameter, int):
        block_parameter = hex(block_parameter)
    return _make_request(
        "eth_getUncleCountByBlockNumber", [block_parameter], network, network_type
    )


@tool
def eth_maxPriorityFeePerGas(network: str, network_type: str = "mainnet") -> Dict:
    """Returns the current maxPriorityFeePerGas in wei."""
    return _make_request("eth_maxPriorityFeePerGas", [], network, network_type)


# @tool
# def eth_sendRawTransaction(
#     signed_tx_data: str, network: str = "ethereum", network_type: str = "mainnet"
# ) -> Dict:
#     """Creates new message call transaction or a contract creation for signed transactions."""
#     return _make_request(
#         "eth_sendRawTransaction", [signed_tx_data], network, network_type
#     )


@tool
def eth_syncing(network: str, network_type: str = "mainnet") -> Dict:
    """Returns an object with data about the sync status or false."""
    return _make_request("eth_syncing", [], network, network_type)


@tool
def net_peerCount(network: str, network_type: str = "mainnet") -> Dict:
    """Returns number of peers currently connected to the client."""
    return _make_request("net_peerCount", [], network, network_type)


@tool
def net_version(network: str, network_type: str = "mainnet") -> Dict:
    """Returns the current network id."""
    return _make_request("net_version", [], network, network_type)


def generate_erc20_approve_data(spender_address: str, amount: str) -> str:
    """Generate unsigned transaction data for ERC20 token approve."""
    approve_function_signature = "approve(address,uint256)"
    w3 = Web3()
    fn_selector = w3.keccak(text=approve_function_signature)[:4].hex()
    padded_address = Web3.to_bytes(hexstr=spender_address).rjust(32, b"\0")
    amount_int = int(amount)
    padded_amount = amount_int.to_bytes(32, "big")
    data = fn_selector + padded_address.hex() + padded_amount.hex()
    return data


@tool
def generate_approve_erc20(
    token_address: str,
    spender_address: str,
    amount: str,
    chain_id: int,
    symbol: str,
    decimals: int,
):
    """Generate transaction data for approving ERC20 token."""
    try:
        rpc_url = get_rpc_url(chain_id)
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        token_address = Web3.to_checksum_address(token_address)
        spender_address = Web3.to_checksum_address(spender_address)
        tx_data = generate_erc20_approve_data(
            spender_address=spender_address, amount=amount
        )
        tx = {
            "to": token_address,
            "data": tx_data,
            "from": spender_address,
        }
        try:
            gas_limit = w3.eth.estimate_gas(tx)
            gas_price = w3.eth.gas_price
        except Exception as e:
            return (
                f"Failed when estimate gas. {e}",
                {
                    "success": False,
                    "message": f"Failed when estimate gas. {e}",
                },
            )

        return (
            "Already notify the front end to sign the transaction data and send the transaction.",
            {
                "to": token_address,
                "data": tx_data,
                "value": "0x0",
                "chain_id": chain_id,
                "name": "Approve",
                "tx_detail": {
                    "token_address": token_address,
                    "spender_address": spender_address,
                    "amount": amount,
                    "symbol": symbol,
                    "decimals": decimals,
                },
            },
        )
    except Exception as e:
        return (f"Error generating ERC20 approve transaction: {str(e)}", None)


# Minimal ABI for ERC20 balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function",
    },
]


@tool
def allowance_erc20(
    token_address: str,
    owner_address: str,
    spender_address: str,
    symbol: str,
    decimals: int,
    chain_id: int,
) -> dict:
    """Check the approved amount of an ERC20 token."""
    try:
        rpc_url = get_rpc_url(chain_id)
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        token_address = Web3.to_checksum_address(token_address)
        owner_address = owner_address = Web3.to_checksum_address(owner_address)
        spender_address = Web3.to_checksum_address(spender_address)
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        allowance = token_contract.functions.allowance(
            owner_address, spender_address
        ).call()

        return {
            "success": True,
            "allowance": str(allowance),
            "owner_address": owner_address,
            "spender_address": spender_address,
            "token_address": token_address,
            "symbol": symbol,
            "decimals": decimals,
            "chainId": chain_id,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "owner_address": owner_address,
            "spender_address": spender_address,
            "token_address": token_address,
        }


# Export all tools
tools = [
    get_supported_networks,
    get_eth_block_number,
    get_eth_balance,
    get_eth_transaction,
    get_eth_block,
    call_eth_method,
    get_token_balance,
    estimate_gas,
    get_contract_events,
    get_network_info,
    # eth_accounts,
    # eth_blockNumber,
    # eth_call,
    # eth_chainId,
    # eth_coinbase,
    # eth_createAccessList,
    eth_estimateGas,
    eth_feeHistory,
    # eth_gasPrice,
    # eth_getBalance,
    # eth_getBlockByHash,
    # eth_getBlockByNumber,
    eth_getBlockReceipts,
    eth_getBlockTransactionCountByHash,
    eth_getBlockTransactionCountByNumber,
    eth_getCode,
    eth_getLogs,
    eth_getProof,
    eth_getStorageAt,
    # eth_getTransactionByBlockHashAndIndex,
    # eth_getTransactionByBlockNumberAndIndex,
    # eth_getTransactionByHash,
    eth_getTransactionCount,
    eth_getTransactionReceipt,
    # eth_getUncleByBlockHashAndIndex,
    # eth_getUncleByBlockNumberAndIndex,
    # eth_getUncleCountByBlockHash,
    # eth_getUncleCountByBlockNumber,
    eth_maxPriorityFeePerGas,
    # eth_sendRawTransaction,
    # eth_syncing,
    net_peerCount,
    net_version,
    generate_approve_erc20,
]
