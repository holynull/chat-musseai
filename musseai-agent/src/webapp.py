from typing import Dict, Optional
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
import requests
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
import os

from langsmith import Client

app = FastAPI()

lsclient = Client(api_key=os.getenv("LANGCHAIN_API_KEY"))


@app.post("/api/runs/share")
async def runs_share(request: Request) -> dict:
    try:
        body = await request.json()
        sharedRunURL = lsclient.share_run(run_id=body["runId"])
        return {"success": True, "sharedRunURL": sharedRunURL, "code": 200}
    except Exception as e:
        return {"success": False, "message": e, "code": 400}


class GenerateSwapOrderRequest(BaseModel):
    hash: str
    from_token_address: str
    to_token_address: str
    from_address: str
    to_address: str
    from_token_chain: str
    to_token_chain: str
    from_token_amount: str
    amount_out_min: str
    from_coin_code: str
    to_coin_code: str
    source_type: str | None = Field(default=None)
    slippage: str | None = Field(default=None)


def generate_swap_order(
    hash: str,
    from_token_address: str,
    to_token_address: str,
    from_address: str,
    to_address: str,
    from_token_chain: str,
    to_token_chain: str,
    from_token_amount: str,
    amount_out_min: str,
    from_coin_code: str,
    to_coin_code: str,
    source_type: str = None,
    slippage: str = None,
) -> Optional[Dict]:
    """
    Generate an order record for token swap transaction using the Bridgers API.

    Args:
        hash (str): Transaction hash
        from_token_address (str): Source token contract address
        to_token_address (str): Destination token contract address
        from_address (str): User's wallet address
        to_address (str): Destination address
        from_token_chain (str): Source token chain
        to_token_chain (str): Destination token chain
        from_token_amount (str): Amount of source token
        amount_out_min (str): Minimum output amount
        from_coin_code (str): Source token code
        to_coin_code (str): Destination token code
        source_type (str, optional): Device type (H5/IOS/Android)
        slippage (str, optional): Slippage tolerance

    Returns:
        Optional[Dict]: Returns order information containing:
            - resCode: Response code (100 for success)
            - resMsg: Response message
            - data.orderId: Generated order ID
        Returns error message string if the request fails
    """
    try:
        # API endpoint
        url = "https://api.bridgers.xyz/api/exchangeRecord/updateDataAndStatus"

        # Prepare required parameters
        params = {
            "equipmentNo": from_address,
            "sourceFlag": "MUSSE_AI",
            "hash": hash,
            "fromTokenAddress": from_token_address,
            "toTokenAddress": to_token_address,
            "fromAddress": from_address,
            "toAddress": to_address,
            "fromTokenChain": from_token_chain,
            "toTokenChain": to_token_chain,
            "fromTokenAmount": from_token_amount,
            "amountOutMin": amount_out_min,
            "fromCoinCode": from_coin_code,
            "toCoinCode": to_coin_code,
        }

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
            return f"API request failed: {data.get('resMsg')}"

        # Return order data
        return data

    except requests.exceptions.RequestException as e:
        return f"API request failed: {str(e)}"
    except ValueError as e:
        return f"API response parsing failed: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@app.post("/api/generate_swap_order")
async def create_swap_order(request: GenerateSwapOrderRequest) -> dict:
    """Generate a swap order record.

    Args:
        request (GenerateSwapOrderRequest): The swap order details

    Returns:
        dict: The generated order information or error message
    """
    try:
        result = generate_swap_order(
            hash=request.hash,
            from_token_address=request.from_token_address,
            to_token_address=request.to_token_address,
            from_address=request.from_address,
            to_address=request.to_address,
            from_token_chain=request.from_token_chain.upper(),
            to_token_chain=request.to_token_chain.upper(),
            from_token_amount=request.from_token_amount,
            amount_out_min=request.amount_out_min,
            from_coin_code=request.from_coin_code,
            to_coin_code=request.to_coin_code,
            source_type=request.source_type,
            slippage=request.slippage,
        )
        return result
    except Exception as e:
        return {"error": str(e)}


class CustomHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Custom-Header"] = "Hello from middleware!"
        return response


app.add_middleware(CustomHeaderMiddleware)

origins = [
    "*",
    "http://localhost",
    "http://localhost:3000",
    "http://192.168.3.6:3000",
    "http://musse.ai",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
