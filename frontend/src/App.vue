<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script>
import { useStore } from 'vuex'
import { onMounted } from 'vue'
import axios from 'axios'

export default {
  name: 'App',
  setup() {
    const store = useStore()

    // 从JWT令牌中解析用户信息
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

    // 页面加载时验证token并获取用户信息
    onMounted(async () => {
      const token = localStorage.getItem('token')
      if (token) {
        try {
          // 首先尝试从token直接解析用户信息
          const payload = parseJwtToken(token);
          if (payload && payload.username) {
            // 构建基本用户信息对象
            const user = {
              id: payload.user_id,
              username: payload.username
            };
            console.log('从JWT中解析到用户信息:', user);
            store.commit('setUser', user);
          } else {
            // 如果无法从token解析，尝试API请求
            try {
              const response = await axios.get('/api/user/info', {
                headers: {
                  'Authorization': `Bearer ${token}`
                }
              });
              if (response.data && response.data.user) {
                store.commit('setUser', response.data.user);
                console.log('从API获取到用户信息:', response.data.user);
              }
            } catch (apiError) {
              console.error('API获取用户信息失败:', apiError);
              // 即使API失败，如果我们从JWT中获取了部分信息，也不要登出用户
              if (!store.state.user && payload) {
                const fallbackUser = { username: payload.username || '用户' };
                store.commit('setUser', fallbackUser);
                console.log('使用JWT中的基本信息:', fallbackUser);
              } else if (!store.state.user) {
                store.dispatch('logout');
              }
            }
          }
        } catch (error) {
          console.error('处理用户信息失败:', error);
          // 如果获取失败（如token过期），清除auth状态
          store.dispatch('logout');
        }
      }
    })
  }
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
  font-family: Arial, sans-serif;
}

#app {
  height: 100vh;
}
</style>
