import requests
import json
from typing import List, Dict, Optional, Any, Union
from langchain.agents import tool
from web3 import Web3
import os

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
            - network: Network name (e.g., ethereum, polygon)
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
        network (str): Blockchain network name (ethereum, polygon, optimism, arbitrum)
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".

    Returns:
        Dict: Returns a dictionary containing:
            - block_number: Latest block number
            - network: Requested network
            - network_type: Requested network type
    """
    try:
        infura_url = get_infura_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        # Get latest block number
        block_number = w3.eth.block_number

        return {
            "block_number": block_number,
            "network": network,
            "network_type": network_type,
        }
    except Exception as e:
        return f"Error getting block number: {str(e)}"


@tool
def get_eth_balance(address: str, network: str, network_type: str = "mainnet") -> Dict:
    """
    Get native token balance for specified address on specified network.

    Args:
        address (str): Ethereum address to query balance for
        network (str): Blockchain network name (ethereum, polygon, optimism, arbitrum)
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
        return f"Error getting balance: {str(e)}"


@tool
def get_eth_transaction(
    tx_hash: str, network: str, network_type: str = "mainnet"
) -> Dict:
    """
    Get transaction details for specified transaction hash on specified network.

    Args:
        tx_hash (str): Transaction hash
        network (str): Blockchain network name (ethereum, polygon, optimism, arbitrum)
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
        return f"Error getting transaction: {str(e)}"


@tool
def get_eth_block(
    block_identifier: Union[str, int],
    network: str,
    network_type: str = "mainnet",
    full_transactions: bool = False,
) -> Dict:
    """
    Get block details for specified block on specified network.

    Args:
        block_identifier (Union[str, int]): Block number or block hash or special tag (e.g., "latest")
        network (str): Blockchain network name (ethereum, polygon, optimism, arbitrum)
        network_type (str, optional): Network type (mainnet, goerli, sepolia, etc.). Defaults to "mainnet".
        full_transactions (bool, optional): Whether to return full transaction objects. If False, only returns transaction hashes. Defaults to False.

    Returns:
        Dict: Returns a dictionary containing:
            - number: Block number
            - hash: Block hash
            - parentHash: Parent block hash
            - timestamp: Block timestamp
            - transactions: List of transactions (hashes or full objects)
            - miner: Miner address
            - gasUsed: Gas used
            - gasLimit: Gas limit
            - network: Requested network
            - network_type: Requested network type
            - explorer_url: Block URL in block explorer
    """
    try:
        infura_url = get_rpc_url(network, network_type)
        w3 = Web3(Web3.HTTPProvider(infura_url))

        # Get block
        block = w3.eth.get_block(block_identifier, full_transactions=full_transactions)

        # Build explorer URL
        explorer_base = NETWORK_CONFIG[network.lower()][network_type.lower()][
            "explorer"
        ]
        if isinstance(block_identifier, (int, str)) and not isinstance(
            block_identifier, bool
        ):
            block_id_for_url = (
                block.hash.hex() if hasattr(block, "hash") else block_identifier
            )
            explorer_url = f"{explorer_base}/block/{block_id_for_url}"
        else:
            explorer_url = f"{explorer_base}"

        # Convert to serializable dictionary
        if full_transactions:
            # Convert transaction objects to dictionaries if full transactions requested
            transactions = []
            for tx in block.transactions:
                if hasattr(tx, "to") and hasattr(tx, "from"):
                    tx_dict = {
                        "hash": tx.hash.hex(),
                        "from": tx["from"],
                        "to": (
                            tx["to"] if tx["to"] else None
                        ),  # Contract creation transactions have no 'to' address
                        "value": tx.value,
                        "gas": tx.gas,
                        "gasPrice": tx.gasPrice,
                        "nonce": tx.nonce,
                    }
                    transactions.append(tx_dict)
                else:
                    transactions.append(tx.hex())
        else:
            transactions = [tx.hex() for tx in block.transactions]

        block_dict = {
            "number": block.number,
            "hash": block.hash.hex(),
            "parentHash": block.parentHash.hex(),
            "timestamp": block.timestamp,
            "transactions": transactions,
            "miner": block.miner,
            "gasUsed": block.gasUsed,
            "gasLimit": block.gasLimit,
            "network": network,
            "network_type": network_type,
            "explorer_url": explorer_url,
        }

        return block_dict
    except Exception as e:
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
        network (str): Blockchain network name (ethereum, polygon, optimism, arbitrum)
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
        network (str): Blockchain network name (ethereum, polygon, optimism, arbitrum)
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
        network (str, optional): Blockchain network name. Defaults to "ethereum".
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
        network (str, optional): Blockchain network name. Defaults to "ethereum".
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
        return f"Error getting contract events: {str(e)}"


@tool
def get_network_info(network: str, network_type: str = "mainnet") -> Dict:
    """
    Get general information about the specified network.

    Args:
        network (str): Blockchain network name (ethereum, polygon, optimism, arbitrum)
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
        return f"Error getting network info: {str(e)}"


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
]
