import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import './body-parts.css'
import './eye/eye.css'
import './eye/chat.css'
import './eye/care.css'
import './twin/twin.css'
import './readability.css'
import './theme.css'

try {
  const stored = localStorage.getItem('humantwin.theme')
  document.documentElement.dataset.theme = stored === 'dark' || stored === 'light' ? stored : matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
} catch { document.documentElement.dataset.theme = 'light' }

createApp(App).mount('#app')
