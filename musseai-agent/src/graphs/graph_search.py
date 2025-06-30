import json
import logging
from typing import Annotated, List, Literal, cast
from agent_config import ROUTE_MAPPING, tools_condition
from typing_extensions import TypedDict
from langgraph.types import Command

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.utils.runnable import RunnableCallable

from langchain_core.messages import HumanMessage
from langchain_core.documents import Document
from langchain_community.document_loaders import SpiderLoader
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_text_splitters import RecursiveCharacterTextSplitter
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import os
from loggers import logger

GRAPH_NAME = "graph_search"

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


graph_builder = StateGraph(State)

from tools.tools_search import (
    tools,
    search_webpage,
    search_news,
    access_links_content,
)
from tools.tools_agent_router import generate_routing_tools

from langchain_core.prompts import SystemMessagePromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.utils.runnable import RunnableCallable

from langchain_community.document_transformers import Html2TextTransformer


from prompts.prompt_search import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)

from langgraph.types import Command, Send


def call_model(state: State, config: RunnableConfig) -> State | Command:
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    system_message = system_template.format_messages()
    response = cast(
        AIMessage, llm_with_tools.invoke(system_message + state["messages"], config)
    )

    return {"messages": [response]}


async def acall_model(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools + generate_routing_tools())
    system_message = system_template.format_messages()
    response = cast(
        AIMessage,
        await llm_with_tools.ainvoke(system_message + state["messages"], config),
    )
    return {"messages": [response]}


class LinksContentState:
    links_content: list[dict]


message_id_map = {}


def edge_get_links_read_content(
    state: State,
):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and (
        last_message.name == search_webpage.get_name()
        or last_message.name == search_news.get_name()
        or last_message.name == access_links_content.get_name()
    ):
        content = json.loads(last_message.content)
        search_result = content["search_result"]
        links = [
            {"link": sr["link"], "message_id": last_message.id} for sr in search_result
        ]
        return [
            Send(
                node_read_content.__name__,
                link,
            )
            for link in links
        ]
    else:
        return node_llm.get_name()


class LinkRelaventContentState:
    link: str
    question: str
    message_id: str


KEY_LINK_RELAVENT_CONTENT = "link_relavent_content"
KEY_LINK_CONTENT_SPLITS = "link_content_splits"

driver_path = os.getenv("CHROME_DRIVER_PATH")
service = Service(executable_path=driver_path)
# 创建ChromeOptions对象
chrome_options = Options()
# 添加无头模式参数
chrome_options.add_argument("--headless")


import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from loggers import logger


def getHTMLChrome(url: str) -> str:
    """useful when you need get the HTML of URL asynchronously. The input to this should be URL."""
    logger.info(f"Access url use Chrome. {url}")

    # 容器环境下的Chrome选项配置
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--disable-javascript")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    )

    driver_path = os.getenv("CHROME_DRIVER_PATH", "/chromedriver-linux64/chromedriver")
    service = Service(executable_path=driver_path)

    browser = webdriver.Chrome(service=service, options=chrome_options)
    try:
        # Get the web page content
        browser.get(url=url)

        # Wait for page to load completely (with timeout)
        try:
            WebDriverWait(browser, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logger.warning(f"Page load timeout for URL: {url}")

        html_content = browser.page_source
        soup = BeautifulSoup(html_content, "html.parser")
        body = soup.find("body")

        if not body:
            logger.warning(f"No body tag found in the HTML from URL: {url}")
            return html_content

        # Remove unwanted tags
        for tag in body.find_all(
            [
                "link",
                "script",
                "style",
                "button",
                "input",
                "meta",
                "iframe",
                "img",
                "noscript",
                "svg",
            ]
        ):
            tag.decompose()

        # Clean up attributes
        for tag in body.findAll(True):
            tag.attrs = {
                key: value
                for key, value in tag.attrs.items()
                if key not in ["class", "style"]
            }

        # Clean whitespace
        clean_html = re.sub(r"(?m)^[\t ]+$", "", str(body))
        return clean_html
    except Exception as e:
        logger.error(f"Error fetching HTML from {url}: {str(e)}")
        return ""
    finally:
        browser.quit()


from langchain_community.document_loaders import WebBaseLoader


async def getDocumentFromLink(
    link: str, chunk_size: int, chunk_overlap: int
) -> List[Document]:
    """get documents from link."""
    html = []
    # try:
    #     clean_html = await asyncio.to_thread(getHTMLChrome, link)
    #     html = [Document(page_content=clean_html)]
    # except Exception as e:
    #     logger.error(f"Error loading {link}: {e}")
    try:
        loader = SpiderLoader(
            url=link,
            mode="scrape",  # if no API key is provided it looks for SPIDER_API_KEY in env
        )
        docs = await loader.aload()
        html += docs
    except Exception as e:
        logger.warning(e)
        loader = WebBaseLoader(web_paths=[link])
        html = await asyncio.to_thread(loader.load)
    #     async for doc in loader.alazy_load():
    #         html.append(doc)

    def split_documents(html):
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        ).split_documents(html)

    return await asyncio.to_thread(split_documents, html)
    # 使用线程池执行同步文本分割操作，避免阻塞事件循环
    # with ThreadPoolExecutor() as executor:
    #     _split = await asyncio.get_event_loop().run_in_executor(
    #         executor,
    #         lambda: RecursiveCharacterTextSplitter(
    #             chunk_size=chunk_size, chunk_overlap=chunk_overlap
    #         ).split_documents(html),
    #     )


async def node_read_content(state: LinkRelaventContentState):
    splits = await getDocumentFromLink(
        state["link"], chunk_size=5000, chunk_overlap=1500
    )
    if state["message_id"] not in message_id_map:
        message_id_map[state["message_id"]] = {}
        message_id_map[state["message_id"]][KEY_LINK_CONTENT_SPLITS] = []
    else:
        message_id_map[state["message_id"]][KEY_LINK_CONTENT_SPLITS] += splits


def node_read_content_reduce(state: State):
    return state


def edge_read_content_extract_relevant_content(state: State):
    last_message = state["messages"][-1]
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            last_human_message = message
    question = last_human_message.content
    splits = message_id_map[last_message.id][KEY_LINK_CONTENT_SPLITS]
    return [
        Send(
            "node_extranct_relevant_content",
            {
                "content": [s.page_content],
                "question": question,
                "message_id": last_message.id,
            },
        )
        for s in splits
    ]


class ContentInLink:
    content: str
    message_id: str
    question: str


async def node_extranct_relevant_content(state: ContentInLink):
    prompt_template = """Extract as much relevant content about the question as possible from the context below.

Question:{question}

Context:
```plaintext
{text}
```
"""
    template = ChatPromptTemplate.from_template(prompt_template)
    messages = template.format_messages(
        question=state["question"], text=state["content"]
    )
    contents = []

    # loader = AsyncChromiumLoader(links)
    # html = loader.load()
    _extract_llm = ChatAnthropic(
        model="claude-3-5-haiku-latest",
        temperature=0.7,
        max_tokens=150,
    )
    contents = await _extract_llm.ainvoke(messages)
    relevant_content = (
        "The contents of the first three search results are extracted as follows:\n"
        + contents.content
    )

    if state["message_id"] not in message_id_map:
        message_id_map[state["message_id"]] = {}
        message_id_map[state["message_id"]][
            KEY_LINK_RELAVENT_CONTENT
        ] = relevant_content
    else:
        if KEY_LINK_RELAVENT_CONTENT not in message_id_map[state["message_id"]]:
            message_id_map[state["message_id"]][
                KEY_LINK_RELAVENT_CONTENT
            ] = relevant_content
        else:
            message_id_map[state["message_id"]][
                KEY_LINK_RELAVENT_CONTENT
            ] += relevant_content


def node_relevant_reduce(state: State):
    last_message = state["messages"][-1]
    last_message = cast(ToolMessage, last_message)
    content = json.loads(last_message.content)
    relevant_content = message_id_map[last_message.id][KEY_LINK_RELAVENT_CONTENT]
    content["content_from_search_result"] = relevant_content
    last_message.content = json.dumps(content)
    state["messages"][-1] = last_message
    message_id_map.pop(last_message.id)
    return state


node_llm = RunnableCallable(call_model, acall_model, name="node_llm_search")

graph_builder.add_node(node_llm)

from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools=tools + generate_routing_tools(), name="node_tools_search")
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_node(node_read_content.__name__, node_read_content)
graph_builder.add_node(node_read_content_reduce.__name__, node_read_content_reduce)
graph_builder.add_node(
    node_extranct_relevant_content.__name__, node_extranct_relevant_content
)
# graph_builder.add_node("node_get_link", node_get_link)
graph_builder.add_node(node_relevant_reduce.__name__, node_relevant_reduce)

graph_builder.add_edge(START, node_llm.get_name())
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)


def node_router(state: State):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.name in ROUTE_MAPPING:
        logger.info(f"Node:{GRAPH_NAME}, Need to route to other node, cause graph end.")
        return Command(goto=END, update=state)
    else:
        return Command(goto=node_start_read_link.__name__, update=state)


def node_start_read_link(state: State):
    return state


graph_builder.add_node(node_start_read_link)
graph_builder.add_node(node_router)
graph_builder.add_edge(tool_node.get_name(), node_router.__name__)
graph_builder.add_conditional_edges(
    node_start_read_link.__name__,
    edge_get_links_read_content,
    {
        node_llm.get_name(): node_llm.get_name(),
        node_read_content.__name__: node_read_content.__name__,
    },
)
graph_builder.add_edge(node_read_content.__name__, node_read_content_reduce.__name__)
graph_builder.add_conditional_edges(
    node_read_content_reduce.__name__,
    edge_read_content_extract_relevant_content,
    [node_extranct_relevant_content.__name__],
)
graph_builder.add_edge(
    node_extranct_relevant_content.__name__, node_relevant_reduce.__name__
)
graph_builder.add_edge(node_relevant_reduce.__name__, node_llm.get_name())
graph = graph_builder.compile()
graph.name = GRAPH_NAME
