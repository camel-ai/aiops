<template>
  <div class="change-cloud">
    <h2>变更云选择</h2>
    <div class="cloud-grid">
      <div v-for="cloud in cloudProviders" :key="cloud.id" class="cloud-card">
        <el-card :body-style="{ padding: '0px' }" shadow="hover">
          <div class="cloud-logo">
            <img :src="cloud.logo" :alt="cloud.name">
          </div>
          <div class="cloud-name">{{ cloud.name }}</div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useStore } from 'vuex'

export default {
  name: 'ChangeCloud',
  setup() {
    const store = useStore()
    const cloudProviders = ref([])
    
    // 获取云服务提供商列表
    const fetchClouds = async () => {
      try {
        // 从store获取云列表
        const clouds = await store.dispatch('fetchClouds')
        cloudProviders.value = clouds
      } catch (error) {
        console.error('获取云服务提供商列表失败:', error)
        // 如果获取失败，使用默认数据（会从store获取备用数据）
      }
    }
    
    // 组件挂载时获取云列表
    onMounted(fetchClouds)

    return {
      cloudProviders
    }
  }
}
</script>

<style scoped>
.change-cloud {
  padding: 20px;
}

.cloud-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.cloud-card {
  transition: transform 0.3s;
  cursor: pointer;
}

.cloud-card:hover {
  transform: translateY(-5px);
}

.cloud-logo {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background-color: #f5f7fa;
}

.cloud-logo img {
  max-width: 100%;
  max-height: 80px;
  object-fit: contain;
}

.cloud-name {
  padding: 10px;
  text-align: center;
  font-weight: bold;
}
</style>
