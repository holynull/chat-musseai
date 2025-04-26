import logging
from typing import Dict, Optional
import aiohttp
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import pytz
import requests
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid

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


@app.get("/api/tradingview/symbol_search")
async def symbol_search(text: str):
    """
    搜索TradingView符号，并优化返回格式以便前端使用。

    Args:
        query (str): 要搜索的加密货币代码，例如 BTC, ETH, SOL 等

    Returns:
        dict: 包含搜索结果的字典，格式如下：
            {
                "symbols_remaining": int,  # 剩余结果数量
                "symbols": [
                    {
                        "symbol": str,     # 交易对符号
                        "description": str, # 描述
                        "type": str,       # 类型
                        "exchange": str,   # 交易所
                        "currency_code": str, # 货币代码
                        ...
                    },
                    ...
                ]
            }
    """
    # 确保query参数不为空
    if not text:
        return {"symbols_remaining": 0, "symbols": []}

    # TradingView搜索API的URL
    url = "https://symbol-search.tradingview.com/symbol_search/v3/"

    # 优化请求参数，增加对加密货币的偏好
    params = {
        "text": text,
        "hl": 1,
        "exchange": "",
        "lang": "en",
        "search_type": "crypto",  # 指定搜索类型为加密货币
        "domain": "production",
        "sort_by_country": "US",
        # "type": "crypto",  # 尝试优先返回加密货币结果
        "promo": "true",
    }

    # 请求头
    headers = {
        "authority": "symbol-search.tradingview.com",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "origin": "https://www.tradingview.com",
        "pragma": "no-cache",
        "referer": "https://www.tradingview.com/",
        "sec-ch-ua": '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    }
    # 获取系统代理设置
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    # 根据URL协议选择代理
    proxy = https_proxy if url.startswith("https") else http_proxy

    # 发送请求
    try:
        async with aiohttp.ClientSession(proxy=proxy) as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    return {
                        "result": await response.json(),
                        "error": f"TradingView API returned status code {response.status}",
                        "symbols_remaining": 0,
                        "symbols": [],
                    }

                # 解析JSON响应
                data = await response.json()

                # 优化返回结果
                return data
    except aiohttp.ClientError as e:
        return {
            "error": f"Request error: {str(e)}",
            "symbols_remaining": 0,
            "symbols": [],
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "symbols_remaining": 0,
            "symbols": [],
        }


# class CustomHeaderMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         response = await call_next(request)
#         response.headers["X-Custom-Header"] = "Hello from middleware!"
#         return response


# app.add_middleware(CustomHeaderMiddleware)


import secrets
import hashlib
import datetime
from typing import Dict, Optional, List
import aiohttp
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, EmailStr
import requests
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
import os
import jwt
from passlib.context import CryptContext
from jose import JWTError, jwt

# 现有导入
from langsmith import Client

# JWT配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# 密码哈希工具
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

# 模拟用户数据库 - 在实际应用中应该使用真实数据库
users_db = {}


# 用户模型
class User(BaseModel):
    user_id: str  # 新增字段
    email: EmailStr
    username: str
    hashed_password: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    created_at: datetime.datetime


# 用户存储模型 - 向客户端返回的用户信息
class UserInDB(BaseModel):
    user_id: str  # 新增字段
    email: str
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    created_at: datetime.datetime


# 用户注册请求
class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None


# 用户登录请求
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# 令牌模型
class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserInDB


# 令牌数据模型
class TokenData(BaseModel):
    email: Optional[str] = None


# 用户密码更改请求
class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# 密码哈希函数
def get_password_hash(password):
    return pwd_context.hash(password)


# 验证密码
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# 获取用户
def get_user(email: str):
    if email in users_db:
        user_dict = users_db[email]
        return User(**user_dict)
    return None


# 验证用户
def authenticate_user(email: str, password: str):
    user = get_user(email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


# 创建访问令牌
def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 获取当前用户
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = get_user(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


# 获取当前活跃用户
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# 用户注册接口
@app.post("/api/register", response_model=Token)
async def register_user(user_data: UserRegister):
    # 检查邮箱是否已注册
    if user_data.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # 检查用户名是否已存在
    for email, user in users_db.items():
        if user["username"] == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
            )

    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    user_obj = User(
        user_id=str(uuid.uuid4()),
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        disabled=False,
        created_at=datetime.datetime.utcnow(),
    )

    # 存储用户数据
    users_db[user_data.email] = user_obj.dict()

    # 创建访问令牌
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_data.email}, expires_delta=access_token_expires
    )

    # 返回用户信息（不包含密码）
    user_response = UserInDB(
        user_id=user_obj.user_id,
        email=user_obj.email,
        username=user_obj.username,
        full_name=user_obj.full_name,
        disabled=user_obj.disabled,
        created_at=user_obj.created_at,
    )

    return Token(access_token=access_token, token_type="bearer", user=user_response)


# 用户登录接口
@app.post("/api/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    # 返回用户信息（不包含密码）
    user_response = UserInDB(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        disabled=user.disabled,
        created_at=user.created_at,
    )

    return Token(access_token=access_token, token_type="bearer", user=user_response)


# 简化的登录接口 - 支持邮箱和密码直接登录
@app.post("/api/login/email", response_model=Token)
async def login_with_email(user_data: UserLogin):
    user = authenticate_user(user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    # 返回用户信息（不包含密码）
    user_response = UserInDB(
        user_id=user.user_id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        disabled=user.disabled,
        created_at=user.created_at,
    )

    return Token(access_token=access_token, token_type="bearer", user=user_response)


# 获取当前用户信息
@app.get("/api/users/me", response_model=UserInDB)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return UserInDB(
        user_id=current_user.user_id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        disabled=current_user.disabled,
        created_at=current_user.created_at,
    )


# 用户登出接口 - 前端只需清除令牌
@app.post("/api/logout")
async def logout():
    # 实际上后端无需操作，前端只需删除本地存储的令牌
    # 如果需要实现令牌黑名单，可以在此处添加
    return {"message": "Successfully logged out"}


# 修改用户密码
@app.post("/api/users/change-password")
async def change_password(
    password_data: PasswordChange, current_user: User = Depends(get_current_active_user)
):
    # 验证当前密码
    if not verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
        )

    # 更新密码
    new_hashed_password = get_password_hash(password_data.new_password)
    users_db[current_user.email]["hashed_password"] = new_hashed_password

    return {"message": "Password updated successfully"}


# 预设几个测试用户
def initialize_test_users():
    """
    从.env文件中初始化测试用户。

    环境变量格式：
    TEST_USER_1=email:test@example.com,username:testuser,password:password123,full_name:Test User
    TEST_USER_2=email:admin@example.com,username:admin,password:admin123,full_name:Admin User

    可以添加多个用户，格式为 TEST_USER_n，其中n为数字。
    """
    from dotenv import load_dotenv
    import os
    import re

    # 加载.env文件
    load_dotenv(".env")

    # 查找所有TEST_USER_开头的环境变量
    test_user_pattern = re.compile(r"^TEST_USER_\d+$")
    test_user_vars = [var for var in os.environ.keys() if test_user_pattern.match(var)]
    logging.info(test_user_vars)

    if test_user_vars:
        # 从环境变量中解析用户信息
        test_users = []
        for var_name in test_user_vars:
            user_str = os.environ.get(var_name, "")
            if not user_str:
                continue

            # 解析用户信息，格式：email:xxx,username:xxx,password:xxx,full_name:xxx
            user_dict = {}
            for field in user_str.split(","):
                if ":" in field:
                    key, value = field.split(":", 1)
                    user_dict[key.strip()] = value.strip()

            # 确保必要字段存在
            if all(k in user_dict for k in ["email", "username", "password"]):
                test_users.append(user_dict)
    else:
        raise Exception("No user data")

    # 添加测试用户到数据库
    for user in test_users:
        if user["email"] not in users_db:
            hashed_password = get_password_hash(user["password"])
            users_db[user["email"]] = {
                "user_id": str(uuid.uuid4()),
                "email": user["email"],
                "username": user["username"],
                "hashed_password": hashed_password,
                "full_name": user.get("full_name", ""),
                "disabled": False,
                "created_at": datetime.datetime.now(tz=pytz.UTC).isoformat(" "),
            }


# 初始化测试用户
initialize_test_users()


# 添加一个认证中间件来保护指定的路径
class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            # 直接放行预检请求
            response = await call_next(request)
            return response
        # 定义需要保护的路径列表
        protected_paths = [
            "/api/runs/share",
            "/api/generate_swap_order",
            "/api/tradingview/symbol_search",
        ]

        # 检查是否是需要保护的线程路径
        if request.url.path.startswith("/threads/"):
            is_protected = True
        else:
            is_protected = request.url.path in protected_paths

        # 如果是受保护的路径，则验证用户登录状态
        if is_protected:
            authorization = request.headers.get("Authorization")
            logging.info("$" * 100)
            logging.info(request.url)
            logging.info(authorization)

            # 如果没有Authorization头，返回401未授权错误
            if not authorization:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Not authenticated"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 提取token
            try:
                scheme, token = authorization.split(" ")
                if scheme.lower() != "bearer":
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid authentication scheme"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                # 验证token
                try:
                    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                    email: str = payload.get("sub")
                    if email is None:
                        raise HTTPException(status_code=401, detail="Invalid token")

                    # 检查用户是否存在
                    user = get_user(email)
                    if user is None:
                        raise HTTPException(status_code=401, detail="User not found")

                    # 检查用户是否被禁用
                    if user.disabled:
                        raise HTTPException(status_code=401, detail="Inactive user")

                except JWTError:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid authentication credentials"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )

            except Exception:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid authentication format"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # 继续处理请求
        response = await call_next(request)
        return response


origins = [
    "*",  # 注意：生产环境不建议使用通配符
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://192.168.3.6:3000",
    "http://192.168.3.6:3001",
    "http://musse.ai",
    "https://musse.ai",
    "http://www.musse.ai",
    "https://www.musse.ai",
    "http://api.musse.ai",
    "https://api.musse.ai",
]
# 添加身份验证中间件 - 在CORS中间件之后添加，因为CORS中间件需要先处理preflight请求
app.add_middleware(AuthenticationMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
