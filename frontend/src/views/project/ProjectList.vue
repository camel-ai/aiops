<template>
  <div class="project-list">
    <el-table :data="projects" style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="项目名称" />
      <el-table-column prop="description" label="项目描述" />
      <el-table-column prop="created_at" label="创建时间">
        <template #default="scope">
          {{ formatDate(scope.row.created_at) }}
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useStore } from 'vuex'
import { ElMessage } from 'element-plus'

export default {
  name: 'ProjectList',
  setup() {
    const store = useStore()
    const projects = ref([])
    const loading = ref(false)

    // 格式化日期
    const formatDate = (dateString) => {
      const date = new Date(dateString)
      return date.toLocaleString()
    }

    // 获取项目列表
    const fetchProjects = async () => {
      loading.value = true
      try {
        const result = await store.dispatch('fetchProjects')
        projects.value = result
      } catch (error) {
        ElMessage.error('获取项目列表失败')
      } finally {
        loading.value = false
      }
    }

    onMounted(() => {
      fetchProjects()
    })

    return {
      projects,
      loading,
      formatDate
    }
  }
}
</script>

<style scoped>
.project-list {
  padding: 20px;
}
</style>
