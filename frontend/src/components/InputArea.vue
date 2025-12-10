<template>
  <div class="input-area">
    <div class="input-container">
      <textarea
        v-model="inputText"
        @keydown="handleKeydown"
        placeholder="请输入您的任务或问题..."
        :disabled="disabled"
        rows="3"
        class="task-input"
      ></textarea>
      <div class="button-group">
        <button
          @click="handleSubmit"
          :disabled="disabled || !inputText.trim()"
          class="send-button"
        >
          <span v-if="!loading">🚀 发送</span>
          <span v-else>⏳ 发送中...</span>
        </button>
        <button
          @click="handleClear"
          :disabled="disabled && !inputText"
          class="clear-button"
        >
          🗑️ 清空
        </button>
      </div>
    </div>
    <div class="input-tips">
      <span class="tip">💡 提示：按 Ctrl/Cmd + Enter 快速发送</span>
      <span class="char-count">{{ inputText.length }}/5000</span>
    </div>
  </div>
</template>

<script setup>
/**
 * 输入区域组件
 *
 * 功能：
 * 1. 接收用户输入的任务或问题
 * 2. 支持快捷键发送（Ctrl/Cmd + Enter）
 * 3. 字符计数和输入验证
 * 4. 发送和清空按钮交互
 * 5. 禁用状态管理（加载中时禁止输入）
 */

import { ref, watch, computed } from 'vue'

// Props 定义
const props = defineProps({
  loading: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

// Emits 定义
const emit = defineEmits(['submit', 'clear'])

// 响应式数据
const inputText = ref('')

// 计算属性：是否禁用输入
const isDisabled = computed(() => {
  return props.disabled || props.loading
})

// 监听输入文本变化，自动截断超长文本
watch(inputText, (newValue) => {
  if (newValue.length > 5000) {
    inputText.value = newValue.slice(0, 5000)
  }
})

/**
 * 处理表单提交
 */
const handleSubmit = () => {
  const text = inputText.value.trim()

  // 验证输入
  if (!text) {
    alert('请输入任务内容')
    return
  }

  if (text.length > 5000) {
    alert('任务内容过长（限制 5000 字符）')
    return
  }

  // 发送事件给父组件
  emit('submit', text)

  // 清空输入（可选，保持输入让用户参考）
  // inputText.value = ''
}

/**
 * 处理清空操作
 */
const handleClear = () => {
  inputText.value = ''
  emit('clear')
}

/**
 * 处理键盘事件（快捷键支持）
 * @param {KeyboardEvent} event - 键盘事件对象
 */
const handleKeydown = (event) => {
  // 支持 Ctrl/Cmd + Enter 快速发送
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    handleSubmit()
  }
}
</script>

<style scoped>
.input-area {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  flex-shrink: 0; /* 防止被压缩 */
}

.input-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-input {
  width: 100%;
  padding: 16px;
  border: 2px solid #e1e8ed;
  border-radius: 8px;
  font-size: 16px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.5;
  resize: vertical;
  min-height: 100px;
  transition: border-color 0.3s ease;
  box-sizing: border-box;
}

.task-input:focus {
  outline: none;
  border-color: #1da1f2;
  box-shadow: 0 0 0 3px rgba(29, 161, 242, 0.1);
}

.task-input:disabled {
  background-color: #f5f8fa;
  cursor: not-allowed;
  opacity: 0.6;
}

.button-group {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.send-button,
.clear-button {
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.send-button {
  background: linear-gradient(135deg, #1da1f2 0%, #0d8bd9 100%);
  color: white;
}

.send-button:hover:not(:disabled) {
  background: linear-gradient(135deg, #0d8bd9 0%, #1da1f2 100%);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(29, 161, 242, 0.3);
}

.send-button:disabled {
  background: #ccd6dd;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.clear-button {
  background: #f5f8fa;
  color: #657786;
  border: 1px solid #e1e8ed;
}

.clear-button:hover:not(:disabled) {
  background: #e1e8ed;
  color: #14171a;
}

.clear-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-tips {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  font-size: 14px;
  color: #657786;
}

.tip {
  display: flex;
  align-items: center;
  gap: 6px;
}

.char-count {
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .input-area {
    padding: 16px;
  }

  .task-input {
    font-size: 16px; /* 防止 iOS 自动缩放 */
  }

  .button-group {
    flex-direction: column;
  }

  .send-button,
  .clear-button {
    width: 100%;
    justify-content: center;
  }

  .input-tips {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
}
</style>
