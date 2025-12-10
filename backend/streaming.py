"""
流式响应处理模块

本模块负责：
1. 将智能体团队的异步流式输出转换为 Server-Sent Events (SSE)
2. 处理前端 SSE 连接和断开
3. 实现流式数据的格式化传输
4. 提供连接管理和错误处理

核心技术：
- 使用 FastAPI 的 StreamingResponse
- 实现 SSE 协议格式
- 异步生成器实时推送数据
"""

import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime

from fastapi import Request
from fastapi.responses import StreamingResponse, JSONResponse


class StreamManager:
    """流式响应管理器"""

    def __init__(self):
        self.active_streams: Dict[str, asyncio.Queue] = {}
        self.stream_counter = 0

    def create_stream(self) -> str:
        """创建新的流式连接"""
        stream_id = f"stream_{self.stream_counter}"
        self.stream_counter += 1
        self.active_streams[stream_id] = asyncio.Queue()
        return stream_id

    async def send_to_stream(self, stream_id: str, data: Dict[str, Any]):
        """发送数据到指定流"""
        if stream_id in self.active_streams:
            await self.active_streams[stream_id].put(data)

    async def close_stream(self, stream_id: str):
        """关闭流式连接"""
        if stream_id in self.active_streams:
            # 发送结束信号
            try:
                await self.active_streams[stream_id].put({
                    "type": "end",
                    "agent": "系统",
                    "message": "Stream completed",
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                print(f"发送结束信号失败: {e}")
            # 注意：不立即删除流，由 generate_sse_stream 的 finally 块负责清理

    def remove_stream(self, stream_id: str):
        """移除流式连接"""
        if stream_id in self.active_streams:
            try:
                del self.active_streams[stream_id]
            except Exception as e:
                print(f"删除流时出错: {type(e).__name__}: {str(e)}")


# 全局流管理器实例
stream_manager = StreamManager()


def format_sse_data(data: Dict[str, Any]) -> str:
    """
    将数据格式化为 SSE 格式

    Args:
        data: 要发送的数据

    Returns:
        SSE 格式的字符串
    """
    # 将数据转换为 JSON 字符串（单行，避免多行JSON导致解析问题）
    json_data = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

    # SSE 格式要求每行以 "data: " 开头，空行表示结束
    # 使用单行 JSON 以便前端正确解析
    formatted = f"data: {json_data}\n\n"

    return formatted


async def generate_sse_stream(
    stream_id: str,
    request: Request
) -> AsyncGenerator[bytes, None]:
    """
    生成 SSE 流式响应

    Args:
        stream_id: 流式连接 ID
        request: FastAPI 请求对象

    Yields:
        bytes: SSE 格式的数据块
    """
    try:
        # 发送初始连接确认
        initial_data = {
            "type": "connection",
            "agent": "系统",
            "message": "流式连接已建立",
            "stream_id": stream_id,
            "timestamp": datetime.now().isoformat()
        }
        yield format_sse_data(initial_data).encode('utf-8')

        # 持续监听流管理器中的数据
        while True:
            # 检查客户端是否断开连接
            if await request.is_disconnected():
                print(f"客户端已断开连接: {stream_id}")
                break

            try:
                # 检查流是否仍然存在
                if stream_id not in stream_manager.active_streams:
                    print(f"流已关闭，停止监听: {stream_id}")
                    break

                # 从队列获取数据，设置超时避免无限阻塞
                data = await asyncio.wait_for(
                    stream_manager.active_streams[stream_id].get(),
                    timeout=0.1
                )

                # 格式化并发送数据
                yield format_sse_data(data).encode('utf-8')

                # 如果收到结束信号，退出循环
                if data.get("type") == "end":
                    break

            except asyncio.TimeoutError:
                # 超时继续循环，保持连接
                continue

            except Exception as e:
                # 记录详细错误信息
                print(f"流式传输错误 [stream_id={stream_id}]: {type(e).__name__}: {str(e)}")
                # 发生错误，发送错误信息
                error_data = {
                    "type": "error",
                    "agent": "系统",
                    "message": f"流式传输错误: {type(e).__name__}",
                    "stream_id": stream_id,
                    "timestamp": datetime.now().isoformat()
                }
                yield format_sse_data(error_data).encode('utf-8')
                break

    except asyncio.CancelledError:
        print(f"流式响应被取消: {stream_id}")
        raise

    except Exception as e:
        # 捕获所有异常
        error_data = {
            "type": "error",
            "agent": "系统",
            "message": f"流式响应异常: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        yield format_sse_data(error_data).encode('utf-8')

    finally:
        # 清理资源（安全删除，即使流已不存在）
        try:
            stream_manager.remove_stream(stream_id)
            print(f"流式连接已关闭: {stream_id}")
        except Exception as e:
            print(f"清理流时出错 [stream_id={stream_id}]: {type(e).__name__}: {str(e)}")


def create_streaming_response(stream_id: str, request: Request) -> StreamingResponse:
    """
    创建流式响应

    Args:
        stream_id: 流式连接 ID
        request: FastAPI 请求对象

    Returns:
        StreamingResponse: SSE 流式响应
    """
    return StreamingResponse(
        generate_sse_stream(stream_id, request),
        media_type="text/event-stream",
        headers={
            # 关键 headers 确保 SSE 正常工作
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 禁用缓冲
            "Access-Control-Allow-Origin": "*",  # 允许跨域
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )


async def process_agent_stream(
    task: str,
    stream_id: str,
    agent_team
) -> None:
    """
    处理智能体团队流式输出并推送到指定流

    Args:
        task: 用户任务
        stream_id: 流式连接 ID
        agent_team: 智能体团队实例
    """
    try:
        # 创建后台任务队列用于实时转发
        output_queue = asyncio.Queue()

        # 启动智能体团队任务处理（在后台运行）
        async def run_agent_task():
            try:
                async for data in agent_team.process_task_stream(task):
                    await output_queue.put(data)
                await output_queue.put({"type": "task_completed"})  # 任务完成信号
            except Exception as e:
                await output_queue.put({
                    "type": "error",
                    "agent": "系统",
                    "message": f"任务处理异常: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })

        # 在后台启动任务
        task_handle = asyncio.create_task(run_agent_task())

        # 实时从队列读取并转发到流管理器
        while True:
            try:
                # 等待数据（设置超时保持响应性）
                data = await asyncio.wait_for(output_queue.get(), timeout=0.1)

                # 检查是否是任务完成信号
                if isinstance(data, dict) and data.get("type") == "task_completed":
                    break

                # 推送到流管理器
                await stream_manager.send_to_stream(stream_id, data)

                # 如果收到结束信号，退出循环
                if data.get("type") == "end":
                    break

            except asyncio.TimeoutError:
                # 超时继续循环，保持连接活跃
                continue

        # 等待后台任务完成
        await task_handle

        # 发送结束信号
        await stream_manager.close_stream(stream_id)

    except Exception as e:
        # 处理过程中的异常
        error_data = {
            "type": "error",
            "agent": "系统",
            "message": f"流式处理异常: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        await stream_manager.send_to_stream(stream_id, error_data)
        await stream_manager.close_stream(stream_id)


# ==============================================================================
# 辅助函数
# ==============================================================================

def create_error_response(message: str, status_code: int = 500) -> JSONResponse:
    """创建错误响应"""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": True,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    )


def validate_task_input(task: str) -> Optional[str]:
    """
    验证用户输入的任务

    Args:
        task: 用户输入的任务字符串

    Returns:
        str or None: 验证失败返回错误信息，验证成功返回 None
    """
    if not task or not task.strip():
        return "任务内容不能为空"

    if len(task) > 5000:
        return "任务内容过长（限制 5000 字符）"

    # 检查是否包含恶意内容
    malicious_patterns = ["<script", "javascript:", "eval("]
    task_lower = task.lower()
    for pattern in malicious_patterns:
        if pattern in task_lower:
            return f"任务内容包含不允许的模式: {pattern}"

    return None
