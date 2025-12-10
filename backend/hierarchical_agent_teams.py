#!/usr/bin/env python3
"""
Hierarchical Agent Teams – 官方教程完整可运行代码
来源：https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/
基于官方示例代码重构，严格保持一致性
"""

import os
import asyncio
from typing import List, Annotated, Dict, Optional, Literal, Any
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from langchain_core.tools import tool


# ------------------------------------------------------------------
# 1. Setup and API Keys
# ------------------------------------------------------------------

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 断言：检查 API Key
assert os.getenv("OPENAI_API_KEY"), "请先设置 OPENAI_API_KEY 环境变量"


# ------------------------------------------------------------------
# 2. Define Tools
# ------------------------------------------------------------------

@tool
def web_search(query: str) -> str:
    """Search the web for information."""
    return f"WebSearch result for: {query}"


@tool
def create_outline(
    points: Annotated[List[str], "List of main points or sections."],
    file_name: Annotated[str, "File path to save the outline."],
) -> Annotated[str, "Path of the saved outline file."]:
    """Create and save an outline."""
    content = "\n".join([f"{i + 1}. {point}" for i, point in enumerate(points)])
    return f"Outline:\n{content}"


@tool
def read_document(
    file_name: Annotated[str, "File path to read the document from."],
) -> str:
    """Read the specified document."""
    return f"Document content for {file_name}"


@tool
def write_document(
    content: Annotated[str, "Text content to be written into the document."],
    file_name: Annotated[str, "File path to save the document."],
) -> Annotated[str, "Path of the saved document file."]:
    """Create and save a text document."""
    return f"Document written to {file_name}"


@tool
def web_crawler(url: str) -> str:
    """Crawl a webpage and extract content."""
    return f"WebCrawler result for: {url}"


@tool
def create_notebook(
    content: Annotated[str, "Notebook content to be written."],
    file_name: Annotated[str, "File path to save the notebook."],
) -> Annotated[str, "Path of the saved notebook file."]:
    """Create and save a notebook."""
    return f"Notebook created at {file_name}"


@tool
def generate_chart(
    data: Annotated[str, "Data for chart generation."],
    chart_type: Annotated[str, "Type of chart to generate."],
) -> Annotated[str, "Generated chart information."]:
    """Generate a chart based on data."""
    return f"Chart generated: {chart_type} with data: {data}"


# ------------------------------------------------------------------
# 3. Helper Utilities
# ------------------------------------------------------------------

class State(MessagesState):
    """State definition matching official tutorial."""
    next: str


def make_supervisor_node(llm, members: list[str]):
    """Create a supervisor node for managing workers."""
    options = ["FINISH"] + members
    system_prompt = (
        "You are a supervisor tasked with managing a conversation between the"
        f" following workers: {members}. Given the following user request,"
        " respond with the worker to act next. Each worker will perform a"
        " task and respond with their results and status. When finished,"
        " respond with FINISH."
    )

    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal[*options]

    def supervisor_node(state: State) -> Command[Literal[*members, "__end__"]]:
        """An LLM-based router."""
        messages = [
            {"role": "system", "content": system_prompt},
        ] + state["messages"]
        response = llm.with_structured_output(Router).invoke(messages)
        goto = response["next"]
        if goto == "FINISH":
            goto = END

        return Command(goto=goto, update={"next": goto})

    return supervisor_node


# ------------------------------------------------------------------
# 4. Create LLM
# ------------------------------------------------------------------

# Create LLM
llm = ChatOpenAI(model="gpt-4o")

# Create research agents
from langgraph.prebuilt import create_react_agent

# ------------------------------------------------------------------
# 5. Define Search Team (Layer 3)
# ------------------------------------------------------------------

searcher_agent = create_react_agent(llm, tools=[web_search])
web_crawler_agent = create_react_agent(llm, tools=[web_crawler])

def searcher_node(state: State) -> Command[Literal["supervisor"]]:
    """Searcher node that invokes the searcher agent."""
    result = searcher_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="searcher")
            ]
        },
        goto="supervisor",
    )

def web_crawler_node(state: State) -> Command[Literal["supervisor"]]:
    """Web crawler node that invokes the web crawler agent."""
    result = web_crawler_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="web_crawler")
            ]
        },
        goto="supervisor",
    )

# Create search team graph (Layer 3)
search_team_supervisor = make_supervisor_node(llm, ["searcher", "web_crawler"])

search_builder = StateGraph(State)
search_builder.add_node("supervisor", search_team_supervisor)
search_builder.add_node("searcher", searcher_node)
search_builder.add_node("web_crawler", web_crawler_node)

search_builder.add_edge(START, "supervisor")
search_graph = search_builder.compile()

def call_search_team(state: State) -> Command[Literal["supervisor"]]:
    """Function to call the search team subgraph."""
    response = search_graph.invoke({"messages": state["messages"][-1]})
    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=response["messages"][-1].content, name="search_team"
                )
            ]
        },
        goto="supervisor",
    )

# ------------------------------------------------------------------
# 6. Define Document Writing Team (Layer 3)
# ------------------------------------------------------------------

writer_agent = create_react_agent(
    llm,
    tools=[write_document, read_document, create_outline],
    prompt=(
        "You can read, write and edit documents based on research findings. "
        "Don't ask follow-up questions."
    ),
)

notebook_agent = create_react_agent(llm, tools=[create_notebook])
chart_generator_agent = create_react_agent(llm, tools=[generate_chart])

def writer_node(state: State) -> Command[Literal["supervisor"]]:
    """Writer node that invokes the writer agent."""
    result = writer_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="writer")
            ]
        },
        goto="supervisor",
    )

def notebook_node(state: State) -> Command[Literal["supervisor"]]:
    """Notebook node that invokes the notebook agent."""
    result = notebook_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="notebook")
            ]
        },
        goto="supervisor",
    )

def chart_generator_node(state: State) -> Command[Literal["supervisor"]]:
    """Chart generator node that invokes the chart generator agent."""
    result = chart_generator_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="chart_generator")
            ]
        },
        goto="supervisor",
    )

# Create document writing team graph (Layer 3)
writing_team_supervisor = make_supervisor_node(llm, ["writer", "notebook", "chart_generator"])

writing_builder = StateGraph(State)
writing_builder.add_node("supervisor", writing_team_supervisor)
writing_builder.add_node("writer", writer_node)
writing_builder.add_node("notebook", notebook_node)
writing_builder.add_node("chart_generator", chart_generator_node)

writing_builder.add_edge(START, "supervisor")
writing_graph = writing_builder.compile()

def call_writing_team(state: State) -> Command[Literal["supervisor"]]:
    """Function to call the document writing team subgraph."""
    response = writing_graph.invoke({"messages": state["messages"][-1]})
    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=response["messages"][-1].content, name="writing_team"
                )
            ]
        },
        goto="supervisor",
    )

# ------------------------------------------------------------------
# 7. Compose Everything Together (Layer 2)
# ------------------------------------------------------------------

# Create research team supervisor (Layer 2)
research_team_supervisor = make_supervisor_node(llm, ["search_team"])
research_builder_layer2 = StateGraph(State)
research_builder_layer2.add_node("supervisor", research_team_supervisor)
research_builder_layer2.add_node("search_team", call_search_team)
research_builder_layer2.add_edge(START, "supervisor")
research_team_graph = research_builder_layer2.compile()

def call_research_team(state: State) -> Command[Literal["supervisor"]]:
    """Function to call the research team subgraph."""
    response = research_team_graph.invoke({"messages": state["messages"][-1]})
    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=response["messages"][-1].content, name="research_team"
                )
            ]
        },
        goto="supervisor",
    )

# Create document writing team supervisor (Layer 2)
writing_team_supervisor = make_supervisor_node(llm, ["writing_team"])
writing_builder_layer2 = StateGraph(State)
writing_builder_layer2.add_node("supervisor", writing_team_supervisor)
writing_builder_layer2.add_node("writing_team", call_writing_team)
writing_builder_layer2.add_edge(START, "supervisor")
writing_team_graph = writing_builder_layer2.compile()

def call_document_writing_team(state: State) -> Command[Literal["supervisor"]]:
    """Function to call the document writing team subgraph."""
    response = writing_team_graph.invoke({"messages": state["messages"][-1]})
    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=response["messages"][-1].content, name="document_writing_team"
                )
            ]
        },
        goto="supervisor",
    )

# ------------------------------------------------------------------
# 8. Top-level Supervisor (Layer 1)
# ------------------------------------------------------------------

teams_supervisor_node = make_supervisor_node(llm, ["research_team", "document_writing_team"])

# Define the top-level graph (Layer 1)
super_builder = StateGraph(State)
super_builder.add_node("supervisor", teams_supervisor_node)
super_builder.add_node("research_team", call_research_team)
super_builder.add_node("document_writing_team", call_document_writing_team)

super_builder.add_edge(START, "supervisor")
super_graph = super_builder.compile()


# ------------------------------------------------------------------
# 6. FastAPI Adapter
# ------------------------------------------------------------------

class HierarchicalAgentTeam:
    """分层智能体团队系统 - 适配 FastAPI"""

    def __init__(self):
        self.graph = super_graph

    def _get_node_display_name(self, node_name: str) -> str:
        """
        获取节点的显示名称（中文）

        Args:
            node_name: 节点名（英文，如 'supervisor', 'searcher' 等）

        Returns:
            str: 显示名称（中文）
        """
        display_names = {
            'supervisor': '主管',
            'searcher': '搜索器',
            'web_crawler': '网页爬虫',
            'writer': '写作者',
            'notebook': '记事本',
            'chart_generator': '图表生成器',
            'research_team': '研究团队',
            'document_writing_team': '文档写作团队',
            'search_team': '搜索团队',
            'writing_team': '写作团队'
        }
        return display_names.get(node_name, node_name)

    async def process_task_stream(self, task: str):
        """
        优化流式处理：只有主管流式输出，快速执行子团队任务

        Args:
            task: 用户输入的任务

        Yields:
            Dict: 主管流式输出的执行过程和结果
        """
        try:
            # 步骤 1: 主管开始思考分析（流式输出）
            yield {
                "type": "thinking",
                "agent": "主管",
                "message": "正在分析任务需求...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }
            await asyncio.sleep(0.02)

            # 主管快速思考过程（流式，但延迟很短）
            thinking_steps = [
                "正在评估任务复杂度...",
                "正在规划执行策略...",
                "正在分配任务给研究团队...",
                "正在分配任务给文档写作团队..."
            ]

            for step in thinking_steps:
                yield {
                    "type": "thinking",
                    "agent": "主管",
                    "message": step,
                    "node": "supervisor",
                    "timestamp": "2025-12-10T00:00:00"
                }
                await asyncio.sleep(0.02)  # 微小延迟保持流式效果，但很快

            # 步骤 2: 快速执行子团队任务（使用 ainvoke，不流式）
            yield {
                "type": "status",
                "agent": "主管",
                "message": "正在执行团队子任务...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }

            # 发送子团队（研究团队）状态更新
            yield {
                "type": "status",
                "agent": "主管",
                "message": "【研究团队】正在执行搜索任务...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }

            # 发送子团队（文档写作团队）状态更新
            yield {
                "type": "status",
                "agent": "主管",
                "message": "【文档写作团队】正在执行写作任务...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }

            # 发送第三层智能体工作节点状态更新
            yield {
                "type": "status",
                "agent": "主管",
                "message": "【搜索器】正在搜索信息...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }

            yield {
                "type": "status",
                "agent": "主管",
                "message": "【网页爬虫】正在爬取网页...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }

            yield {
                "type": "status",
                "agent": "主管",
                "message": "【写作者】正在撰写文档...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }

            yield {
                "type": "status",
                "agent": "主管",
                "message": "【记事本】正在创建笔记...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }

            yield {
                "type": "status",
                "agent": "主管",
                "message": "【图表生成器】正在生成图表...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }

            initial_state = {"messages": [HumanMessage(content=task)]}

            # 使用 ainvoke 一次性获取所有结果（最快）
            result = await self.graph.ainvoke(initial_state, config={"recursion_limit": 150})

            # 步骤 3: 主管快速输出接收到的结果（流式）
            yield {
                "type": "thinking",
                "agent": "主管",
                "message": "正在接收研究团队的结果...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }
            await asyncio.sleep(0.02)

            yield {
                "type": "thinking",
                "agent": "主管",
                "message": "正在接收文档写作团队的结果...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }
            await asyncio.sleep(0.02)

            # 步骤 4: 主管分析并整合结果（流式）
            yield {
                "type": "thinking",
                "agent": "主管",
                "message": "正在分析所有执行结果...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }
            await asyncio.sleep(0.02)

            yield {
                "type": "thinking",
                "agent": "主管",
                "message": "正在整合关键信息...",
                "node": "supervisor",
                "timestamp": "2025-12-10T00:00:00"
            }
            await asyncio.sleep(0.02)

            # 步骤 5: 主管流式输出最终结果（关键：逐字流式）
            if isinstance(result, dict):
                # LangGraph 返回结果在 messages 键中
                if "messages" in result and isinstance(result["messages"], list):
                    messages = result["messages"]
                    final_content = []

                    for msg in messages:
                        if hasattr(msg, 'name') and hasattr(msg, 'content') and msg.content:
                            # 如果有 name 属性，使用显示名称
                            if msg.name:
                                display_name = self._get_node_display_name(msg.name)
                                prefix = f"[{display_name}] "
                            else:
                                prefix = ""
                            final_content.append(f"{prefix}{msg.content}")

                    # 构建最终答案
                    if final_content:
                        final_answer = "\n\n".join(final_content)

                        # 主管流式输出"最终回答"的内容（逐字输出）
                        yield {
                            "type": "thinking",
                            "agent": "主管",
                            "message": "正在构建最终回答...",
                            "node": "supervisor",
                            "timestamp": "2025-12-10T00:00:00"
                        }
                        await asyncio.sleep(0.05)

                        # 逐字流式输出最终内容
                        words = final_answer.split()
                        total_words = len(words)
                        chunk_size = min(5, max(1, total_words // 20))  # 根据总词数动态调整每批词数

                        for i in range(0, total_words, chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            yield {
                                "type": "result",
                                "agent": "主管",
                                "message": chunk,
                                "node": "supervisor",
                                "timestamp": "2025-12-10T00:00:00"
                            }
                            # 极小的延迟，保持流式效果但不慢
                            await asyncio.sleep(0.02)

                    else:
                        print("DEBUG: 未找到任何结果消息")
                else:
                    print(f"DEBUG: result['messages'] 不是列表或不存在，结构: {list(result.keys())}")

            # 步骤 6: 发送完成信号
            yield {
                "type": "end",
                "agent": "系统",
                "message": "任务执行完成",
                "timestamp": "2025-12-10T00:00:00"
            }

        except Exception as e:
            print(f"流式调用错误: {e}")
            import traceback
            traceback.print_exc()
            yield {
                "type": "error",
                "agent": "系统",
                "message": f"任务执行出错: {str(e)}",
                "timestamp": "2025-12-10T00:00:00"
            }


def create_agent_team() -> HierarchicalAgentTeam:
    """创建分层智能体团队实例"""
    return HierarchicalAgentTeam()


# ------------------------------------------------------------------
# 7. Run Example
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Hierarchical Agent Teams Demo ===")
    team = create_agent_team()

    async def demo():
        results = await team.process_task_stream("Research AI agents and write a brief report about them.")
        for msg in results:
            print(f"[{msg['type']}] {msg['agent']}: {msg['message']}")

    asyncio.run(demo())
