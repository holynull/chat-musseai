from langchain.agents import tool
from solana.rpc.api import Client
from spl.token.client import Token
from web3 import Web3
from tronpy import Tron
import os
import requests
from typing import Optional, Union
from solders.pubkey import Pubkey
from tronpy.keys import to_hex_address, to_base58check_address, to_tvm_address
import base58

# Chain configuration data
CHAIN_CONFIG = {
    "ethereum": {"network_name": "mainnet"},
    "sepolia": {"network_name": "sepolia"},
    "tron": {"network_name": "tron"},
    "bsc": {"network_name": "bsc"},
    "polygon": {"network_name": "polygon"},
    "arbitrum": {"network_name": "arbitrum"},
    "optimism": {"network_name": "optimism"},
    "solana": {"network_name": "solana"},
}

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

# Get Infura API key from environment variable
INFURA_API_KEY = os.environ.get("INFURA_API_KEY", "")


def get_rpc_url(chain_id: int) -> str:
    """Get RPC URL for specified chain ID using Infura"""
    if not INFURA_API_KEY:
        raise ValueError("INFURA_API_KEY environment variable is not set")

    # Chain ID到网络名称和类型的映射
    chain_id_to_network = {
        1: ("ethereum", "mainnet"),
        5: ("ethereum", "goerli"),
        11155111: ("ethereum", "sepolia"),
        56: ("bsc", "mainnet"),
        97: ("bsc", "testnet"),
        137: ("polygon", "mainnet"),
        80001: ("polygon", "mumbai"),
        42161: ("arbitrum", "mainnet"),
        421613: ("arbitrum", "goerli"),
        10: ("optimism", "mainnet"),
        420: ("optimism", "goerli"),
        43114: ("avalanche", "mainnet"),
        43113: ("avalanche", "testnet"),
        8453: ("base", "mainnet"),
        84532: ("base", "sepolia"),
        81457: ("blast", "mainnet"),
    }

    if chain_id not in chain_id_to_network:
        raise ValueError(f"Unsupported chain ID: {chain_id}")

    network, network_type = chain_id_to_network[chain_id]

    # 使用类似于tools_infura.py中的逻辑构建URL
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
        if network == "ethereum" and network_type == "mainnet":
            return f"https://mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "ethereum" and network_type == "sepolia":
            return f"https://sepolia.infura.io/v3/{INFURA_API_KEY}"
        elif network == "arbitrum" and network_type == "mainnet":
            return f"https://arbitrum-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "avalanche" and network_type == "mainnet":
            return f"https://avalanche-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "base" and network_type == "sepolia":
            return f"https://base-sepolia.infura.io/v3/{INFURA_API_KEY}"
        elif network == "blast" and network_type == "mainnet":
            return f"https://blast-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "bsc" and network_type == "mainnet":
            return f"https://bsc-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "optimism" and network_type == "mainnet":
            return f"https://optimism-mainnet.infura.io/v3/{INFURA_API_KEY}"
        elif network == "polygon" and network_type == "mainnet":
            return f"https://polygon-mainnet.infura.io/v3/{INFURA_API_KEY}"
        else:
            # 通用格式，适用于其他网络
            return f"https://{network}-{network_type}.infura.io/v3/{INFURA_API_KEY}"

    # 对于不支持的网络，提供备选RPC
    fallback_rpc_urls = {
        1: f"https://mainnet.infura.io/v3/{INFURA_API_KEY}",
        56: f"https://bsc-mainnet.infura.io/v3/{INFURA_API_KEY}",
        137: f"https://polygon-mainnet.infura.io/v3/{INFURA_API_KEY}",
        42161: f"https://arbitrum-mainnet.infura.io/v3/{INFURA_API_KEY}",
        10: f"https://optimism-mainnet.infura.io/v3/{INFURA_API_KEY}",
    }

    return fallback_rpc_urls.get(chain_id, fallback_rpc_urls[1])


@tool
def connect_to_wallet():
    """Notify front end to connect to wallet."""
    return "The wallet is not ready. But already notify front end to connect to wallet."


def generate_erc20_transfer_data(to_address: str, amount: str) -> str:
    """Generate unsigned transaction data for ERC20 token transfer."""
    transfer_function_signature = "transfer(address,uint256)"
    w3 = Web3()
    fn_selector = w3.keccak(text=transfer_function_signature)[:4].hex()
    padded_address = Web3.to_bytes(hexstr=to_address).rjust(32, b"\0")
    amount_int = int(amount)
    padded_amount = amount_int.to_bytes(32, "big")
    data = fn_selector + padded_address.hex() + padded_amount.hex()
    return data


def get_erc20_decimals(token_address: str, symbol: str, chain_id) -> dict:
    """Get the decimals of an ERC20 token."""
    try:
        rpc_url = get_rpc_url(chain_id)
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        token_address = Web3.to_checksum_address(token_address)
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        decimals = token_contract.functions.decimals().call()
        return {
            "success": True,
            "decimals": decimals,
            "token_address": token_address,
            "symbol": symbol,
            "chainId": chain_id,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "token_address": token_address,
        }


def generate_transfer_erc20_tx_data(
    token_address: str, to_address: str, amount: str, chain_id: int = 1
):
    """Generate transaction data for transfer ERC20 token."""
    try:
        rpc_url = get_rpc_url(chain_id)
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        token_address = Web3.to_checksum_address(token_address)
        to_address = Web3.to_checksum_address(to_address)
        tx_data = generate_erc20_transfer_data(to_address=to_address, amount=amount)
        tx = {
            "to": token_address,
            "data": tx_data,
            "from": to_address,
        }
        gas_limit = w3.eth.estimate_gas(tx)
        gas_price = w3.eth.gas_price
    except Exception as e:
        gas_limit = 0
        gas_price = 0

    return (
        "Already notify the front end to sign the transaction data and send the transaction.",
        {
            "to": token_address,
            "data": tx_data,
            "gasLimit": str(gas_limit),
            "gasPrice": str(gas_price),
            "value": "0x0",
            "chain_id": chain_id,
        },
    )


@tool
def generate_transfer_native_token(to_address: str, amount: str, chain_id: int = 1):
    """Generate transaction data for transfer native token."""
    try:
        rpc_url = get_rpc_url(chain_id)
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        to_address = Web3.to_checksum_address(to_address)
        gas_price = w3.eth.gas_price
        gas_limit = 21000
    except Exception as e:
        gas_limit = 21000
        gas_price = 0

    return (
        "Already notify the front end to sign the transaction data and send the transaction.",
        {
            "to": to_address,
            "value": amount,
            "gasLimit": str(gas_limit),
            "gasPrice": str(gas_price),
            "data": "0x",
            "chain_id": chain_id,
        },
    )


@tool
def change_network_to(target_network: str):
    """Notify the front end to change the connected network."""
    target_network = target_network.lower()
    if target_network not in CHAIN_CONFIG:
        return (
            "Invalid network specified. Available networks: ethereum, bsc, polygon, arbitrum, optimism",
            None,
        )
    chain_config = CHAIN_CONFIG[target_network]
    return (
        f"Already notify the front end to switch to {target_network.capitalize()} network.",
        chain_config,
    )


def get_trc20_balance(token_address: str, wallet_address: str) -> dict:
    """Get TRC20 token balance of a wallet address."""
    try:
        wallet_address = to_hex_address(wallet_address)
        token_address = to_hex_address(token_address)
        client = Tron()
        contract = client.get_contract(token_address)
        balance = contract.functions.balanceOf(wallet_address)

        return {
            "success": True,
            "balance": str(balance),
            "wallet_address": base58.b58encode_check(
                bytes.fromhex(wallet_address)
            ).decode(),
            "token_address": base58.b58encode_check(
                bytes.fromhex(token_address)
            ).decode(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "wallet_address": base58.b58encode_check(
                bytes.fromhex(wallet_address)
            ).decode(),
            "token_address": base58.b58encode_check(
                bytes.fromhex(token_address)
            ).decode(),
        }


def get_trx_balance(wallet_address: str) -> dict:
    """Get TRX balance of a wallet address."""
    try:
        wallet_address = to_hex_address(wallet_address)
        client = Tron()
        balance = client.get_account_balance(wallet_address)

        return {
            "success": True,
            "balance": str(balance),
            "wallet_address": wallet_address,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "wallet_address": wallet_address}


def generate_trc20_approve_data(spender_address: str, amount: str) -> str:
    """Generate transaction data for TRC20 token approve."""
    approve_function_signature = "approve(address,uint256)"
    w3 = Web3()
    fn_selector = w3.keccak(text=approve_function_signature)[:4].hex()

    if spender_address.startswith("41"):
        spender_address = spender_address[2:]
    padded_address = bytes.fromhex(spender_address).rjust(32, b"\0")
    amount_int = int(amount)
    padded_amount = amount_int.to_bytes(32, "big")
    data = fn_selector + padded_address.hex() + padded_amount.hex()
    return data


def generate_approve_trc20(token_address: str, spender_address: str, amount: str):
    """Generate transaction data for approving TRC20 token spending."""
    try:
        spender_address = to_hex_address(spender_address)
        tx_data = generate_trc20_approve_data(
            spender_address=spender_address, amount=amount
        )
        client = Tron()
        contract = client.get_contract(token_address)
        fee_limit = 100_000_000  # Default fee limit (100 TRX)

        return (
            "Already notify the front end to sign the transaction data and send the transaction.",
            {
                "to": token_address,
                "data": tx_data,
                "feeLimit": str(fee_limit),
                "value": "0",
                "chain_id": "tron",
                "name": "Approve",
            },
        )
    except Exception as e:
        return (f"Error generating TRC20 approve transaction: {str(e)}", None)


def allowance_trc20(
    token_address: str, owner_address: str, spender_address: str
) -> dict:
    """Get the approved amount of a TRC20 token for a specific spender."""
    try:
        spender_address = to_hex_address(spender_address)
        owner_address = to_hex_address(owner_address)
        token_address = to_hex_address(token_address)
        client = Tron()
        contract = client.get_contract(token_address)
        allowance = contract.functions.allowance(owner_address, spender_address)

        return {
            "success": True,
            "allowance": str(allowance),
            "owner_address": owner_address,
            "spender_address": spender_address,
            "token_address": token_address,
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
    connect_to_wallet,
    change_network_to,
]
