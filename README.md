# 分层智能体团队系统 (Hierarchical Agent Teams)

基于 LangGraph 的多智能体协作框架，支持实时流式响应，提供前后端分离的全栈解决方案。

## 📁 项目结构

```
hierarchical-agent-teams/
├── backend/                     # 后端代码
│   ├── .env                     # 环境变量（已存在）
│   ├── pyproject.toml           # uv 依赖配置
│   ├── uv.lock                  # 依赖锁文件
│   ├── main.py                   # FastAPI 主应用
│   ├── hierarchical_agent_teams.py      # 分层智能体团队核心逻辑
│   └── streaming.py             # SSE 流式响应处理
│
└── frontend/                    # 前端代码
    ├── index.html               # HTML 入口
    ├── package.json             # npm 依赖配置
    ├── vite.config.js           # Vite 配置
    ├── src/
    │   ├── main.js              # Vue 应用入口
    │   ├── App.vue              # 根组件
    │   └── components/
    │       ├── InputArea.vue    # 输入组件
    │       └── ChatDisplay.vue  # 聊天显示组件
    └── public/                  # 静态资源
```

---

## 后端启动

```bash
cd backend

# 创建虚拟环境命令（第一次运行时执行）
uv venv --python 3.13

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖（使用 uv）
uv sync

# 启动服务（默认端口 8000）
uv run uvicorn main:app --reload --port 8000
```

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（默认端口 3000）
npm run dev
```

## 配置修改

- **后端 API 地址**：修改 `frontend/src/App.vue` 中的 `API_BASE_URL`

## API 接口

### 端点列表

#### 1. 健康检查

```http
GET /health
```

**响应**：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-12-10"
}
```

#### 2. 获取智能体列表

```http
GET /agents
```

**响应**：
```json
{
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
                    "name": "网页搜索智能体",
                    "role": "Search Specialist",
                    "description": "负责网络搜索和信息查找",
                    "tools": ["web_search"],
                    "layer": 3
                },
                "web_crawler": {
                    "name": "网页爬取智能体",
                    "role": "Web Crawler Specialist",
                    "description": "负责网页内容抓取",
                    "tools": ["web_crawler"],
                    "layer": 3
                },
                "writer": {
                    "name": "文档写作智能体",
                    "role": "Writing Specialist",
                    "description": "负责文档撰写",
                    "tools": ["write_document", "read_document", "create_outline"],
                    "layer": 3
                },
                "outline": {
                    "name": "大纲生成智能体",
                    "role": "Outline Generation Specialist",
                    "description": "负责创建文档大纲",
                    "tools": ["create_outline"],
                    "layer": 3
                },
                "chart_generator": {
                    "name": "图表生成智能体",
                    "role": "Chart Generation Specialist",
                    "description": "负责数据可视化",
                    "tools": ["generate_chart"],
                    "layer": 3
                }
            }
        }
}
```

#### 3. 同步聊天

```http
POST /chat
Content-Type: application/json

{
  "task": "分析北京房价趋势",
  "stream": false
}
```

#### 4. 流式聊天（SSE）

```http
POST /stream-chat/v2
Content-Type: application/json

{
  "task": "制定一份 Python 学习计划",
  "stream": true
}
```
# HierarchicalAgentTeams
