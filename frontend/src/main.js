import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/theme.css'

const app = createApp(App)

// 全局异常兜底：组件渲染抛错时不再整页空白，而是显示可读的错误条
app.config.errorHandler = (err, _instance, info) => {
  console.error('[vue-error]', info, err)
  window.__vErr = `${info}: ${err?.message || err}`
  let bar = document.getElementById('__v_err_bar')
  if (!bar) {
    bar = document.createElement('div')
    bar.id = '__v_err_bar'
    bar.style.cssText =
      'position:fixed;left:0;right:0;top:0;z-index:99999;background:#c22f27;color:#fff;' +
      'padding:8px 14px;font:13px/1.6 system-ui;white-space:pre-wrap'
    document.body.appendChild(bar)
  }
  bar.textContent = `页面渲染异常（${info}）：${err?.message || err}`
}
window.addEventListener('unhandledrejection', (e) => {
  console.error('[unhandled-rejection]', e.reason)
})

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
for (const [name, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, comp)
}
app.mount('#app')
