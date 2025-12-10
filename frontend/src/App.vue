<template>
  <div id="app">
    <div class="app-layout">
      <!-- 顶部导航栏 -->
      <header class="app-header">
        <div class="header-left">
          <div class="logo">
            <span class="logo-icon">🤖</span>
            <h1>分层智能体团队系统</h1>
          </div>
        </div>
        <div class="header-right">
          <!-- 流式状态指示器 -->
          <div v-if="loading" class="streaming-status">
            <span class="streaming-dot"></span>
            <span class="streaming-text">
              {{ currentActiveAgent || '智能体团队正在思考中...' }}
            </span>
          </div>
        </div>
      </header>

      <!-- 主体内容 -->
      <div class="app-main">
        <!-- 侧边栏 -->
        <aside class="sidebar" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
          <div class="sidebar-header">
            <h3>分层智能体团队</h3>
          </div>

          <!-- 智能体团队树形结构 -->
          <div class="agent-tree">
            <!-- 第 1 层 -->
            <div class="tree-level">
              <div class="tree-node root-node">
                <span class="node-icon">👨‍💼</span>
                <span class="node-name">主管</span>
                <span :class="['agent-status-dot', 'idle']"></span>
              </div>
            </div>

            <!-- 第 2 层 -->
            <div class="tree-level">
              <!-- 研究团队分支 -->
              <div class="tree-branch">
                <div class="tree-node team-node">
                  <span class="branch-connector">├─</span>
                  <span class="node-icon">👥</span>
                  <span class="node-name">研究团队</span>
                  <span :class="['agent-status-dot', 'idle']"></span>
                </div>
                <div class="tree-children">
                  <div class="tree-node child-node">
                    <span class="leaf-connector">│  ├─</span>
                    <span class="node-icon">🔍</span>
                    <span class="node-name">搜索器</span>
                    <span :class="['agent-status-dot', 'idle']"></span>
                  </div>
                  <div class="tree-node child-node">
                    <span class="leaf-connector">│  └─</span>
                    <span class="node-icon">🕷️</span>
                    <span class="node-name">网页爬虫</span>
                    <span :class="['agent-status-dot', 'idle']"></span>
                  </div>
                </div>
              </div>

              <!-- 文档写作团队分支 -->
              <div class="tree-branch">
                <div class="tree-node team-node">
                  <span class="branch-connector">└─</span>
                  <span class="node-icon">📝</span>
                  <span class="node-name">文档写作团队</span>
                  <span :class="['agent-status-dot', 'idle']"></span>
                </div>
                <div class="tree-children">
                  <div class="tree-node child-node">
                    <span class="leaf-connector">   ├─</span>
                    <span class="node-icon">✍️</span>
                    <span class="node-name">写作者</span>
                    <span :class="['agent-status-dot', 'idle']"></span>
                  </div>
                  <div class="tree-node child-node">
                    <span class="leaf-connector">   ├─</span>
                    <span class="node-icon">📓</span>
                    <span class="node-name">记事本</span>
                    <span :class="['agent-status-dot', 'idle']"></span>
                  </div>
                  <div class="tree-node child-node">
                    <span class="leaf-connector">   └─</span>
                    <span class="node-icon">📊</span>
                    <span class="node-name">图表生成器</span>
                    <span :class="['agent-status-dot', 'idle']"></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <!-- 聊天区域 -->
        <main class="chat-area">
          <ChatDisplay
            :messages="messages"
            :loading="loading"
          />
          <InputArea
            :loading="loading"
            :disabled="loading"
            @submit="handleSubmit"
          />
        </main>
      </div>
    </div>

    <!-- 错误提示模态框 -->
    <div v-if="error" class="error-modal" @click.self="error = ''">
      <div class="error-content">
        <h3>❌ 发生错误</h3>
        <p>{{ error }}</p>
        <button @click="error = ''" class="error-close-button">
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import ChatDisplay from './components/ChatDisplay.vue'
import InputArea from './components/InputArea.vue'

// 配置
const API_BASE_URL = 'http://localhost:8000'

// 响应式数据
const messages = ref([])
const loading = ref(false)
const error = ref('')
const sidebarCollapsed = ref(false)
const currentActiveAgent = ref('')
const currentMainMessageIndex = ref(-1) // 当前请求的主消息框索引（所有输出聚合到这里）

// 智能体团队状态（基于官方 LangGraph 教程三层结构）
const agentTeam = reactive([
  // 第 1 层
  { name: '主管', avatar: '👨‍💼', status: 'idle', active: false, role: 'supervisor', layer: 1 },
  // 第 2 层
  { name: '研究团队', avatar: '👥', status: 'idle', active: false, role: 'research_team', layer: 2 },
  { name: '文档写作团队', avatar: '📝', status: 'idle', active: false, role: 'document_writing_team', layer: 2 },
  // 第 3 层 - 研究团队
  { name: '搜索器', avatar: '🔍', status: 'idle', active: false, role: 'searcher', layer: 3 },
  { name: '网页爬虫', avatar: '🕷️', status: 'idle', active: false, role: 'web_crawler', layer: 3 },
  // 第 3 层 - 文档写作团队
  { name: '写作者', avatar: '✍️', status: 'idle', active: false, role: 'writer', layer: 3 },
  { name: '记事本', avatar: '📓', status: 'idle', active: false, role: 'notebook', layer: 3 },
  { name: '图表生成器', avatar: '📊', status: 'idle', active: false, role: 'chart_generator', layer: 3 }
])

/**
 * 立即滚动到最新消息
 */
const scrollToLatestMessage = () => {
  const chatDisplay = document.querySelector('.chat-display .messages-container')
  if (chatDisplay) {
    chatDisplay.scrollTop = chatDisplay.scrollHeight
  }
}

/**
 * 处理用户提交的任务
 */
const handleSubmit = async (task) => {
  error.value = ''

  // 清空之前的消息，实现单次对话效果
  // 保留欢迎消息相关检查，只清空之前的智能体消息
  messages.value = []

  // 添加用户任务消息（但不会显示）
  const userMessage = {
    type: 'user',
    agent: '用户',
    message: task,
    timestamp: new Date().toISOString()
  }
  messages.value.push(userMessage)

  // 初始化当前主消息框索引
  currentMainMessageIndex.value = -1

  // 开始加载
  loading.value = true
  updateAgentStatus('active')

  // 建立流式连接
  fetchStreamData(task)
}

/**
 * 使用 Fetch API 处理流式响应
 */
const fetchStreamData = async (task) => {
  try {
    loading.value = true
    console.log('开始发送请求:', task)

    const response = await fetch(`${API_BASE_URL}/stream-chat/v2`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        task: task,
        stream: true
      })
    })

    console.log('响应状态:', response.status, response.statusText)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    console.log('开始读取流式数据...')

    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        console.log('流式数据读取完成')
        break
      }

      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk

      const lines = buffer.split('\n')
      const lastLine = lines.pop() || ''

      for (const line of lines) {
        if (line.trim() && line.startsWith('data: ')) {
          try {
            const jsonData = line.slice(6).trim()

            if (!jsonData.endsWith('}')) {
              console.log('JSON 不完整，跳过:', jsonData)
              continue
            }

            const parsedData = JSON.parse(jsonData)
            const agentName = parsedData.agent || '系统'
            console.log('接收到数据:', parsedData.type, agentName, parsedData.message?.substring(0, 50))

            // 只显示主管（supervisor）的消息
            if (parsedData.node === 'supervisor') {
              const messageType = parsedData.type

              // 思考过程：追加到当前主消息框（保持打字机效果）
              if (messageType === 'thinking') {
                if (currentMainMessageIndex.value === -1) {
                  // 创建新的主消息框（这是本次请求的第一个消息）
                  messages.value.push(parsedData)
                  currentMainMessageIndex.value = messages.value.length - 1
                } else {
                  // 追加内容到当前主消息框 - 必须使用 Vue 的响应式方式更新
                  const index = currentMainMessageIndex.value
                  const currentMessage = messages.value[index]
                  if (currentMessage) {
                    // 关键：创建新对象而不是直接修改属性，触发 Vue 响应式更新
                    // 追加新内容而不是替换（在原有内容后添加换行和新内容）
                    const separator = currentMessage.message.endsWith('\n') ? '' : '\n'
                    const newMessage = {
                      ...currentMessage,
                      message: currentMessage.message + separator + parsedData.message
                    }
                    // 使用 splice 替换元素，确保 Vue 检测到变化
                    messages.value.splice(index, 1, newMessage)
                  }
                }
              }

              // 结果输出：追加到同一个主消息框（不换框）
              else if (messageType === 'result' || messageType === 'final') {
                if (currentMainMessageIndex.value !== -1) {
                  // 追加到当前主消息框，添加换行分隔 - 必须创建新对象触发更新
                  const index = currentMainMessageIndex.value
                  const currentMessage = messages.value[index]
                  if (currentMessage) {
                    // 如果之前是思考过程，添加分隔符
                    const separator = currentMessage.message.endsWith('\n') ? '' : '\n\n'
                    // 关键：创建新对象触发 Vue 响应式更新
                    const newMessage = {
                      ...currentMessage,
                      message: currentMessage.message + separator + parsedData.message
                    }
                    // 使用 splice 替换元素，确保 Vue 检测到变化
                    messages.value.splice(index, 1, newMessage)
                  }
                } else {
                  // 如果没有主消息框，创建新的
                  messages.value.push(parsedData)
                  currentMainMessageIndex.value = messages.value.length - 1
                }
              }

              // 错误信息：追加到同一个主消息框
              else if (messageType === 'error') {
                if (currentMainMessageIndex.value !== -1) {
                  const index = currentMainMessageIndex.value
                  const currentMessage = messages.value[index]
                  if (currentMessage) {
                    const separator = currentMessage.message.endsWith('\n') ? '' : '\n\n'
                    // 关键：创建新对象触发 Vue 响应式更新
                    const newMessage = {
                      ...currentMessage,
                      message: currentMessage.message + separator + `❌ ${parsedData.message}`
                    }
                    // 使用 splice 替换元素，确保 Vue 检测到变化
                    messages.value.splice(index, 1, newMessage)
                  }
                } else {
                  messages.value.push(parsedData)
                  currentMainMessageIndex.value = messages.value.length - 1
                }
              }

              // 状态信息：追加到同一个主消息框（不换框）
              else if (messageType === 'status') {
                if (currentMainMessageIndex.value !== -1) {
                  const index = currentMainMessageIndex.value
                  const currentMessage = messages.value[index]
                  if (currentMessage) {
                    const separator = currentMessage.message.endsWith('\n') ? '' : '\n'
                    // 关键：创建新对象触发 Vue 响应式更新
                    const newMessage = {
                      ...currentMessage,
                      message: currentMessage.message + separator + parsedData.message
                    }
                    // 使用 splice 替换元素，确保 Vue 检测到变化
                    messages.value.splice(index, 1, newMessage)
                  }
                } else {
                  // 如果没有主消息框，创建新的（理论上不会发生）
                  messages.value.push(parsedData)
                  currentMainMessageIndex.value = messages.value.length - 1
                }
              }

              // 其他类型（连接、结束）：创建独立消息框
              else if (messageType === 'connection' || messageType === 'end') {
                messages.value.push(parsedData)
              }
            }

            // 立即滚动到最新消息
            await nextTick()
            scrollToLatestMessage()

            // 更新智能体状态
            updateAgentFromMessage(parsedData)

            // 如果收到结束信号，停止加载并重置主消息索引
            if (parsedData.type === 'end' || parsedData.type === 'final') {
              loading.value = false
              updateAgentStatus('idle')
              currentMainMessageIndex.value = -1 // 请求完成，重置索引
            }
          } catch (err) {
            console.error('解析 SSE 数据错误:', err, line)
          }
        }
      }

      buffer = lastLine
    }

  } catch (err) {
    console.error('获取流式数据错误:', err)
    error.value = `获取数据失败: ${err.message}`
    loading.value = false
    updateAgentStatus('idle')
    currentMainMessageIndex.value = -1 // 出错时也要重置索引
  }
}

/**
 * 根据消息更新智能体状态（匹配官方教程结构）
 */
const updateAgentFromMessage = (message) => {
  const agentName = message.agent || '系统'
  const agent = agentTeam.find(a => a.name === agentName)

  if (agent) {
    // 根据消息类型更新状态
    if (message.type === 'status') {
      agent.status = 'active'
      agent.active = true
      currentActiveAgent.value = agentName
    } else if (message.type === 'result' || message.type === 'final') {
      agent.status = 'completed'
      agent.active = false
      // 如果是最终答案，清除活跃智能体
      if (message.type === 'final') {
        currentActiveAgent.value = ''
      }
    } else if (message.type === 'error') {
      agent.status = 'idle'
      agent.active = false
      currentActiveAgent.value = ''
    }
  } else if (message.type === 'end') {
    // 流程结束，所有智能体恢复空闲状态
    agentTeam.forEach(a => {
      a.status = 'idle'
      a.active = false
    })
    currentActiveAgent.value = ''
  }
}

/**
 * 更新所有智能体状态
 */
const updateAgentStatus = (status) => {
  agentTeam.forEach(agent => {
    agent.status = status
    agent.active = status === 'active'
  })
}


// 组件卸载时清理资源
import { onUnmounted } from 'vue'
onUnmounted(() => {
  // 清理资源
})
</script>

<style>
:root {
  --primary-color: #667eea;
  --primary-dark: #5568d3;
  --background: #ffffff;
  --surface: #f5f8fa;
  --text-primary: #14171a;
  --text-secondary: #657786;
  --border-color: #e1e8ed;
  --shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: var(--background);
  color: var(--text-primary);
}

.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* 顶部导航栏 */
.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: var(--shadow);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 32px;
}

.logo h1 {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
}

.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* 流式状态指示器 */
.streaming-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  font-size: 14px;
  color: white;
  white-space: nowrap;
}

.streaming-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #4CAF50;
  animation: streamingPulse 1.5s infinite;
}

.streaming-text {
  font-weight: 500;
}

@keyframes streamingPulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.2);
  }
}

.icon-button {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  color: white;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 16px;
}

.icon-button:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}

/* 主体内容 */
.app-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 侧边栏 */
.sidebar {
  width: 280px;
  background: var(--surface);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
}

.sidebar-collapsed {
  width: 0;
  overflow: hidden;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-header h3 {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.new-chat-btn {
  width: 100%;
  padding: 12px;
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.new-chat-btn:hover {
  background: var(--primary-dark);
  transform: translateY(-2px);
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.conversation-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 8px;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conversation-item:hover {
  background: var(--background);
}

.conversation-item.active {
  background: var(--primary-color);
  color: white;
}

.conversation-title {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-time {
  font-size: 12px;
  opacity: 0.7;
}

.agent-status {
  padding: 20px;
  border-top: 1px solid var(--border-color);
}

.agent-status h4 {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.agent-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 60vh;
  overflow-y: auto;
}

.layer-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.layer-header {
  padding: 6px 10px;
  background: rgba(102, 126, 234, 0.15);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #667eea;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.layer-section:first-child .layer-header {
  margin-top: 0;
}

.team-group {
  margin-left: 8px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 6px;
  border-left: 3px solid #667eea;
}

.team-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding: 4px 8px;
  background: rgba(102, 126, 234, 0.08);
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #667eea;
}

.team-icon {
  font-size: 16px;
}

.team-children {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-left: 16px;
}

.child-agent {
  padding: 6px 8px;
  background: white;
  border: 1px solid rgba(102, 126, 234, 0.2);
  border-radius: 4px;
}

.child-agent .agent-avatar {
  font-size: 16px;
}

.child-agent .agent-name {
  font-size: 12px;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.3s ease;
}

.agent-item:hover {
  background: var(--background);
}

.agent-avatar {
  font-size: 20px;
}

.agent-name {
  flex: 1;
  font-size: 14px;
}

.agent-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}

.agent-status-dot.active {
  background: #4CAF50;
  animation: pulse 2s infinite;
}

.agent-status-dot.completed {
  background: #2196F3;
}

.agent-status-dot.idle {
  background: #ccc;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 聊天区域 */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--background);
}

/* 错误模态框 */
.error-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.error-content {
  background: var(--background);
  padding: 32px;
  border-radius: 12px;
  max-width: 500px;
  text-align: center;
  box-shadow: var(--shadow);
}

.error-content h3 {
  color: #c62828;
  margin-bottom: 16px;
  font-size: 20px;
}

.error-content p {
  color: var(--text-primary);
  margin-bottom: 24px;
  line-height: 1.6;
}

.error-close-button {
  padding: 12px 32px;
  background: #c62828;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.3s ease;
}

.error-close-button:hover {
  background: #b71c1c;
}

/* 树形结构样式 */
.agent-tree {
  padding: 16px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', 'Droid Sans Mono', monospace;
}

.tree-level {
  margin-bottom: 4px;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background 0.2s ease;
}

.tree-node:hover {
  background: rgba(102, 126, 234, 0.1);
}

.root-node {
  background: rgba(102, 126, 234, 0.15);
  margin-bottom: 8px;
}

.team-node {
  margin-left: 0;
}

.child-node {
  margin-left: 0;
}

.branch-connector,
.leaf-connector {
  color: var(--text-secondary);
  font-size: 14px;
  white-space: pre;
  font-weight: 500;
}

.node-icon {
  font-size: 16px;
}

.node-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.tree-branch {
  margin-bottom: 4px;
}

.tree-children {
  margin-left: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .sidebar {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 200;
    box-shadow: var(--shadow);
  }

  .sidebar-collapsed {
    transform: translateX(-100%);
  }

  .app-header {
    padding: 12px 16px;
  }

  .logo h1 {
    font-size: 16px;
  }

  .header-right {
    gap: 8px;
  }
}
</style>
