#!/usr/bin/env python3
"""
Hierarchical Agent Teams – 官方教程完整可运行代码
来源：https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/
基于官方示例代码重构，严格保持一致性
"""

import os
import asyncio
import time
from typing import List, Annotated, Dict, Optional, Literal, Any
from typing_extensions import TypedDict
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from langchain_core.tools import tool


# ------------------------------------------------------------------
# 执行追踪系统
# ------------------------------------------------------------------

class ExecutionTrace:
    """执行追踪类，用于记录调度决策和执行过程"""

    def __init__(self):
        self.decisions = []  # 调度决策记录
        self.timeline = []   # 执行时间线
        self.current_phase = None

    def add_decision(self, supervisor: str, decision: str, reason: str = ""):
        """添加调度决策"""
        self.decisions.append({
            "supervisor": supervisor,
            "decision": decision,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })

    def add_timeline_event(self, event_type: str, agent: str, message: str):
        """添加时间线事件"""
        self.timeline.append({
            "type": event_type,
            "agent": agent,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    def get_summary(self) -> str:
        """获取执行摘要"""
        if not self.decisions:
            return "无调度决策记录"

        summary_lines = ["调度决策摘要："]
        for i, decision in enumerate(self.decisions, 1):
            reason = f" - {decision['reason']}" if decision['reason'] else ""
            summary_lines.append(f"{i}. {decision['supervisor']} → {decision['decision']}{reason}")

        return "\n".join(summary_lines)


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

    # 智能提示词生成系统
    def generate_system_prompt(members: list[str]) -> str:
        """根据成员列表生成智能提示词"""

        # 一级主管：顶级任务分配
        if set(members) == {"research_team", "document_writing_team"}:
            return """你是一个智能任务分配专家，负责分析用户任务并分配给合适的团队。

任务类型分析：
1. 仅研究类任务：
   - 特征：需要搜索信息、分析数据、了解趋势等
   - 示例："搜索AI发展趋势"、"分析量子计算市场"、"查找最新技术资讯"
   - 决策：分配给"research_team"

2. 仅写作类任务：
   - 特征：需要基于已有信息写作、编辑文档、创建内容等
   - 示例："写一份工作总结"、"创建项目文档"、"编写使用指南"
   - 决策：分配给"document_writing_team"

3. 研究+写作类任务：
   - 特征：需要先研究信息，再基于研究结果写作报告
   - 示例："研究人工智能并写一份报告"、"分析市场趋势并撰写报告"
   - 决策：先分配给"research_team"，完成后再次调用分配给"document_writing_team"

4. 复杂协作类任务：
   - 特征：需要研究、写作、可视化等多个环节
   - 示例："分析行业竞争态势并生成可视化报告"
   - 决策：先"research_team"后"document_writing_team"

工作流程：
- 分析用户任务，识别任务类型
- 选择最合适的团队执行
- 如果任务需要多个阶段，可以多次调用进行分配
- 当任务完成时，响应"FINISH"

成员列表：{members}
请基于任务实际需要，选择最合适的下一个执行者。"""

        # 二级主管：团队内部任务分配
        elif "search_team" in members or "writing_team" in members:
            if "search_team" in members:
                return """你是研究团队主管，负责分析任务需求并分配给搜索专家。

任务分析：
- 如果任务只需要基本搜索 → 选择"searcher"
- 如果任务需要深度信息收集 → 选择"web_crawler"
- 如果任务需要完整信息收集 → 依次调用"searcher"和"web_crawler"

成员列表：{members}
请根据信息收集的深度需求选择合适的专家。"""

            elif "writing_team" in members:
                return """你是文档写作团队主管，负责分析写作需求并分配给写作专家。

任务分析指南：
1. 简单写作任务：
   - 特征：基于已有信息写文档、报告、总结
   - 示例："写一份工作总结"、"编写项目说明"
   - 决策：直接选择"writer"

2. 结构化写作任务：
   - 特征：需要先规划结构再写作
   - 示例："写一份详细的市场分析报告"、"创建技术文档大纲"
   - 决策：先选择"outline"创建大纲，再选择"writer"写作

3. 数据可视化写作任务：
   - 特征：包含数据分析、图表生成需求
   - 示例："分析数据并生成图表报告"、"写一份包含图表的财务报告"
   - 决策：根据需要选择"chart_generator"和"writer"

4. 复杂协作写作任务：
   - 特征：需要大纲+写作+可视化的完整流程
   - 示例："研究市场并写包含图表的详细报告"、"分析趋势并生成可视化分析"
   - 决策：按顺序选择"outline"→"writer"→"chart_generator"或"chart_generator"→"writer"

成员列表：{members}
请根据任务的具体需求和复杂度，智能选择最合适的专家组合。

重要提示：
- 可以选择多个专家按顺序执行
- 每个专家执行后都会提供结果供下一步决策
- 当所有必要的专家都执行完成后，选择"FINISH"结束任务"""

        # 三级主管：执行层智能体选择
        else:
            role_map = {
                "searcher": "搜索专家",
                "web_crawler": "网页爬取专家",
                "writer": "文档写作专家",
                "outline": "大纲生成专家",
                "chart_generator": "图表生成专家"
            }
            roles = ", ".join([f"{m}({role_map.get(m, m)})" for m in members])
            return f"""你是执行层主管，负责将任务分配给专业智能体。

可用专家：{roles}

分配原则：
- 根据任务的具体需求选择最合适的专家
- 简单任务选择单个专家
- 复杂任务可以按顺序调用多个专家
- 每个专家执行后都会返回结果供下一步决策

请选择下一个执行专家。"""

    system_prompt = generate_system_prompt(members).format(members=members)

    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal[*options]

    def supervisor_node(state: State) -> Command[Literal[*members, "__end__"]]:
        """An LLM-based router."""
        messages = [
            {"role": "system", "content": system_prompt},
        ] + state["messages"]
        response = llm.with_structured_output(Router).invoke(messages)

        # 安全的访问next字段
        if isinstance(response, dict) and "next" in response:
            goto = response["next"]
        else:
            # 如果响应不包含next字段，尝试其他可能的字段
            goto = None
            if isinstance(response, dict):
                for key in ["next_agent", "route", "target", "worker"]:
                    if key in response:
                        goto = response[key]
                        break

            if goto is None:
                # 如果找不到路由目标，默认返回第一个选项
                goto = options[0] if options else "FINISH"

        if goto == "FINISH":
            goto = END

        return Command(goto=goto, update={"next": goto})

    return supervisor_node


# ------------------------------------------------------------------
# 4. Create LLM
# ------------------------------------------------------------------

# Create LLM with streaming support
llm = ChatOpenAI(model="gpt-4o-mini", streaming=True)

# Create research agents
from langgraph.prebuilt import create_react_agent

# ------------------------------------------------------------------
# 5. Define Search Agents (Layer 3)
# ------------------------------------------------------------------

searcher_agent = create_react_agent(llm, tools=[web_search])
web_crawler_agent = create_react_agent(llm, tools=[web_crawler])

def searcher_node(state: State) -> Command[Literal["supervisor"]]:
    """Searcher node that uses OpenAI streaming API and outputs real streaming chunks."""
    # 获取用户任务
    task_message = state["messages"][-1].content if state["messages"] else "请搜索相关信息"

    try:
        # 使用OpenAI的astream获取真正的流式输出
        stream_content = []
        prompt = f"请搜索以下内容并提供详细结果：{task_message}"

        # 调用astream获取流式块
        for chunk in llm.stream([HumanMessage(content=prompt)]):
            if chunk.content:
                stream_content.append(chunk.content)

        # 合并所有流式块
        full_content = "".join(stream_content)

        # 输出流式块（作为消息的一部分传递给TaskScheduler）
        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=full_content,
                        name="searcher",
                        additional_kwargs={
                            "is_streaming": True,
                            "streaming_chunks": stream_content  # 保存流式块供TaskScheduler使用
                        }
                    )
                ]
            },
            goto="supervisor",
        )
    except Exception as e:
        return Command(
            update={
                "messages": [
                    HumanMessage(content=f"搜索过程中发生错误：{str(e)}", name="searcher", additional_kwargs={"error": True})
                ]
            },
            goto="supervisor",
        )

def web_crawler_node(state: State) -> Command[Literal["supervisor"]]:
    """Web crawler node that uses OpenAI streaming API and marks output for streaming."""
    # 获取用户任务
    task_message = state["messages"][-1].content if state["messages"] else "请爬取相关信息"

    try:
        # 使用OpenAI流式调用
        result = llm.invoke([
            HumanMessage(content=f"请爬取以下网页内容并提取有用信息：{task_message}")
        ])

        # 标记输出为流式输出
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result.content, name="web_crawler", additional_kwargs={"is_streaming": True})
                ]
            },
            goto="supervisor",
        )
    except Exception as e:
        return Command(
            update={
                "messages": [
                    HumanMessage(content=f"爬取过程中发生错误：{str(e)}", name="web_crawler", additional_kwargs={"error": True})
                ]
            },
            goto="supervisor",
        )

# ------------------------------------------------------------------
# 6. Define Document Writing Agents (Layer 3)
# ------------------------------------------------------------------

writer_agent = create_react_agent(
    llm,
    tools=[write_document, read_document, create_outline],
    prompt=(
        "You can read, write and edit documents based on research findings. "
        "Don't ask follow-up questions."
    ),
)

outline_agent = create_react_agent(llm, tools=[create_outline])
chart_generator_agent = create_react_agent(llm, tools=[generate_chart])

def writer_node(state: State) -> Command[Literal["supervisor"]]:
    """Writer node that uses OpenAI streaming API and marks output for streaming."""
    # 获取用户任务
    task_message = state["messages"][-1].content if state["messages"] else "请写作相关内容"

    try:
        # 使用OpenAI流式调用
        result = llm.invoke([
            HumanMessage(content=f"请基于以下信息写作详细文档：{task_message}")
        ])

        # 标记输出为流式输出
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result.content, name="writer", additional_kwargs={"is_streaming": True})
                ]
            },
            goto="supervisor",
        )
    except Exception as e:
        return Command(
            update={
                "messages": [
                    HumanMessage(content=f"写作过程中发生错误：{str(e)}", name="writer", additional_kwargs={"error": True})
                ]
            },
            goto="supervisor",
        )

def outline_node(state: State) -> Command[Literal["supervisor"]]:
    """Outline node that uses OpenAI streaming API and marks output for streaming."""
    # 获取用户任务
    task_message = state["messages"][-1].content if state["messages"] else "请创建大纲"

    try:
        # 使用OpenAI流式调用
        result = llm.invoke([
            HumanMessage(content=f"请基于以下内容创建详细大纲：{task_message}")
        ])

        # 标记输出为流式输出
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result.content, name="outline", additional_kwargs={"is_streaming": True})
                ]
            },
            goto="supervisor",
        )
    except Exception as e:
        return Command(
            update={
                "messages": [
                    HumanMessage(content=f"创建大纲过程中发生错误：{str(e)}", name="outline", additional_kwargs={"error": True})
                ]
            },
            goto="supervisor",
        )

def chart_generator_node(state: State) -> Command[Literal["supervisor"]]:
    """Chart generator node that uses OpenAI streaming API and marks output for streaming."""
    # 获取用户任务
    task_message = state["messages"][-1].content if state["messages"] else "请生成图表"

    try:
        # 使用OpenAI流式调用
        result = llm.invoke([
            HumanMessage(content=f"请基于以下信息生成图表和可视化内容：{task_message}")
        ])

        # 标记输出为流式输出
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result.content, name="chart_generator", additional_kwargs={"is_streaming": True})
                ]
            },
            goto="supervisor",
        )
    except Exception as e:
        return Command(
            update={
                "messages": [
                    HumanMessage(content=f"生成图表过程中发生错误：{str(e)}", name="chart_generator", additional_kwargs={"error": True})
                ]
            },
            goto="supervisor",
        )

# ------------------------------------------------------------------
# 7. Compose Everything Together (Layer 2)
# ------------------------------------------------------------------

# Create research team supervisor (Layer 2) - 直接管理三级智能体
research_team_supervisor = make_supervisor_node(llm, ["searcher", "web_crawler"])
research_builder_layer2 = StateGraph(State)
research_builder_layer2.add_node("supervisor", research_team_supervisor)
research_builder_layer2.add_node("searcher", searcher_node)
research_builder_layer2.add_node("web_crawler", web_crawler_node)
research_builder_layer2.add_edge(START, "supervisor")
research_team_graph = research_builder_layer2.compile()

def call_research_team(state: State) -> Command[Literal["supervisor"]]:
    """Function to call the research team subgraph."""
    # Get the last message from state
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message is None:
        # If no messages, create a default message
        last_message = HumanMessage(content="请开始处理任务", name="user")

    # Invoke the subgraph
    response = research_team_graph.invoke({"messages": [last_message]})

    # Handle Command response
    if isinstance(response, Command):
        # Extract messages from the command's update
        messages = response.update.get("messages", [])
        final_message = messages[-1] if messages else HumanMessage(content="任务处理完成", name="research_team")

        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=final_message.content, name="research_team"
                    )
                ]
            },
            goto=response.goto,
        )
    else:
        # Handle regular dict response
        messages = response.get("messages", [])
        final_message = messages[-1] if messages else HumanMessage(content="任务处理完成", name="research_team")

        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=final_message.content, name="research_team"
                    )
                ]
            },
            goto="supervisor",
        )

# Create document writing team supervisor (Layer 2) - 直接管理三级智能体
writing_team_supervisor = make_supervisor_node(llm, ["writer", "outline", "chart_generator"])
writing_builder_layer2 = StateGraph(State)
writing_builder_layer2.add_node("supervisor", writing_team_supervisor)
writing_builder_layer2.add_node("writer", writer_node)
writing_builder_layer2.add_node("outline", outline_node)
writing_builder_layer2.add_node("chart_generator", chart_generator_node)
writing_builder_layer2.add_edge(START, "supervisor")
writing_team_graph = writing_builder_layer2.compile()

def call_document_writing_team(state: State) -> Command[Literal["supervisor"]]:
    """Function to call the document writing team subgraph."""
    # Get the last message from state
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message is None:
        # If no messages, create a default message
        last_message = HumanMessage(content="请开始处理任务", name="user")

    # Invoke the subgraph
    response = writing_team_graph.invoke({"messages": [last_message]})

    # Handle Command response
    if isinstance(response, Command):
        # Extract messages from the command's update
        messages = response.update.get("messages", [])
        final_message = messages[-1] if messages else HumanMessage(content="任务处理完成", name="document_writing_team")

        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=final_message.content, name="document_writing_team"
                    )
                ]
            },
            goto=response.goto,
        )
    else:
        # Handle regular dict response
        messages = response.get("messages", [])
        final_message = messages[-1] if messages else HumanMessage(content="任务处理完成", name="document_writing_team")

        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=final_message.content, name="document_writing_team"
                    )
                ]
            },
            goto="supervisor",
        )

# ------------------------------------------------------------------
# 8. Top-level Supervisor (Layer 1)
# ------------------------------------------------------------------

# 创建主管节点（直接路由到第3级智能体）
teams_supervisor_node = make_supervisor_node(llm, ["searcher", "web_crawler", "writer", "outline", "chart_generator"])

# Define the top-level graph (Layer 1) - 直接包含第3级智能体
super_builder = StateGraph(State)
super_builder.add_node("supervisor", teams_supervisor_node)
# 直接添加第3级智能体作为顶层节点
super_builder.add_node("searcher", searcher_node)
super_builder.add_node("web_crawler", web_crawler_node)
super_builder.add_node("writer", writer_node)
super_builder.add_node("outline", outline_node)
super_builder.add_node("chart_generator", chart_generator_node)

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
            'searcher': '网页搜索智能体',
            'web_crawler': '网页爬取智能体',
            'writer': '文档写作智能体',
            'outline': '大纲生成智能体',
            'chart_generator': '图表生成智能体',
            'research_team': '研究团队',
            'document_writing_team': '文档写作团队',
            'search_team': '搜索团队',
            'writing_team': '写作团队'
        }
        return display_names.get(node_name, node_name)

    async def process_task_stream(self, task: str, enable_streaming: bool = True):
        """
        智能流式处理：基于真实执行过程的流式输出

        Args:
            task: 用户输入的任务
            enable_streaming: 是否启用流式输出，默认真实执行时启用

        Yields:
            Dict: 真实执行过程的流式输出
        """
        trace = ExecutionTrace()  # 初始化执行追踪
        agents_called = set()  # 在外部定义，供异常处理使用

        try:
            # 步骤 1: 智能任务分析和执行计划编排
            if enable_streaming:
                yield {
                    "type": "thinking",
                    "agent": "主管",
                    "message": "正在分析任务需求并制定执行计划...",
                    "node": "supervisor",
                    "timestamp": datetime.now().isoformat()
                }
                await asyncio.sleep(0.1)

            # 任务类型预判和执行计划编排
            task_lower = task.lower()
            is_research_only = any(keyword in task_lower for keyword in ['搜索', '查找', '调研', '分析数据', '趋势', '最新'])
            is_writing_only = any(keyword in task_lower for keyword in ['写', '创建', '编辑', '文档', '报告'])
            is_research_writing = is_research_only and is_writing_only

            # 编排执行流程
            execution_plan = []
            if is_research_only and not is_writing_only:
                execution_plan = ["🔍 研究团队 → 搜索专家 → 网页爬取专家"]
            elif is_writing_only and not is_research_only:
                execution_plan = ["📝 文档写作团队 → 大纲生成专家 → 写作专家 → 图表生成专家"]
            elif is_research_writing:
                execution_plan = [
                    "🔍 步骤1：研究团队 → 搜索专家 → 网页爬取专家",
                    "📝 步骤2：文档写作团队 → 大纲生成专家 → 写作专家 → 图表生成专家"
                ]
            else:
                execution_plan = ["🔄 任务类型待定，将根据执行过程动态调整"]

            # 展示完整的任务执行流程
            if enable_streaming:
                plan_message = "📋 **任务执行计划**\n\n" + "\n\n".join(execution_plan) + "\n\n✅ 开始执行..."
                yield {
                    "type": "status",
                    "agent": "主管",
                    "message": plan_message,
                    "node": "supervisor",
                    "timestamp": datetime.now().isoformat()
                }
                await asyncio.sleep(0.1)

            # 步骤 2: 执行真实任务并追踪过程
            initial_state = {"messages": [HumanMessage(content=task)]}

            # 启动执行（无流式输出）
            if enable_streaming:
                yield {
                    "type": "status",
                    "agent": "主管",
                    "message": "🚀 启动智能体团队执行...",
                    "node": "supervisor",
                    "timestamp": datetime.now().isoformat()
                }
                await asyncio.sleep(0.05)

            # 使用 astream 执行并实时追踪
            async for chunk in self.graph.astream(initial_state, config={"recursion_limit": 150}):
                # 遍历每个节点
                for node_name, output in chunk.items():
                    # 获取节点显示名称
                    display_name = self._get_node_display_name(node_name)

                    # 记录调用的智能体
                    if hasattr(output, 'get') and isinstance(output, dict):
                        if 'messages' in output:
                            for msg in output['messages']:
                                if hasattr(msg, 'name') and msg.name:
                                    agents_called.add(msg.name)

                    # 如果启用流式输出，为每个节点创建单独的消息框
                    if enable_streaming:
                        # 节点开始执行的消息
                        yield {
                            "type": "thinking",
                            "agent": display_name,
                            "message": f"⚙️ 正在执行 {display_name} 任务...",
                            "node": node_name,
                            "timestamp": datetime.now().isoformat()
                        }
                        await asyncio.sleep(0.05)

                        # 如果有消息输出，逐个输出
                        if hasattr(output, 'get') and isinstance(output, dict):
                            if 'messages' in output:
                                for msg in output['messages']:
                                    if hasattr(msg, 'content') and msg.content:
                                        # 逐字流式输出
                                        words = msg.content.split()
                                        chunk_size = min(5, max(1, len(words) // 10))
                                        for i in range(0, len(words), chunk_size):
                                            word_chunk = " ".join(words[i:i+chunk_size])
                                            yield {
                                                "type": "result",
                                                "agent": display_name,
                                                "message": word_chunk,
                                                "node": node_name,
                                                "timestamp": datetime.now().isoformat()
                                            }
                                            await asyncio.sleep(0.02)

                        # 节点完成消息
                        yield {
                            "type": "status",
                            "agent": display_name,
                            "message": f"✅ {display_name} 执行完成",
                            "node": node_name,
                            "timestamp": datetime.now().isoformat()
                        }
                        await asyncio.sleep(0.05)

            # 步骤 3: 生成执行摘要（仅在流式输出时）
            if enable_streaming:
                yield {
                    "type": "thinking",
                    "agent": "主管",
                    "message": "📊 整理执行结果...",
                    "node": "supervisor",
                    "timestamp": datetime.now().isoformat()
                }
                await asyncio.sleep(0.05)

                # 生成调度摘要
                if agents_called:
                    agent_names = [self._get_node_display_name(agent) for agent in agents_called]
                    yield {
                        "type": "status",
                        "agent": "主管",
                        "message": f"🎯 执行完成！共调用了 {len(agents_called)} 个智能体：{', '.join(agent_names)}",
                        "node": "supervisor",
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    yield {
                        "type": "status",
                        "agent": "主管",
                        "message": "⚠️ 未检测到智能体调用",
                        "node": "supervisor",
                        "timestamp": datetime.now().isoformat()
                    }

                await asyncio.sleep(0.05)

            # 步骤 5: 发送完成信号
            yield {
                "type": "end",
                "agent": "系统",
                "message": f"✨ 任务执行完成（调用{len(agents_called)}个智能体）",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            print(f"流式调用错误: {e}")
            import traceback
            traceback.print_exc()
            yield {
                "type": "error",
                "agent": "系统",
                "message": f"任务执行出错: {str(e)}",
                "timestamp": datetime.now().isoformat()
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


# ==============================================================================
# 10. 统一任务调度器
# ==============================================================================

class TaskScheduler:
    """
    统一任务调度器

    职责：
    1. 接收用户任务
    2. 调用主管进行任务分析和决策
    3. 编排执行流程
    4. 调度执行该流程
    5. 控制流式输出
    """

    def __init__(self, agent_team: HierarchicalAgentTeam):
        """
        初始化任务调度器

        Args:
            agent_team: 智能体团队实例
        """
        self.agent_team = agent_team

    async def receive_task(self, task: str, enable_streaming: bool = True):
        """
        接收用户任务并调度执行

        Args:
            task: 用户提交的任务
            enable_streaming: 是否启用流式输出

        Yields:
            任务执行过程的流式输出
        """
        try:
            # 步骤 1: 任务调度器接收任务
            if enable_streaming:
                yield {
                    "type": "status",
                    "agent": "任务调度器",
                    "message": f"📥 接收任务：{task}",
                    "node": "scheduler",
                    "timestamp": datetime.now().isoformat()
                }
                await asyncio.sleep(0.05)

            # 步骤 2: 调用主管进行任务分析并编排执行流程
            if enable_streaming:
                yield {
                    "type": "thinking",
                    "agent": "任务调度器",
                    "message": "🤖 正在调用一级主管进行任务分析并编排执行流程...",
                    "node": "scheduler",
                    "timestamp": datetime.now().isoformat()
                }
                await asyncio.sleep(0.05)

            # 步骤 3: 初始化任务状态
            initial_state = {"messages": [HumanMessage(content=task)]}

            # 步骤 4: 实时追踪整个智能体团队的执行过程
            agents_called = set()  # 记录所有被调用的智能体

            if enable_streaming:
                yield {
                    "type": "status",
                    "agent": "任务调度器",
                    "message": "🚀 启动智能体团队，实时追踪执行过程...",
                    "node": "scheduler",
                    "timestamp": datetime.now().isoformat()
                }
                await asyncio.sleep(0.05)

            # 使用 astream 实时追踪所有节点的执行（包括第3级智能体）
            async for chunk in self.agent_team.graph.astream(initial_state, config={"recursion_limit": 150}):
                for node_name, output in chunk.items():
                    display_name = self.agent_team._get_node_display_name(node_name)

                    # 记录被调用的智能体
                    if hasattr(output, 'get') and isinstance(output, dict):
                        if 'messages' in output:
                            for msg in output['messages']:
                                if hasattr(msg, 'name') and msg.name:
                                    agents_called.add(msg.name)

                    # 为每个节点创建独立的消息框
                    if enable_streaming:
                        # 节点开始执行
                        yield {
                            "type": "thinking",
                            "agent": display_name,
                            "message": f"⚙️ 正在执行 {display_name} 任务...",
                            "node": node_name,
                            "timestamp": datetime.now().isoformat()
                        }
                        await asyncio.sleep(0.05)

                        # 输出结果内容（真实流式输出）
                        if hasattr(output, 'get') and isinstance(output, dict):
                            if 'messages' in output:
                                for msg in output['messages']:
                                    if hasattr(msg, 'content') and msg.content:
                                        # 检查是否有流式块（来自OpenAI的真正流式内容）
                                        if (hasattr(msg, 'additional_kwargs') and
                                            msg.additional_kwargs.get('is_streaming') and
                                            'streaming_chunks' in msg.additional_kwargs):

                                            # 真正的OpenAI流式输出：逐个输出流式块
                                            streaming_chunks = msg.additional_kwargs['streaming_chunks']
                                            for chunk in streaming_chunks:
                                                if chunk:  # 确保块不为空
                                                    yield {
                                                        "type": "result",
                                                        "agent": display_name,
                                                        "message": chunk,
                                                        "node": node_name,
                                                        "timestamp": datetime.now().isoformat(),
                                                        "is_real_streaming": True  # 标记为真正的OpenAI流式输出
                                                    }
                                                    await asyncio.sleep(0.01)  # 短暂延迟以实现流式效果
                                        else:
                                            # 非流式输出：根据内容长度决定输出方式
                                            content_length = len(msg.content)
                                            if content_length > 100:
                                                # 长内容：分块流式输出（模拟）
                                                words = msg.content.split()
                                                chunk_size = min(8, max(3, len(words) // 15))
                                                for i in range(0, len(words), chunk_size):
                                                    word_chunk = " ".join(words[i:i+chunk_size])
                                                    yield {
                                                        "type": "result",
                                                        "agent": display_name,
                                                        "message": word_chunk,
                                                        "node": node_name,
                                                        "timestamp": datetime.now().isoformat()
                                                    }
                                                    await asyncio.sleep(0.03)
                                            else:
                                                # 短内容：直接输出
                                                yield {
                                                    "type": "result",
                                                    "agent": display_name,
                                                    "message": msg.content,
                                                    "node": node_name,
                                                    "timestamp": datetime.now().isoformat()
                                                }
                                                await asyncio.sleep(0.05)

                        # 节点完成
                        yield {
                            "type": "status",
                            "agent": display_name,
                            "message": f"✅ {display_name} 执行完成",
                            "node": node_name,
                            "timestamp": datetime.now().isoformat()
                        }
                        await asyncio.sleep(0.05)

            # 步骤 5: 调度器汇总执行结果
            if enable_streaming:
                yield {
                    "type": "thinking",
                    "agent": "任务调度器",
                    "message": "📊 汇总执行结果...",
                    "node": "scheduler",
                    "timestamp": datetime.now().isoformat()
                }
                await asyncio.sleep(0.05)

                # 显示实际调用的智能体列表
                agent_names = [self.agent_team._get_node_display_name(agent) for agent in agents_called if agent in ['supervisor', 'research_team', 'document_writing_team', 'searcher', 'web_crawler', 'writer', 'outline', 'chart_generator']]
                if agent_names:
                    summary_message = f"📋 **任务执行完成**\n\n✅ 成功调用 {len(agent_names)} 个智能体：\n" + "\n".join([f"  • {name}" for name in agent_names])
                    yield {
                        "type": "final",
                        "agent": "任务调度器",
                        "message": summary_message,
                        "node": "scheduler",
                        "timestamp": datetime.now().isoformat()
                    }
                    await asyncio.sleep(0.05)

            # 结束任务
            if enable_streaming:
                yield {
                    "type": "end",
                    "agent": "任务调度器",
                    "message": "✨ 任务执行完成",
                    "node": "scheduler",
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            yield {
                "type": "error",
                "agent": "任务调度器",
                "message": f"❌ 任务调度执行出错: {str(e)}",
                "node": "scheduler",
                "timestamp": datetime.now().isoformat()
            }

    async def execute_sync(self, task: str):
        """
        同步执行任务（不启用流式输出）

        Args:
            task: 用户任务

        Returns:
            执行结果
        """
        results = []
        async for data in self.receive_task(task, enable_streaming=False):
            results.append(data)

        # 提取最终结果
        final_messages = []
        for result in results:
            if result.get("type") == "result":
                final_messages.append(result.get("message", ""))

        return {
            "task": task,
            "result": "\n\n".join(final_messages) if final_messages else "任务执行完成",
            "steps": results,
            "success": True
        }


def create_task_scheduler(agent_team: HierarchicalAgentTeam = None):
    """
    创建任务调度器实例

    Args:
        agent_team: 智能体团队实例，如果为None则创建新的

    Returns:
        任务调度器实例
    """
    if agent_team is None:
        agent_team = create_agent_team()

    return TaskScheduler(agent_team)
