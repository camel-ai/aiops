<template>
  <div class="project-add">
    <h2>新增项目</h2>
    <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" class="project-form">
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入项目名称"></el-input>
      </el-form-item>
      <el-form-item label="项目描述" prop="description">
        <el-input v-model="form.description" type="textarea" rows="4" placeholder="请输入项目描述"></el-input>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="submitForm" :loading="loading">提交</el-button>
        <el-button @click="resetForm">重置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

export default {
  name: 'ProjectAdd',
  setup() {
    const store = useStore()
    const router = useRouter()
    const formRef = ref(null)
    const loading = ref(false)

    const form = reactive({
      name: '',
      description: ''
    })

    const rules = {
      name: [
        { required: true, message: '请输入项目名称', trigger: 'blur' },
        { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
      ],
      description: [
        { required: true, message: '请输入项目描述', trigger: 'blur' }
      ]
    }

    const submitForm = async () => {
      if (!formRef.value) return
      
      await formRef.value.validate(async (valid) => {
        if (valid) {
          loading.value = true
          try {
            await store.dispatch('createProject', form)
            ElMessage.success('项目创建成功')
            router.push('/workspace/project/list')
          } catch (error) {
            ElMessage.error(error.response?.data?.error || '创建项目失败，请稍后重试')
          } finally {
            loading.value = false
          }
        }
      })
    }

    const resetForm = () => {
      if (formRef.value) {
        formRef.value.resetFields()
      }
    }

    return {
      form,
      rules,
      formRef,
      loading,
      submitForm,
      resetForm
    }
  }
}
</script>

<style scoped>
.project-add {
  padding: 20px;
}

.project-form {
  max-width: 600px;
}
</style>
