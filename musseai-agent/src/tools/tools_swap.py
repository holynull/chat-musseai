import requests
from typing import List, Dict, Optional
from langchain.agents import tool
from web3 import Web3


@tool
def get_available_tokens() -> Optional[List[Dict]]:
    """
    Get the list of supported tokens for token cross chain swap functionality.

    Returns:
        Optional[List[Dict]]: Returns token list, each token contains following fields:
            - chain: Chain name
            - symbol: Token symbol
            - name: Token name
            - address: Token contract address
            - decimals: Decimal places
            - logoURI: Token logo URL
            - isCrossEnable: Cross-chain support flag
            - withdrawGas: Withdrawal gas fee
        Returns None if the request fails
    """
    try:
        # API endpoint
        url = "https://api.bridgers.xyz/api/exchangeRecord/getToken"

        # Request parameters
        # params = {'chain': chain}
        params = {}

        # Send POST request
        response = requests.post(url, params=params)
        response.raise_for_status()

        # Parse response data
        data = response.json()

        # Check response status code
        if data.get("resCode") != 100:
            return f"API request failed: {data.get('resMsg')}"

        # Return token list
        return data.get("data", {}).get("tokens", [])

    except requests.exceptions.RequestException as e:
        return f"API request failed: {data.get('resMsg')}"
    except ValueError as e:
        return f"API request failed: {data.get('resMsg')}"
    except Exception as e:
        return f"API request failed: {data.get('resMsg')}"


@tool
def swap_quote(
    # equipment_no: str,
    # source_flag: str,
    from_token_address: str,
    from_token_symbol: str,
    to_token_address: str,
    to_token_symbol: str,
    from_token_amount: str,
    from_token_chain: str,
    to_token_chain: str,
    user_addr: str = None,
    source_type: str = None,
) -> Optional[Dict]:
    """
    Get a detailed quote for token cross chain swap transaction, including expected output amount, fees, and transaction parameters.

    Args:
        from_token_address (str): Contract address of token to sell
        from_token_symbol (str): Symbol of token to sell
        to_token_address (str): Contract address of token to receive
        to_token_symbol (str): Symbol of token to receive
        from_token_amount (str): Amount of token to sell (must be calculated from actual amount and corresponding 'decimals' value from `get_available_tokens`)
        from_token_chain (str): Blockchain of token to sell
        to_token_chain (str): Blockchain of token to receive
        user_addr (str, optional): The address which token transfer from.
        source_type (str, optional): Device type (H5/IOS/Android)

    Returns:
        Optional[Dict]: Returns quote information containing:
            - amountOutMin: Minimum output amount
            - chainFee: Chain fee
            - contractAddress: Swap contract address
            - depositMin: Minimum deposit amount
            - depositMax: Maximum deposit amount
            - dex: DEX name
            - fee: Fee amount
            - feeToken: Fee token
            - fromTokenAmount: Input token amount
            - fromTokenDecimal: Input token decimal places
            - toTokenAmount: Output token amount
            - toTokenDecimal: Output token decimal places
            - path: Token swap path
            - logoUrl: Logo URL
        Returns error message string if the request fails
    """
    try:
        # API endpoint
        url = "https://api.bridgers.xyz/api/sswap/quote"

        # Prepare required parameters
        params = {
            "equipmentNo": "eddie_pc" if not user_addr else user_addr,
            "sourceFlag": "MUSSE_AI",
            "fromTokenAddress": from_token_address,
            "toTokenAddress": to_token_address,
            "fromTokenAmount": from_token_amount,
            "fromTokenChain": from_token_chain.upper(),
            "toTokenChain": to_token_chain.upper(),
        }
        # import json

        # print(json.dumps(params))

        # Add optional parameters if provided
        if user_addr:
            params["userAddr"] = user_addr
        if source_type:
            params["sourceType"] = source_type

        # Send POST request
        response = requests.post(url, json=params)
        response.raise_for_status()

        # Parse response data
        data = response.json()
        # print(data)

        # Check response status code
        if data.get("resCode") != 100:
            return f"API request failed: {data.get('resMsg')}"

        # Return quote data
        txData = data.get("data", {}).get("txData", {})
        if txData["amountOutMin"] == "0":
            return f"Error: Parameter `from_token_amount={from_token_amount}` is wrong, please check the `decimals` of the token on `from_token_address`."
        else:
            txData["tx_detail"] = {
                "from_token_address": from_token_address,
                "from_token_symbol": from_token_symbol,
                "to_token_address": to_token_address,
                "to_token_symbol": to_token_symbol,
                "from_token_amount": from_token_amount,
                "from_token_chain": from_token_chain,
                "to_token_chain": to_token_chain,
                "user_addr": user_addr,
                "source_type": source_type,
            }
            return txData

    except requests.exceptions.RequestException as e:
        return f"API request failed: {str(e)}"
    except ValueError as e:
        return f"API response parsing failed: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@tool
def generate_swap_tx_data(
    from_token_address: str,
    from_token_symbol: str,
    from_token_decimals: int,
    amount_out_min: str,
    equipment_no: str,
    to_address: str,
    to_token_chain: str,
    from_token_amount: str,
    from_token_chain: str,
    to_token_address: str,
    to_token_symbol: str,
    to_token_decimals: int,
    from_address: str,
    from_coin_code: str,
    to_coin_code: str,
    source_type: str = None,
    slippage: float = None,
) -> Optional[Dict]:
    """
    Notify the front end to generate a button to send a token swap transaction.

    Args:
        from_token_address (str): Source token contract address, `address` in the return from `get_available_tokens`
        from_token_symbol (str): Symbol of from token
        from_token_decimals (int): Decimals of from token
        amount_out_min (str): Minimum output amount, must the same as `amountOutMin` in the return from `swap_quote`
        equipment_no (str): Equipment number identifier or user's wallet address
        to_address (str): Destination address. The receiving address of the `to_token_chain` provided by the user.
        to_token_chain (str): Destination token chain, `chain` in the return from `get_available_tokens`
        from_token_amount (str): Amount of source token to swap
        from_token_chain (str): Source token chain, `chain` in the return from `get_available_tokens`
        to_token_address (str): Destination token contract address, `address` in the return from `get_available_tokens`
        to_token_symbol (str): Symbol of to token
        to_token_decimals (int): Decimals of to token
        from_address (str): User's wallet address
        from_coin_code (str): Source token code, `symbol` return from `get_available_tokens`
        to_coin_code (str): Destination token code, `symbol` return from `get_available_tokens`
        source_type (str, optional): Source type (H5/IOS/Android)
        slippage (float, optional): Slippage tolerance percentage

    Returns:
        Optional[Dict]: Returns transaction data containing:
            - txHash: Transaction hash
            - status: Transaction status
            - Additional transaction details
        Returns error message string if the request fails
    """
    # from_token_address = Web3.to_checksum_address(from_token_address)
    # to_address = Web3.to_checksum_address(to_address)
    # to_token_address = Web3.to_checksum_address(to_token_address)
    # from_address = Web3.to_checksum_address(from_address)
    # API endpoint
    url = "https://api.bridgers.xyz/api/sswap/swap"

    # Prepare required parameters
    params = {
        "fromTokenAddress": from_token_address,
        "amountOutMin": amount_out_min,
        "equipmentNo": equipment_no,
        "toAddress": to_address,
        "toTokenChain": to_token_chain.upper(),
        "fromTokenAmount": from_token_amount,
        "fromTokenChain": from_token_chain.upper(),
        "toTokenAddress": to_token_address,
        "fromAddress": from_address,
        "sourceFlag": "MUSSE_AI",
        "fromCoinCode": from_coin_code,
        "toCoinCode": to_coin_code,
    }
    # import json

    # print(json.dumps(params))

    # Add optional parameters if provided
    if source_type:
        params["sourceType"] = source_type
    if slippage:
        params["slippage"] = slippage

    # Send POST request
    response = requests.post(url, json=params)
    response.raise_for_status()

    # Parse response data
    data = response.json()

    # Check response status code
    if data.get("resCode") != 100:
        return (
            f"Generate transaction data API error occured. {data.get('resCode')}",
            {
                "success": False,
                "message": f"API request failed: {data.get('resMsg')}",
            },
        )
    tokens = get_available_tokens.invoke({})
    evm_from_token = [
        t
        for t in tokens
        if t["chainId"]
        and t["chainId"] != ""
        and from_token_address == t["address"]
        and from_token_chain == t["chain"]
    ]
    if len(evm_from_token) > 0 and evm_from_token[0]["chain"] != "TRON":
        # RPC URL mapping for different chains
        rpc_urls = {
            1: "https://eth.public-rpc.com",  # Ethereum mainnet
            56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
            137: "https://polygon-rpc.com",  # Polygon mainnet
            42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
            10: "https://mainnet.optimism.io",  # Optimism
        }
        rpc_url = rpc_urls.get(
            int(evm_from_token[0]["chainId"])
        )  # Default to Ethereum mainnet if chain_id not found

        # Create Web3 instance
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        tx = data.get("data", {}).get("txData")
        tx["to"] = Web3.to_checksum_address(tx["to"])
        tx["from"] = Web3.to_checksum_address(from_address)
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
        swap_data = {
            "txData": data.get("data", {}).get("txData"),
            "gasLimit": gas_limit,
            "gasPrice": gas_price,
            "chain_id": evm_from_token[0]["chainId"],
            "chain_type": "evm",
            "name": "Send Swap Transaction",
        }
    elif len(evm_from_token) > 0 and evm_from_token[0]["chain"] == "TRON":
        swap_data = {
            "txData": data.get("data", {}).get("txData"),
            "chain_id": evm_from_token[0]["chainId"],
            "chain_type": "tron",
            "name": "Send Swap Transaction",
        }
    elif from_token_chain.upper() == "SOLANA":
        # Solana chain handling
        tx_data = data.get("data", {}).get("txData", {})
        if "tx" in tx_data and "signer" in tx_data:
            swap_data = {
                "txData": {"tx": tx_data["tx"], "signer": tx_data["signer"]},
                "chain_type": "solana",
                "name": "Send Swap Transaction",
            }
        else:
            swap_data = {
                "txData": tx_data,
                "chain_type": "solana",
                "name": "Send Swap Transaction",
            }

    else:
        swap_data = {
            "txData": data.get("data", {}).get("txData"),
            "chain_type": "unknown",
            "name": "Send Swap Transaction",
        }
        return (
            f"Can't get from chain type from data of token address: `{from_token_address}` and from token chain `{from_token_chain}`",
            {
                "success": False,
                "message": f"Can't get from chain type from token address: `{from_token_address}` and from token chain `{from_token_chain}`",
            },
        )

    order_info = {
        "from_token_address": from_token_address,
        "amount_out_min": amount_out_min,
        "equipment_no": equipment_no,
        "to_address": to_address,
        "to_token_chain": to_token_chain,
        "from_token_amount": from_token_amount,
        "from_token_chain": from_token_chain,
        "to_token_address": to_token_address,
        "from_address": from_address,
        "from_coin_code": from_coin_code,
        "to_coin_code": to_coin_code,
        "source_type": source_type,
        "slippage": slippage,
    }
    # Return transaction data
    return (
        "Already notify the front end to generate a button to sign the transaction data and send the transaction. The button will be named after the `name` in the data.",
        {
            "success": True,
            "message": "From_chain:{from_token_chain}",
            "swap_data": swap_data,
            "order_info": order_info,
            "tx_detail": {
                "from_token_address": from_token_address,
                "from_token_symbol":from_token_symbol,
                "from_token_decimals":from_token_decimals,
                "amount_out_min": amount_out_min,
                "equipment_no": equipment_no,
                "to_address": to_address,
                "to_token_chain": to_token_chain,
                "from_token_amount": from_token_amount,
                "from_token_chain": from_token_chain,
                "to_token_address": to_token_address,
                "to_token_symbol":to_token_symbol,
                "to_token_decimals":to_token_decimals,
                "from_address": from_address,
                "from_coin_code": from_coin_code,
                "to_coin_code": to_coin_code,
                "source_type": source_type,
                "slippage": slippage,
            },
        },
    )


@tool
def get_transaction_records(
    equipment_no: str,
    page_no: int,
    page_size: int,
    from_address: str,
    source_type: str = None,
) -> Optional[Dict]:
    """
    Get transaction records using the Bridgers API.

    Args:
        equipment_no (str): Equipment number or user's unique identifier or user's wallet address
        page_no (int): Current page number
        page_size (int): Number of records per page
        from_address (str): User's wallet address
        source_type (str, optional): Device type (H5/IOS/Android)

    Returns:
        Optional[Dict]: Returns transaction records containing:
            - list: List of transaction records, each containing:
                - id: Record ID
                - orderId: Order number
                - fromTokenAddress: Source token contract address
                - toTokenAddress: Target token contract address
                - fromTokenAmount: Source token amount
                - toTokenAmount: Target token expected amount
                - fromAddress: User's source address
                - slippage: Slippage
                - fromChain: Source chain
                - toChain: Target chain
                - hash: Deposit hash
                - status: Order status
                - createTime: Order creation time
                And more transaction-related fields
            - total: Total pages
            - pageNo: Current page number
        Returns error message string if the request fails
    """
    try:
        # API endpoint
        url = "https://api.bridgers.xyz/api/exchangeRecord/getTransData"

        # Prepare required parameters
        params = {
            "equipmentNo": equipment_no,
            "sourceFlag": "MUSSE_AI",
            "pageNo": page_no,
            "pageSize": page_size,
            "fromAddress": from_address,
        }

        # Add optional parameters if provided
        if source_type:
            params["sourceType"] = source_type

        # Send POST request
        response = requests.post(url, json=params)
        response.raise_for_status()

        # Parse response data
        data = response.json()

        # Check response status code
        if data.get("resCode") != 100:
            return f"API request failed: {data.get('resMsg')}"

        # Return transaction records data
        return data.get("data", {})

    except requests.exceptions.RequestException as e:
        return f"API request failed: {str(e)}"
    except ValueError as e:
        return f"API response parsing failed: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@tool
def get_transaction_details(orderId: str) -> Optional[Dict]:
    """
    Get detailed information about a specific transaction using the Bridgers API.

    Args:
        orderId (str): The transaction order ID to query, return from `get_transaction_records`

    Returns:
        Optional[Dict]: Returns transaction details containing:
            - id: Record ID
            - orderId: Order number
            - fromTokenAddress: Source token contract address
            - toTokenAddress: Target token contract address
            - fromTokenAmount: Source token amount
            - toTokenAmount: Target token expected amount
            - fromAddress: User's source address
            - slippage: Slippage
            - fromChain: Source chain
            - toChain: Target chain
            - hash: Deposit hash
            - depositHashExplore: Deposit block explorer URL
            - status: Order status
            - createTime: Order creation time
            And many other transaction-related fields
        Returns error message string if the request fails
    """
    try:
        # API endpoint
        url = "https://api.bridgers.xyz/api/exchangeRecord/getTransDataById"

        # Prepare required parameters
        params = {
            "orderId": orderId,
        }

        # Send POST request
        response = requests.post(url, json=params)
        response.raise_for_status()

        # Parse response data
        data = response.json()

        # Check response status code
        if data.get("resCode") != 100:
            return f"API request failed: {data.get('resMsg')}"

        # Return transaction details
        return data.get("data", {})

    except requests.exceptions.RequestException as e:
        return f"API request failed: {str(e)}"
    except ValueError as e:
        return f"API response parsing failed: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


tools = [
    get_available_tokens,
    swap_quote,
    generate_swap_tx_data,
    get_transaction_records,
    get_transaction_details,
]
