/**
 * Vue 3 应用入口文件
 *
 * 功能：
 * 1. 导入 Vue 框架和根组件
 * 2. 配置 Vue 应用实例
 * 3. 挂载到 DOM
 */

import { createApp } from 'vue'
import App from './App.vue'

// 创建 Vue 应用实例
const app = createApp(App)

// 全局错误处理
app.config.errorHandler = (err, instance, info) => {
  console.error('全局错误:', err)
  console.error('组件实例:', instance)
  console.error('错误信息:', info)
}

// 性能监控（开发环境）
if (import.meta.env.DEV) {
  app.config.performance = true
}

// 挂载应用
app.mount('#app')

console.log('🚀 Vue 应用已启动')
