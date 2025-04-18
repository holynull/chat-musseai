from langchain.agents import tool
from solana.rpc.api import Client
from spl.token.client import Token
from web3 import Web3
from tronpy import Tron

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


@tool
def connect_to_wallet():
    """Notify front end to connect to wallet."""

    return "The wallet is not ready. But already notify front end to connect to wallet."


def generate_erc20_transfer_data(to_address: str, amount: str) -> str:
    """Generate unsigned transaction data for ERC20 token transfer.

    Args:
        to_address: The recipient address
        amount: The amount to transfer (in token's smallest unit)

    Returns:
        The hex string of unsigned transaction data
    """
    # ERC20 transfer function signature
    transfer_function_signature = "transfer(address,uint256)"

    # Create Web3 instance
    w3 = Web3()

    # Create function signature
    fn_selector = w3.keccak(text=transfer_function_signature)[:4].hex()

    # Encode parameters
    # Pad address to 32 bytes
    padded_address = Web3.to_bytes(hexstr=to_address).rjust(32, b"\0")
    # Pad amount to 32 bytes
    amount_int = int(amount)
    padded_amount = amount_int.to_bytes(32, "big")

    # Combine all parts
    data = fn_selector + padded_address.hex() + padded_amount.hex()

    return data


@tool
def get_erc20_decimals(token_address: str, symbol: str, chain_id) -> dict:
    """Get the decimals of an ERC20 token.

    Args:
        token_address: The address of the ERC20 token contract
        symbol: Symbole of the token.
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A dictionary containing the decimals information
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure address is checksummed
    token_address = Web3.to_checksum_address(token_address)

    try:
        # Create contract instance
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        # Get decimals
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


@tool
def generate_transfer_erc20_tx_data(
    token_address: str, to_address: str, amount: str, chain_id: int = 1
):
    """Generate transaction data for transfer ERC20 token to `to_address`.

    Args:
        token_address: The address of the ERC20 token contract
        to_address: The recipient address
        amount: The amount to transfer (in token's smalest unit)
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A message and the hex string of unsigned transaction data
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id, rpc_urls[1]
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure addresses are checksummed
    token_address = Web3.to_checksum_address(token_address)
    to_address = Web3.to_checksum_address(to_address)

    # Generate transaction data
    tx_data = generate_erc20_transfer_data(to_address=to_address, amount=amount)

    # Prepare transaction object for gas estimation
    tx = {
        "to": token_address,
        "data": tx_data,
        "from": to_address,  # Using recipient address for estimation
    }

    try:
        # Estimate gas limit
        gas_limit = w3.eth.estimate_gas(tx)
        # Get current gas price
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
def get_balance_of_address(
    token_address: str, wallet_address: str, symbol: str, decimals: int, chain_id: int
) -> dict:
    """Get the balance of an ERC20 token for a specific address.

    Args:
        token_address: The address of the ERC20 token contract
        wallet_address: The address to check the balance for
        symbol: Symbol of the token.
        decimals: Decimals of the token.
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A dictionary containing the balance information
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id
    )  # Default to Ethereum mainnet if chain_id not found
    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure addresses are checksummed
    token_address = Web3.to_checksum_address(token_address)
    wallet_address = Web3.to_checksum_address(wallet_address)

    try:
        # Create contract instance
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        # Get balance
        balance = token_contract.functions.balanceOf(wallet_address).call()

        return {
            "success": True,
            "balance": str(balance),
            "wallet_address": wallet_address,
            "token_address": token_address,
            "symbol": symbol,
            "decimals": decimals,
            "chainId": chain_id,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "wallet_address": wallet_address,
            "token_address": token_address,
        }


@tool
def generate_transfer_native_token(to_address: str, amount: str, chain_id: int = 1):
    """Generate transaction data for transfer native token (like ETH, BNB) to `to_address`.

    Args:
        to_address: The recipient address
        amount: The amount to transfer (in wei)
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A message and the transaction data for signing
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id, rpc_urls[1]
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure address is checksummed
    to_address = Web3.to_checksum_address(to_address)

    try:
        # Get current gas price
        gas_price = w3.eth.gas_price
        # For native token transfers, gas limit is typically 21000
        gas_limit = 21000
    except Exception as e:
        gas_limit = 21000
        gas_price = 0

    return (
        "Already notify the front end to sign the transaction data and send the transaction.",
        {
            "to": to_address,
            "value": amount,  # amount in wei
            "gasLimit": str(gas_limit),
            "gasPrice": str(gas_price),
            "data": "0x",  # Empty data for native token transfer
            "chain_id": chain_id,
        },
    )


@tool
def change_network_to(target_network: str):
    """Notify the front end to change the connected network to the target network in wallet.

    Args:
        target_network: Network name to switch to. Available networks: ethereum, bsc, tron, arbitrum, sepolia, solana,polygon,optimism

    Returns:
        A tuple containing a message and the chain configuration data
    """
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


def generate_erc20_approve_data(spender_address: str, amount: str) -> str:
    """Generate unsigned transaction data for ERC20 token approve.

    Args:
        spender_address: The spender address to approve
        amount: The amount to approve (in token's smallest unit)

    Returns:
        The hex string of unsigned transaction data
    """
    # ERC20 approve function signature
    approve_function_signature = "approve(address,uint256)"

    # Create Web3 instance
    w3 = Web3()

    # Create function signature
    fn_selector = w3.keccak(text=approve_function_signature)[:4].hex()

    # Encode parameters
    # Pad address to 32 bytes
    padded_address = Web3.to_bytes(hexstr=spender_address).rjust(32, b"\0")
    # Pad amount to 32 bytes
    amount_int = int(amount)
    padded_amount = amount_int.to_bytes(32, "big")

    # Combine all parts
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
    """Notify the front end to generate a button to send tansaction data for approve spender to use ERC20 token.

    Args:
        token_address: The address of the ERC20 token contract
        spender_address: The address to approve
        amount: The amount to approve (in token's smallest unit)
        chain_id: Chain ID, available: ethereum, bsc, tron, arbitrum, sepolia, solana,polygon,optimism
        symbol: Token's symbol.
        decimals: Token's decimals.

    Returns:
        A message and the hex string of unsigned transaction data
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure addresses are checksummed
    token_address = Web3.to_checksum_address(token_address)
    spender_address = Web3.to_checksum_address(spender_address)

    # Generate transaction data
    tx_data = generate_erc20_approve_data(
        spender_address=spender_address, amount=amount
    )

    # Prepare transaction object for gas estimation
    tx = {
        "to": token_address,
        "data": tx_data,
        "from": spender_address,  # Using spender address for estimation
    }

    try:
        # Estimate gas limit
        gas_limit = w3.eth.estimate_gas(tx)
        # Get current gas price
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
        "Already notify the front end to sign the transaction data and send the transaction. The button will be named after the `name` in the data.",
        {
            "to": token_address,
            "data": tx_data,
            # "gasLimit": str(gas_limit),
            # "gasPrice": str(gas_price),
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


@tool
def allowance_erc20(
    token_address: str,
    owner_address: str,
    spender_address: str,
    symbol: str,
    decimals: int,
    chain_id: int,
) -> dict:
    """Check the approved amount of an ERC20 token for a specific spender.

    Args:
        token_address: The address of the ERC20 token contract
        owner_address: The address who approved the tokens
        spender_address: The address to check the allowance for
        symbol: Symbol of the token.
        decimals: Decimals of the token.
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A dictionary containing the allowance information
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure addresses are checksummed
    token_address = Web3.to_checksum_address(token_address)
    owner_address = Web3.to_checksum_address(owner_address)
    spender_address = Web3.to_checksum_address(spender_address)

    try:
        # Create contract instance
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        # Get allowance
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


from solana.rpc.api import Client
import requests
from typing import Optional, Union
from solders.pubkey import Pubkey


@tool
def get_sol_balance(wallet_address: str) -> Optional[float]:
    """
    Query SOL balance for a specified wallet address on Solana blockchain.

    Args:
        wallet_address (str): The Solana wallet address to query

    Returns:
        Optional[float]: SOL balance amount, or None if query fails

    Example:
        >>> balance = get_sol_balance("your_wallet_address")
        >>> print(f"SOL Balance: {balance}")
    """
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    try:
        # Create Solana client connection
        solana_client = Client(rpc_url)

        # Get balance in lamports
        response = solana_client.get_balance(Pubkey.from_string(wallet_address))

        if response.value:
            # Convert lamports to SOL (1 SOL = 10^9 lamports)
            balance_in_sol = response.value / 1_000_000_000
            return {"address": wallet_address, "balance": balance_in_sol}
        return None

    except Exception as e:
        print(f"Error occurred while querying SOL balance: {str(e)}")
        return None


@tool
def get_spl_token_balance(
    wallet_address: str, token_mint_address: str, symbol: str
) -> Optional[Union[float, int]]:
    """
    Query SPL token balance for a specified wallet address on Solana blockchain.

    Args:
        wallet_address (str): The Solana wallet address to query
        token_mint_address (str): The mint address of the token
                symbol: Symbol of the token


    Returns:
        Optional[Union[float, int]]: Token balance amount, or None if query fails

    Example:
        >>> token_balance = get_token_balance("wallet_address", "token_mint_address")
        >>> print(f"Token Balance: {token_balance}")
    """
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    try:
        # Set request headers
        headers = {"Content-Type": "application/json"}

        # Construct RPC request payload
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                wallet_address,
                {"mint": token_mint_address},
                {"encoding": "jsonParsed"},
            ],
        }

        # Send POST request to Solana RPC node
        response = requests.post(rpc_url, headers=headers, json=payload)
        result = response.json()

        # Parse response data
        if (
            "result" in result
            and "value" in result["result"]
            and len(result["result"]["value"]) > 0
        ):

            # Extract token balance from response
            token_balance = result["result"]["value"][0]["account"]["data"]["parsed"][
                "info"
            ]["tokenAmount"]["uiAmount"]
            return {
                "success": True,
                "balance": token_balance,
                "symbol": symbol,
                "token_mint_address": token_mint_address,
            }

        return 0  # Return 0 if no token account found

    except Exception as e:
        return f"Error occurred while querying token balance: {str(e)}"


from tronpy.keys import to_hex_address, to_base58check_address, to_tvm_address
import base58


@tool
def get_trc20_balance(token_address: str, wallet_address: str) -> dict:
    """Get TRC20 token balance of a wallet address.

    Args:
        token_address (str): The TRC20 token contract address
        wallet_address (str): The TRON wallet address to check

    Returns:
        dict: A dictionary containing the balance information
            {
                'success': bool,
                'balance': str,  # Balance in token's smallest unit
                'wallet_address': str,
                'token_address': str
            }
    """
    try:
        # Handle wallet address that starts with '0x'
        # if wallet_address.startswith('0x'):
        #     wallet_address = wallet_address[2:]
        wallet_address = to_hex_address(wallet_address)
        token_address = to_hex_address(token_address)
        # Connect to TRON mainnet
        client = Tron()

        # Get contract instance
        contract = client.get_contract(token_address)

        # Get token balance
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


@tool
def get_trx_balance(wallet_address: str) -> dict:
    """Get TRX balance of a wallet address.

    Args:
        wallet_address (str): The TRON wallet address to check

    Returns:
        dict: A dictionary containing the balance information
            {
                'success': bool,
                'balance': str,  # Balance in TRX
                'wallet_address': str
            }
    """
    try:
        wallet_address = to_hex_address(wallet_address)
        # Connect to TRON mainnet
        client = Tron()

        # Get account balance
        balance = client.get_account_balance(wallet_address)

        return {
            "success": True,
            "balance": str(balance),
            "wallet_address": wallet_address,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "wallet_address": wallet_address}
        return None


def generate_trc20_approve_data(spender_address: str, amount: str) -> str:
    """Notify the front end to generate a button to send transaction data for TRC20 token approve.

    Args:
        spender_address: The spender address to approve
        amount: The amount to approve (in token's smallest unit)

    Returns:
        The hex string of transaction data
    """
    # TRC20 approve function signature (same as ERC20)
    approve_function_signature = "approve(address,uint256)"

    # Create Web3 instance for keccak hash (compatible with TRC20)
    w3 = Web3()

    # Create function signature hash
    fn_selector = w3.keccak(text=approve_function_signature)[:4].hex()

    # Encode parameters
    # Remove '41' prefix if present in the address
    if spender_address.startswith("41"):
        spender_address = spender_address[2:]
    # Pad address to 32 bytes
    padded_address = bytes.fromhex(spender_address).rjust(32, b"\0")
    # Pad amount to 32 bytes
    amount_int = int(amount)
    padded_amount = amount_int.to_bytes(32, "big")

    # Combine all parts
    data = fn_selector + padded_address.hex() + padded_amount.hex()

    return data


@tool
def generate_approve_trc20(token_address: str, spender_address: str, amount: str):
    """Generate transaction data for approving TRC20 token spending.

    Args:
        token_address: The address of the TRC20 token contract
        spender_address: The address to approve
        amount: The amount to approve (in token's smallest unit)

    Returns:
        A message and the transaction data for signing
    """
    try:
        spender_address = to_hex_address(spender_address)
        # _token_address = to_hex_address(token_address)
        # Remove '41' prefix if present in addresses
        # if token_address.startswith("41"):
        #     token_address = token_address[2:]
        # if spender_address.startswith("41"):
        #     spender_address = spender_address[2:]

        # Generate transaction data
        tx_data = generate_trc20_approve_data(
            spender_address=spender_address, amount=amount
        )

        # Connect to TRON network
        client = Tron()

        # Prepare transaction for fee estimation
        contract = client.get_contract(token_address)

        # Get fee estimation (this is approximate as TRON uses bandwidth/energy)
        fee_limit = 100_000_000  # Default fee limit (100 TRX)

        return (
            "Already notify the front end to sign the transaction data and send the transaction. The button will be named after the `name` in the data.",
            {
                "to": token_address,
                "data": tx_data,
                "feeLimit": str(fee_limit),
                "value": "0",
                "chain_id": "tron",  # Indicate this is a TRON transaction
                "name": "Approve",
            },
        )

    except Exception as e:
        return (f"Error generating TRC20 approve transaction: {str(e)}", None)


@tool
def allowance_trc20(
    token_address: str, owner_address: str, spender_address: str
) -> dict:
    """Get the approved amount of a TRC20 token for a specific spender.

    Args:
        token_address: The TRC20 token contract address
        owner_address: The address who approved the tokens
        spender_address: The address to check the allowance for

    Returns:
        A dictionary containing the allowance information:
            {
                'success': bool,
                'allowance': str,  # Allowance in token's smallest unit
                'owner_address': str,
                'spender_address': str,
                'token_address': str
            }
    """
    try:
        spender_address = to_hex_address(spender_address)
        owner_address = to_hex_address(owner_address)
        token_address = to_hex_address(token_address)
        # Connect to TRON mainnet
        client = Tron()

        # Get contract instance
        contract = client.get_contract(token_address)

        # Get allowance
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


tools = [
    connect_to_wallet,
    # generate_transfer_erc20_tx_data,
    get_balance_of_address,
    # get_erc20_decimals,
    # generate_transfer_native_token,
    change_network_to,
    generate_approve_erc20,
    allowance_erc20,
    get_sol_balance,
    get_spl_token_balance,
    # get_trx_balance,
    # get_trc20_balance,
    # generate_approve_trc20,
    # allowance_trc20,
]
