import { createStore } from 'vuex'
import axios from 'axios'

// 从JWT令牌中解析用户信息的工具函数
const parseJwtToken = (token) => {
  try {
    // JWT令牌由三部分组成，用.分隔，第二部分是payload
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

export default createStore({
  state: {
    user: null,
    token: localStorage.getItem('token') || '',
    projects: [],
    clouds: [],
    selectedProject: null,
    selectedCloud: null
  },
  getters: {
    isAuthenticated: state => !!state.token,
    currentUser: state => state.user,
    allProjects: state => state.projects,
    allClouds: state => state.clouds,
    selectedProject: state => state.selectedProject,
    selectedCloud: state => state.selectedCloud
  },
  mutations: {
    setToken(state, token) {
      state.token = token
      localStorage.setItem('token', token)
    },
    setUser(state, user) {
      state.user = user
    },
    clearAuth(state) {
      state.token = ''
      state.user = null
      localStorage.removeItem('token')
    },
    setProjects(state, projects) {
      state.projects = projects
    },
    setClouds(state, clouds) {
      state.clouds = clouds
    },
    setSelectedProject(state, projectId) {
      state.selectedProject = projectId
    },
    setSelectedCloud(state, cloudId) {
      state.selectedCloud = cloudId
    }
  },
  actions: {
    // 用户登录
    async login({ commit }, credentials) {
      try {
        const response = await axios.post('/api/login', credentials)
        const { token, user } = response.data
        
        // 保存token到store和localStorage
        commit('setToken', token)
        
        // 确保user对象包含所有必要字段
        if (user) {
          // 直接使用返回的用户对象
          commit('setUser', user)
          console.log('登录成功，用户信息:', user)
        } else if (token) {
          // 如果没有返回user对象但有token，尝试从token解析
          try {
            const payload = parseJwtToken(token);
            if (payload) {
              const parsedUser = {
                id: payload.user_id,
                username: payload.username || credentials.username
              };
              commit('setUser', parsedUser)
              console.log('从JWT解析用户信息:', parsedUser)
            } else {
              // 至少保存用户名
              commit('setUser', { username: credentials.username })
              console.log('使用登录凭据作为用户信息')
            }
          } catch (err) {
            console.error('解析JWT失败:', err)
            // 至少保存用户名
            commit('setUser', { username: credentials.username })
          }
        }
        
        return response.data.user || { username: credentials.username }
      } catch (error) {
        console.error('登录请求错误:', error)
        // 检查是否为CORS错误
        if (error.message && error.message.includes('NetworkError') || 
            (error.response && error.response.status === 0)) {
          throw new Error('跨域请求被拒绝，请检查网络连接或联系管理员')
        }
        throw error
      }
    },
    
    // 用户注册
    async register(_, userData) {
      try {
        // userData 现在包含 username, password, department
        await axios.post('/api/register', userData)
        return true
      } catch (error) {
        console.error('注册请求错误:', error)
        // 检查是否为CORS错误
        if (error.message && error.message.includes('NetworkError') || 
            (error.response && error.response.status === 0)) {
          throw new Error('跨域请求被拒绝，请检查网络连接或联系管理员')
        }
        throw error
      }
    },
    
    // 用户登出
    logout({ commit }) {
      commit('clearAuth')
    },
    
    // 获取项目列表
    async fetchProjects({ commit }) {
      try {
        const token = localStorage.getItem('token')
        const response = await axios.get('/api/projects', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        
        commit('setProjects', response.data.projects || [])
        return response.data.projects || []
      } catch (error) {
        console.error('获取项目列表错误:', error)
        if (error.message && error.message.includes('NetworkError') || 
            (error.response && error.response.status === 0)) {
          throw new Error('跨域请求被拒绝，请检查网络连接或联系管理员')
        }
        return []
      }
    },
    
    // 创建新项目
    async createProject({ dispatch }, projectData) {
      try {
        const token = localStorage.getItem('token')
        const response = await axios.post('/api/projects', projectData, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        
        // 返回新创建的项目信息
        const newProject = response.data.project || response.data
        
        // 刷新项目列表
        dispatch('fetchProjects')
        
        return newProject
      } catch (error) {
        console.error('创建项目错误:', error)
        if (error.message && error.message.includes('NetworkError') || 
            (error.response && error.response.status === 0)) {
          throw new Error('跨域请求被拒绝，请检查网络连接或联系管理员')
        }
        throw error
      }
    },
    
    // 获取云列表
    async fetchClouds({ commit }) {
      try {
        // 从API获取云服务提供商列表
        const response = await axios.get('/api/clouds')
        
        if (response.data && response.data.success) {
          const clouds = response.data.clouds || []
          
          // 格式化数据以适应前端需要的结构
          const formattedClouds = clouds.map(cloud => ({
            id: cloud.id,
            name: cloud.name,
            provider: cloud.provider,
            logo: cloud.logo,
            regions: cloud.regions || []
          }))
          
          commit('setClouds', formattedClouds)
          return formattedClouds
        } else {
          console.error('获取云列表API返回错误:', response.data.error || '未知错误')
          throw new Error(response.data.error || '获取云列表失败')
        }
      } catch (error) {
        console.error('获取云列表错误:', error)
        if (error.message && error.message.includes('NetworkError') || 
            (error.response && error.response.status === 0)) {
          throw new Error('跨域请求被拒绝，请检查网络连接或联系管理员')
        }
        
        // 如果API请求失败，返回默认数据作为备用
        const defaultClouds = [
          { id: 1, name: 'AWS', provider: 'Amazon Web Services', logo: 'https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg' },
          { id: 2, name: 'Azure', provider: 'Microsoft Azure', logo: 'https://upload.wikimedia.org/wikipedia/commons/a/a8/Microsoft_Azure_Logo.svg' },
          { id: 3, name: '阿里云', provider: 'Alibaba', logo: 'https://upload.wikimedia.org/wikipedia/commons/b/b3/AlibabaCloudLogo.svg' },
          { id: 4, name: '华为云', provider: 'Huawei', logo: 'https://res-static.hc-cdn.cn/cloudbu-site/china/zh-cn/wangxue/header/logo.svg' }
        ]
        
        commit('setClouds', defaultClouds)
        return defaultClouds
      }
    },
    
    // 设置选定项目
    setSelectedProject({ commit }, projectId) {
      commit('setSelectedProject', projectId)
    },
    
    // 设置选定云
    setSelectedCloud({ commit }, cloudId) {
      commit('setSelectedCloud', cloudId)
    },
    
    // 发送聊天消息
    async sendChatMessage(_, message) {
      try {
        const response = await axios.post('/chat', { message })
        return response.data.reply
      } catch (error) {
        console.error('发送聊天消息错误:', error)
        if (error.message && error.message.includes('NetworkError') || 
            (error.response && error.response.status === 0)) {
          throw new Error('跨域请求被拒绝，请检查网络连接或联系管理员')
        }
        throw error
      }
    }
  }
})
