from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    user_id: str
    wallet_is_connected: bool
    chain_id: int
    wallet_address: str


graph_builder = StateGraph(State)

from tools.tools_infura import tools
from tools.tools_agent_router import generate_routing_tools

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.utils.runnable import RunnableCallable


def format_messages(state: State) -> list[BaseMessage]:
    system_prompt = """You are a helpful blockchain assistant with access to Infura's blockchain data.
    Please provide accurate and helpful information about blockchain data.

    NETWORK_CONFIG:
	```python
    NETWORK_CONFIG = {{
	    	"ethereum": {{
	    	    "mainnet": {{
	    	        "chain_id": 1,
	    	        "name": "Ethereum Mainnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://etherscan.io",
	    	    }},
	    	    "goerli": {{
	    	        "chain_id": 5,
	    	        "name": "Goerli Testnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://goerli.etherscan.io",
	    	    }},
	    	    "sepolia": {{
	    	        "chain_id": 11155111,
	    	        "name": "Sepolia Testnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://sepolia.etherscan.io",
	    	    }},
	    	}},
	    	"polygon": {{
	    	    "mainnet": {{
	    	        "chain_id": 137,
	    	        "name": "Polygon Mainnet",
	    	        "symbol": "MATIC",
	    	        "explorer": "https://polygonscan.com",
	    	    }},
	    	    "mumbai": {{
	    	        "chain_id": 80001,
	    	        "name": "Mumbai Testnet",
	    	        "symbol": "MATIC",
	    	        "explorer": "https://mumbai.polygonscan.com",
	    	    }},
	    	}},
	    	"optimism": {{
	    	    "mainnet": {{
	    	        "chain_id": 10,
	    	        "name": "Optimism Mainnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://optimistic.etherscan.io",
	    	    }},
	    	    "goerli": {{
	    	        "chain_id": 420,
	    	        "name": "Optimism Goerli",
	    	        "symbol": "ETH",
	    	        "explorer": "https://goerli-optimism.etherscan.io",
	    	    }},
	    	}},
	    	"arbitrum": {{
	    	    "mainnet": {{
	    	        "chain_id": 42161,
	    	        "name": "Arbitrum One",
	    	        "symbol": "ETH",
	    	        "explorer": "https://arbiscan.io",
	    	    }},
	    	    "goerli": {{
	    	        "chain_id": 421613,
	    	        "name": "Arbitrum Goerli",
	    	        "symbol": "ETH",
	    	        "explorer": "https://goerli.arbiscan.io",
	    	    }},
	    	}},
	    	"avalanche": {{
	    	    "mainnet": {{
	    	        "chain_id": 43114,
	    	        "name": "Avalanche C-Chain",
	    	        "symbol": "AVAX",
	    	        "explorer": "https://snowtrace.io",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 43113,
	    	        "name": "Avalanche Fuji Testnet",
	    	        "symbol": "AVAX",
	    	        "explorer": "https://testnet.snowtrace.io",
	    	    }},
	    	}},
	    	"base": {{
	    	    "mainnet": {{
	    	        "chain_id": 8453,
	    	        "name": "Base Mainnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://basescan.org",
	    	    }},
	    	    "sepolia": {{
	    	        "chain_id": 84532,
	    	        "name": "Base Sepolia Testnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://sepolia.basescan.org",
	    	    }},
	    	}},
	    	"blast": {{
	    	    "mainnet": {{
	    	        "chain_id": 81457,
	    	        "name": "Blast Mainnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://blastscan.io",
	    	    }},
	    	}},
	    	"bsc": {{
	    	    "mainnet": {{
	    	        "chain_id": 56,
	    	        "name": "Binance Smart Chain",
	    	        "symbol": "BNB",
	    	        "explorer": "https://bscscan.com",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 97,
	    	        "name": "BSC Testnet",
	    	        "symbol": "BNB",
	    	        "explorer": "https://testnet.bscscan.com",
	    	    }},
	    	}},
	    	"celo": {{
	    	    "mainnet": {{
	    	        "chain_id": 42220,
	    	        "name": "Celo Mainnet",
	    	        "symbol": "CELO",
	    	        "explorer": "https://explorer.celo.org",
	    	    }},
	    	    "alfajores": {{
	    	        "chain_id": 44787,
	    	        "name": "Celo Alfajores Testnet",
	    	        "symbol": "CELO",
	    	        "explorer": "https://alfajores-blockscout.celo-testnet.org",
	    	    }},
	    	}},
	    	"linea": {{
	    	    "mainnet": {{
	    	        "chain_id": 59144,
	    	        "name": "Linea Mainnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://lineascan.build",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 59140,
	    	        "name": "Linea Goerli Testnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://goerli.lineascan.build",
	    	    }},
	    	}},
	    	"mantle": {{
	    	    "mainnet": {{
	    	        "chain_id": 5000,
	    	        "name": "Mantle Mainnet",
	    	        "symbol": "MNT",
	    	        "explorer": "https://explorer.mantle.xyz",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 5001,
	    	        "name": "Mantle Testnet",
	    	        "symbol": "MNT",
	    	        "explorer": "https://explorer.testnet.mantle.xyz",
	    	    }},
	    	}},
	    	"opbnb": {{
	    	    "mainnet": {{
	    	        "chain_id": 204,
	    	        "name": "opBNB Mainnet",
	    	        "symbol": "BNB",
	    	        "explorer": "https://opbnbscan.com",
	    	    }},
	    	}},
	    	"palm": {{
	    	    "mainnet": {{
	    	        "chain_id": 11297108109,
	    	        "name": "Palm Mainnet",
	    	        "symbol": "PALM",
	    	        "explorer": "https://explorer.palm.io",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 11297108099,
	    	        "name": "Palm Testnet",
	    	        "symbol": "PALM",
	    	        "explorer": "https://testnet.explorer.palm.io",
	    	    }},
	    	}},
	    	"polygon_pos": {{
	    	    "mainnet": {{
	    	        "chain_id": 137,
	    	        "name": "Polygon POS Mainnet",
	    	        "symbol": "MATIC",
	    	        "explorer": "https://polygonscan.com",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 80001,
	    	        "name": "Mumbai Testnet",
	    	        "symbol": "MATIC",
	    	        "explorer": "https://mumbai.polygonscan.com",
	    	    }},
	    	}},
	    	"scroll": {{
	    	    "mainnet": {{
	    	        "chain_id": 534352,
	    	        "name": "Scroll Mainnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://scrollscan.com",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 534351,
	    	        "name": "Scroll Sepolia Testnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://sepolia.scrollscan.com",
	    	    }},
	    	}},
	    	"starknet": {{
	    	    "mainnet": {{
	    	        "chain_id": 9,
	    	        "name": "StarkNet Mainnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://voyager.online",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 1,
	    	        "name": "StarkNet Goerli Testnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://goerli.voyager.online",
	    	    }},
	    	}},
	    	"swellchain": {{
	    	    "mainnet": {{
	    	        "chain_id": 30000,
	    	        "name": "Swell Chain Mainnet",
	    	        "symbol": "SWELL",
	    	        "explorer": "https://explorer.swellchain.io",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 30001,
	    	        "name": "Swell Chain Testnet",
	    	        "symbol": "SWELL",
	    	        "explorer": "https://testnet.explorer.swellchain.io",
	    	    }},
	    	}},
	    	"unichain": {{
	    	    "mainnet": {{
	    	        "chain_id": 29,
	    	        "name": "UniChain Mainnet",
	    	        "symbol": "UNI",
	    	        "explorer": "https://explorer.unichain.network",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 30,
	    	        "name": "UniChain Testnet",
	    	        "symbol": "UNI",
	    	        "explorer": "https://testnet.explorer.unichain.network",
	    	    }},
	    	}},
	    	"zksync": {{
	    	    "mainnet": {{
	    	        "chain_id": 324,
	    	        "name": "ZKsync Era Mainnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://explorer.zksync.io",
	    	    }},
	    	    "testnet": {{
	    	        "chain_id": 280,
	    	        "name": "ZKsync Era Testnet",
	    	        "symbol": "ETH",
	    	        "explorer": "https://goerli.explorer.zksync.io",
	    	    }},
	    	}}
	}}
    ```
    """
    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages()
    return system_message + state["messages"]


def call_model_infura(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    response = cast(
        AIMessage, llm_with_tools.invoke(format_messages(state=state), config)
    )

    return {"messages": [response]}


async def acall_model_infura(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    response = cast(
        AIMessage, await llm_with_tools.ainvoke(format_messages(state), config)
    )

    return {"messages": [response]}


from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools + generate_routing_tools(), name="node_tools_infura")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(
    call_model_infura, acall_model_infura, name="node_llm_infura"
)
graph_builder.add_node(node_llm.get_name(), node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)
graph_builder.add_edge(tool_node.get_name(), node_llm.get_name())
graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = "graph_infura"
