from typing import Dict, Optional
from langchain.agents import tool


@tool
def swap(
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
    from_coin_code: str,
    to_coin_code: str,
    source_type: str = None,
    slippage: float = None,
) -> Optional[Dict]:
    """
    Process swap workflow.

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
        "fromAddress": "from_address",
        "sourceFlag": "MUSSE_AI",
        "fromCoinCode": from_coin_code,
        "toCoinCode": to_coin_code,
    }
    # Add optional parameters if provided
    if source_type:
        params["sourceType"] = source_type
    if slippage:
        params["slippage"] = slippage

    order_info = {
        "from_token_address": from_token_address,
        "amount_out_min": amount_out_min,
        "equipment_no": equipment_no,
        "to_address": to_address,
        "to_token_chain": to_token_chain,
        "from_token_amount": from_token_amount,
        "from_token_chain": from_token_chain,
        "to_token_address": to_token_address,
        "from_address": "from_address",
        "from_coin_code": from_coin_code,
        "to_coin_code": to_coin_code,
        "source_type": source_type,
        "slippage": slippage,
    }
    # Return transaction data
    return {
        "success": True,
        "message": "From_chain:{from_token_chain}",
        "order_info": order_info,
        "tx_detail": {
            "from_token_address": from_token_address,
            "from_token_symbol": from_token_symbol,
            "from_token_decimals": from_token_decimals,
            "amount_out_min": amount_out_min,
            "equipment_no": equipment_no,
            "to_address": to_address,
            "to_token_chain": to_token_chain,
            "from_token_amount": from_token_amount,
            "from_token_chain": from_token_chain,
            "to_token_address": to_token_address,
            "to_token_symbol": to_token_symbol,
            "to_token_decimals": to_token_decimals,
            "from_address": "from_address",
            "from_coin_code": from_coin_code,
            "to_coin_code": to_coin_code,
            "source_type": source_type,
            "slippage": slippage,
        },
    }


from tools.tools_swap import (
    get_available_tokens,
    swap_quote,
    get_transaction_details,
    get_transaction_records,
)

tools = [
    get_available_tokens,
    swap_quote,
    swap,
    get_transaction_records,
    get_transaction_details,
]
