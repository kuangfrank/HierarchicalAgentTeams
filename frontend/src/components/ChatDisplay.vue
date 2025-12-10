<template>
  <div class="chat-display">
    <div class="messages-container" ref="messagesContainer">
      <!-- 欢迎消息（首次访问时显示） -->
      <div v-if="filteredMessages.length === 0 && !loading" class="welcome-message">
        <div class="welcome-icon">🤖</div>
        <h2>欢迎使用分层智能体团队系统</h2>
        <p>我是一个由多个专业智能体组成的团队</p>
        <p class="welcome-tip">请在下方输入您的任务，系统将展示团队的协作结果</p>
      </div>

      <!-- 消息列表（过滤用户消息） -->
      <div
        v-for="(message, index) in filteredMessages"
        :key="`${message.type}-${index}-${message.timestamp || Date.now()}`"
        :class="['message', `message-${message.type}`]"
      >
        <!-- 连接消息 -->
        <div v-if="message.type === 'connection'" class="message-connection">
          <div class="agent-avatar">🔌</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">{{ message.message }}</div>
          </div>
        </div>

        <!-- 状态消息 -->
        <div v-else-if="message.type === 'status'" class="message-status">
          <div class="agent-avatar">👤</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">{{ message.message }}</div>
          </div>
        </div>

        <!-- 任务分解消息 -->
        <div v-else-if="message.type === 'decomposition'" class="message-decomposition">
          <div class="agent-avatar">📋</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">{{ message.message }}</div>
            <div class="subtasks" v-if="message.subtasks">
              <h4>子任务列表：</h4>
              <ul>
                <li v-for="(task, idx) in message.subtasks" :key="idx">
                  <strong>{{ task.title }}</strong> - {{ task.requirement }}
                </li>
              </ul>
            </div>
          </div>
        </div>

        <!-- 任务分配消息 -->
        <div v-else-if="message.type === 'assignment'" class="message-assignment">
          <div class="agent-avatar">🎯</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">{{ message.message }}</div>
            <div class="current-task" v-if="message.current_task">
              <strong>当前任务：{{ message.current_task.title }}</strong>
            </div>
          </div>
        </div>

        <!-- 执行过程消息 -->
        <div v-else-if="message.type === 'execution'" class="message-execution">
          <div class="agent-avatar">⚙️</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">{{ message.message }}</div>
          </div>
        </div>

        <!-- 思考过程消息（流式输出） -->
        <div v-else-if="message.type === 'thinking'" class="message-thinking">
          <div class="agent-avatar">💭</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text thinking-content">
              {{ message.message }}
              <span v-if="message.delta" class="cursor">|</span>
            </div>
          </div>
        </div>

        <!-- 结果消息 -->
        <div v-else-if="message.type === 'result'" class="message-result">
          <div class="agent-avatar">✅</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">
              <pre>{{ message.message }}</pre>
            </div>
          </div>
        </div>

        <!-- 汇总消息 -->
        <div v-else-if="message.type === 'aggregation'" class="message-aggregation">
          <div class="agent-avatar">🔄</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">{{ message.message }}</div>
          </div>
        </div>

        <!-- 最终答案 -->
        <div v-else-if="message.type === 'final'" class="message-final">
          <div class="agent-avatar">🎉</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="final-answer">
              <pre>{{ message.message }}</pre>
            </div>
          </div>
        </div>

        <!-- 用户消息 -->
        <div v-else-if="message.type === 'user'" class="message-user">
          <div class="agent-avatar">👤</div>
          <div class="message-content user-message">
            <div class="message-text">{{ message.message }}</div>
          </div>
        </div>

        <!-- 错误消息 -->
        <div v-else-if="message.type === 'error'" class="message-error">
          <div class="agent-avatar">❌</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">{{ message.message }}</div>
          </div>
        </div>

        <!-- 结束消息 -->
        <div v-else-if="message.type === 'end'" class="message-end">
          <div class="agent-avatar">✅</div>
          <div class="message-content">
            <div class="agent-name">{{ message.agent }}</div>
            <div class="message-text">{{ message.message }}</div>
          </div>
        </div>
      </div>

      <!-- 加载指示器 -->
      <div v-if="loading" class="loading-indicator">
        <div class="typing-animation">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="loading-text">智能体团队正在思考中...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 聊天显示组件
 *
 * 功能：
 * 1. 实时展示智能体团队的流式输出
 * 2. 不同类型消息的差异化展示
 * 3. 自动滚动到最新消息
 * 4. 时间戳格式化
 * 5. 加载状态指示器
 * 6. 欢迎消息展示
 */

import { ref, watch, nextTick, computed } from 'vue'

// Props 定义
const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Refs
const messagesContainer = ref(null)

/**
 * 过滤后的消息列表（隐藏用户消息）
 */
const filteredMessages = computed(() => {
  return props.messages.filter(message => message.type !== 'user')
})

/**
 * 滚动到最新消息
 */
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听消息变化，自动滚动
watch(
  () => props.messages.length,
  () => {
    scrollToBottom()
  }
)

// 监听加载状态变化
watch(
  () => props.loading,
  (newLoading) => {
    if (!newLoading) {
      scrollToBottom()
    }
  }
)
</script>

<style scoped>
.chat-display {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--background);
  min-height: 0; /* 确保可以正确收缩 */
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  scroll-behavior: smooth;
  will-change: scroll-position;
  -webkit-overflow-scrolling: touch;
  /* 优化滚动性能 */
  contain: layout style paint;
}

/* 欢迎消息样式 */
.welcome-message {
  text-align: center;
  padding: 60px 20px;
  color: #657786;
}

.welcome-icon {
  font-size: 80px;
  margin-bottom: 20px;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}

.welcome-message h2 {
  color: #14171a;
  font-size: 28px;
  margin-bottom: 20px;
}

.welcome-message p {
  font-size: 16px;
  margin-bottom: 12px;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.welcome-tip {
  margin-top: 30px;
  font-size: 14px;
  color: #1da1f2;
  font-weight: 500;
  text-align: center;
}

/* 消息通用样式 */
.message {
  margin-bottom: 20px;
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-content {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  flex: 1; /* 填满剩余空间，与输入框对齐 */
  max-width: none; /* 移除 max-width 限制 */
}

.agent-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin-bottom: 8px;
}

.agent-name {
  font-weight: 600;
  color: #14171a;
  margin-bottom: 8px;
  font-size: 14px;
}

.message-text {
  color: #14171a;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message-text pre {
  background: #f5f8fa;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
  font-size: 14px;
  line-height: 1.5;
}

/* 不同消息类型的样式 */
.message-connection {
  display: flex;
  gap: 12px;
  opacity: 0.8;
}

.message-connection .agent-avatar {
  background: #e8f5e9;
}

.message-status {
  display: flex;
  gap: 12px;
}

.message-status .agent-avatar {
  background: #e1e8ed;
}

.message-decomposition {
  display: flex;
  gap: 12px;
}

.message-decomposition .agent-avatar {
  background: #e8f4fd;
}

.message-decomposition .subtasks {
  margin-top: 12px;
}

.message-decomposition .subtasks h4 {
  color: #1da1f2;
  font-size: 14px;
  margin-bottom: 8px;
}

.message-decomposition .subtasks ul {
  margin: 0;
  padding-left: 20px;
}

.message-decomposition .subtasks li {
  margin-bottom: 6px;
  font-size: 14px;
  color: #14171a;
}

.message-assignment {
  display: flex;
  gap: 12px;
}

.message-assignment .agent-avatar {
  background: #fff3e0;
}

.message-assignment .current-task {
  background: #fff3e0;
  padding: 8px 12px;
  border-radius: 6px;
  margin-top: 8px;
  font-size: 14px;
}

.message-execution {
  display: flex;
  gap: 12px;
}

.message-execution .agent-avatar {
  background: #f0e6ff;
}

.message-thinking {
  display: flex;
  gap: 12px;
}

.message-thinking .agent-avatar {
  background: #e1f5fe;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.thinking-content {
  font-family: 'Courier New', monospace;
  color: #0277bd;
  background: #e1f5fe;
  padding: 12px;
  border-radius: 8px;
  border-left: 3px solid #0288d1;
}

.cursor {
  animation: blink 1s infinite;
  color: #0288d1;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.message-result {
  display: flex;
  gap: 12px;
}

.message-result .agent-avatar {
  background: #e8f5e9;
}

.message-aggregation {
  display: flex;
  gap: 12px;
}

.message-aggregation .agent-avatar {
  background: #fff9c4;
}

.message-final {
  display: flex;
  gap: 12px;
}

.message-final .agent-avatar {
  background: #1da1f2;
  color: white;
}

.message-final .final-answer {
  background: var(--surface);
  padding: 16px;
  border-radius: 8px;
  border-left: 4px solid #1da1f2;
  margin-top: 8px;
}

.message-user {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.message-user .agent-avatar {
  order: 2;
  background: #667eea;
  color: white;
}

.message-user .message-content {
  order: 1;
  background: #667eea;
  color: white;
}

.message-user .message-text {
  color: white;
}

.message-error {
  display: flex;
  gap: 12px;
}

.message-error .agent-avatar {
  background: #ffebee;
}

.message-error .message-text {
  color: #c62828;
}

/* 加载指示器 */
.loading-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 16px;
}

.typing-animation {
  display: flex;
  gap: 8px;
}

.typing-animation span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #1da1f2;
  animation: typing 1.4s infinite;
}

.typing-animation span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-animation span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-10px);
    opacity: 1;
  }
}

.loading-text {
  color: #657786;
  font-size: 14px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .messages-container {
    padding: 16px;
  }

  .message-content {
    /* 移动端保持适当的边距 */
    flex: 1;
    max-width: none;
  }

  .welcome-message {
    padding: 40px 16px;
  }

  .welcome-message h2 {
    font-size: 24px;
  }

  .welcome-icon {
    font-size: 60px;
  }
}
</style>
