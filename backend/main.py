"""
FastAPI 主应用文件

本文件实现：
1. RESTful API 接口（/chat, /health）
2. SSE 流式响应端点（/stream-chat）
3. 智能体团队的集成调用
4. 请求验证和错误处理
5. CORS 配置支持前端调用

主要端点：
- POST /chat: 提交任务（同步响应）
- POST /stream-chat: 提交任务（流式响应，SSE）
- GET /health: 健康检查
- GET /agents: 获取可用智能体列表
"""

import os
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# 导入本地模块
from hierarchical_agent_teams import create_agent_team, HierarchicalAgentTeam
from streaming import (
    stream_manager,
    create_streaming_response,
    process_agent_stream,
    create_error_response,
    validate_task_input
)


# ==============================================================================
# 1. Pydantic 模型定义
# ==============================================================================

class ChatRequest(BaseModel):
    """聊天请求模型"""
    task: str = Field(..., min_length=1, max_length=500, description="用户任务")
    stream: bool = Field(default=True, description="是否启用流式响应")


class ChatResponse(BaseModel):
    """聊天响应模型"""
    success: bool
    message: str
    data: Dict[str, Any]
    timestamp: str


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str
    version: str
    timestamp: str


# ==============================================================================
# 2. FastAPI 应用初始化
# ==============================================================================

app = FastAPI(
    title="分层智能体团队 API",
    description="基于 LangGraph 的分层智能体团队系统，支持流式响应",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置（允许前端调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # 暴露所有响应头给前端
)


# ==============================================================================
# 3. 全局变量
# ==============================================================================

# 全局智能体团队实例（实际生产中应考虑线程安全）
agent_team: HierarchicalAgentTeam = create_agent_team()


# ==============================================================================
# 4. API 端点
# ==============================================================================

@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查端点"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp="2025-12-09"
    )


@app.get("/agents", response_model=Dict[str, Any], tags=["智能体团队"])
async def get_agents():
    """获取可用智能体列表（基于官方 LangGraph 教程三层结构）"""
    return {
        "layer_1": {
            "name": "第1层 - 主管",
            "nodes": {
                "supervisor": {
                    "name": "主管",
                    "role": "Top-level Supervisor",
                    "description": "负责任务分配和团队协调",
                    "layer": 1
                }
            }
        },
        "layer_2": {
            "name": "第2层 - 团队",
            "nodes": {
                "research_team": {
                    "name": "研究团队",
                    "role": "Research Team Supervisor",
                    "description": "协调研究团队内部工作",
                    "layer": 2,
                    "members": {
                        "search_team": {
                            "name": "搜索团队",
                            "layer": 3,
                            "description": "负责搜索和信息提取"
                        }
                    }
                },
                "document_writing_team": {
                    "name": "文档写作团队",
                    "role": "Document Writing Team Supervisor",
                    "description": "协调文档写作团队内部工作",
                    "layer": 2,
                    "members": {
                        "writing_team": {
                            "name": "写作团队",
                            "layer": 3,
                            "description": "负责文档创作和可视化"
                        }
                    }
                }
            }
        },
        "layer_3": {
            "name": "第3层 - 执行节点",
            "nodes": {
                "searcher": {
                    "name": "搜索器",
                    "role": "Search Specialist",
                    "description": "负责网络搜索和信息查找",
                    "tools": ["web_search"],
                    "layer": 3
                },
                "web_crawler": {
                    "name": "网页爬虫",
                    "role": "Web Crawler Specialist",
                    "description": "负责网页内容抓取",
                    "tools": ["web_crawler"],
                    "layer": 3
                },
                "writer": {
                    "name": "写作者",
                    "role": "Writing Specialist",
                    "description": "负责文档撰写",
                    "tools": ["write_document", "read_document", "create_outline"],
                    "layer": 3
                },
                "notebook": {
                    "name": "记事本",
                    "role": "Notebook Specialist",
                    "description": "负责创建和管理笔记",
                    "tools": ["create_notebook"],
                    "layer": 3
                },
                "chart_generator": {
                    "name": "图表生成器",
                    "role": "Chart Generation Specialist",
                    "description": "负责数据可视化",
                    "tools": ["generate_chart"],
                    "layer": 3
                }
            }
        }
    }


@app.post("/chat", response_model=ChatResponse, tags=["聊天"])
async def chat_sync(request: ChatRequest):
    """
    同步聊天端点（非流式）

    适合需要完整结果而非实时流式响应的场景
    """
    # 验证输入
    validation_error = validate_task_input(request.task)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    try:
        # 同步执行任务（收集所有流式数据）
        results = []
        async for data in agent_team.process_task_stream(request.task):
            results.append(data)

        # 组合最终结果
        final_message = ""
        for result in results:
            if result.get("type") == "final":
                final_message = result.get("message", "")
                break

        return ChatResponse(
            success=True,
            message="任务执行完成",
            data={
                "task": request.task,
                "result": final_message,
                "steps": results
            },
            timestamp="2025-12-10"
        )

    except Exception as e:
        return ChatResponse(
            success=False,
            message=f"任务执行失败: {str(e)}",
            data={},
            timestamp="2025-12-10"
        )


@app.post("/stream-chat", tags=["聊天"])
async def chat_stream(request: ChatRequest):
    """
    流式聊天端点（SSE）

    主要端点：
    1. 验证输入任务
    2. 创建流式连接
    3. 启动后台任务处理
    4. 返回 SSE 响应
    """
    # 验证输入
    validation_error = validate_task_input(request.task)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    # 创建流式连接
    stream_id = stream_manager.create_stream()

    # 创建后台任务处理智能体团队流
    background_task = asyncio.create_task(
        process_agent_stream(request.task, stream_id, agent_team)
    )

    # 创建并返回 SSE 响应
    # 注意：需要在请求对象中传递
    # 实际中需要通过依赖注入获取
    return create_streaming_response(stream_id, Request({"type": "http"}))


# 更实用的实现（通过依赖注入获取 Request）
from fastapi import Depends

async def get_request() -> Request:
    """获取当前请求对象（依赖注入）"""
    # 这里需要 FastAPI 的 Request 对象
    # 在实际应用中通过 Depends 注入
    pass


# 重新定义流式端点（使用更实用的方式）
@app.post("/stream-chat/v2", tags=["聊天"])
async def chat_stream_v2(request: Request, chat_request: ChatRequest):
    """
    流式聊天端点（推荐使用）
    """
    # 验证输入
    validation_error = validate_task_input(chat_request.task)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    # 创建流式连接
    stream_id = stream_manager.create_stream()

    # 创建后台任务
    background_task = asyncio.create_task(
        process_agent_stream(chat_request.task, stream_id, agent_team)
    )

    # 返回 SSE 响应
    return create_streaming_response(stream_id, request)


# ==============================================================================
# 5. 启动配置
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    print("=" * 60)
    print("🚀 分层智能体团队 API 启动成功")
    print("=" * 60)
    print("📡 API 文档: http://localhost:8000/docs")
    print("🔍 ReDoc 文档: http://localhost:8000/redoc")
    print("❤️  健康检查: http://localhost:8000/health")
    print("=" * 60)

    # 检查环境变量
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  警告: 未检测到 OPENAI_API_KEY")
    if not os.getenv("TAVILY_API_KEY"):
        print("⚠️  警告: 未检测到 TAVILY_API_KEY")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    print("=" * 60)
    print("🛑 分层智能体团队 API 已关闭")
    print("=" * 60)


# ==============================================================================
# 6. 主入口
# ==============================================================================

if __name__ == "__main__":
    # 使用 uvicorn 启动应用
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
