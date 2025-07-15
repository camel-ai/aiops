<template>
  <div class="login-container">
    <el-card class="login-card">
      <div class="logo-container">
        <img src="../assets/images/logo.png" alt="Camel" class="logo">
        <h1>Aiops Platform</h1>
      </div>
      
      <el-tabs v-model="activeTab" class="login-tabs">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" :rules="loginRules" ref="loginFormRef" label-position="top">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="loginForm.username" placeholder="请输入用户名"></el-input>
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="请输入密码"></el-input>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleLogin" :loading="loading" class="submit-btn">登录</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="注册" name="register">
          <el-form :model="registerForm" :rules="registerRules" ref="registerFormRef" label-position="top">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="registerForm.username" placeholder="请输入用户名"></el-input>
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="registerForm.password" type="password" placeholder="请输入密码"></el-input>
            </el-form-item>
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input v-model="registerForm.confirmPassword" type="password" placeholder="请再次输入密码"></el-input>
            </el-form-item>
            <el-form-item label="部门" prop="department">
              <el-input v-model="registerForm.department" placeholder="请输入部门"></el-input>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleRegister" :loading="loading" class="submit-btn">注册</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

export default {
  name: 'LoginView',
  setup() {
    const store = useStore()
    const router = useRouter()
    const activeTab = ref('login')
    const loading = ref(false)
    const loginFormRef = ref(null)
    const registerFormRef = ref(null)

    // 登录表单
    const loginForm = reactive({
      username: '',
      password: ''
    })

    // 注册表单
    const registerForm = reactive({
      username: '',
      password: '',
      confirmPassword: '',
      department: ''
    })

    // 登录表单验证规则
    const loginRules = {
      username: [
        { required: true, message: '请输入用户名', trigger: 'blur' }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' }
      ]
    }

    // 注册表单验证规则
    const registerRules = {
      username: [
        { required: true, message: '请输入用户名', trigger: 'blur' }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' }
      ],
      confirmPassword: [
        { required: true, message: '请再次输入密码', trigger: 'blur' },
        { 
          validator: (rule, value, callback) => {
            if (value !== registerForm.password) {
              callback(new Error('两次输入密码不一致'))
            } else {
              callback()
            }
          }, 
          trigger: 'blur' 
        }
      ],
      department: [
        { required: true, message: '请输入部门', trigger: 'blur' }
      ]
    }

    // 登录处理
    const handleLogin = async () => {
      if (!loginFormRef.value) return
      
      await loginFormRef.value.validate(async (valid) => {
        if (valid) {
          try {
            loading.value = true
            await store.dispatch('login', loginForm)
            ElMessage.success('登录成功')
            router.push('/workspace/project/list')
          } catch (error) {
            console.error('登录错误:', error)
            if (error.message && error.message.includes('跨域请求被拒绝')) {
              ElMessage.error(error.message)
            } else {
              ElMessage.error(error.response?.data?.error || '登录失败，请检查用户名和密码')
            }
          } finally {
            loading.value = false
          }
        }
      })
    }

    // 注册处理
    const handleRegister = async () => {
      if (!registerFormRef.value) return
      
      await registerFormRef.value.validate(async (valid) => {
        if (valid) {
          try {
            loading.value = true
            const userData = {
              username: registerForm.username,
              password: registerForm.password,
              department: registerForm.department
            }
            
            await store.dispatch('register', userData)
            ElMessage.success('注册成功，请登录')
            activeTab.value = 'login'
            loginForm.username = registerForm.username
            loginForm.password = registerForm.password
          } catch (error) {
            console.error('注册错误:', error)
            if (error.message && error.message.includes('跨域请求被拒绝')) {
              ElMessage.error(error.message)
            } else {
              ElMessage.error(error.response?.data?.error || '注册失败，请稍后重试')
            }
          } finally {
            loading.value = false
          }
        }
      })
    }

    return {
      activeTab,
      loading,
      loginForm,
      registerForm,
      loginRules,
      registerRules,
      loginFormRef,
      registerFormRef,
      handleLogin,
      handleRegister
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f5f7fa;
}

.login-card {
  width: 450px;
  padding: 20px;
}

.logo-container {
  text-align: center;
  margin-bottom: 20px;
}

.logo {
  height: 60px;
  margin-bottom: 10px;
}

.login-tabs {
  margin-top: 20px;
}

.submit-btn {
  width: 100%;
}
</style>

/* eslint-disable */
