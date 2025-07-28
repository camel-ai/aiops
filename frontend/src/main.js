import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import router from './router'
import store from './store'
import axios from 'axios'

// 配置axios默认URL和凭证
axios.defaults.baseURL = ''
axios.defaults.withCredentials = true

// 添加请求拦截器，自动添加token到请求头
axios.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 从JWT令牌中解析用户信息的工具函数
const parseJwtToken = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));

    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('解析JWT令牌失败:', error);
    return null;
  }
};

// 初始化store中的用户信息
const initializeUserState = () => {
  const token = localStorage.getItem('token');
  if (token) {
    // 设置token
    store.commit('setToken', token);
    
    // 尝试从token解析用户信息
    const payload = parseJwtToken(token);
    if (payload && payload.username) {
      const user = {
        id: payload.user_id,
        username: payload.username
      };
      store.commit('setUser', user);
      console.log('应用启动: 从JWT恢复用户会话', user);
    }
  }
};

// 在应用启动时初始化用户状态
initializeUserState();

const app = createApp(App)

// 注册所有Element Plus图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)
app.use(router)
app.use(store)

app.mount('#app')
