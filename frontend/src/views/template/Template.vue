<template>
  <div class="template-container">
    <div class="template-header">
      <h2>模板管理</h2>
      <el-button 
        type="primary" 
        @click="addTemplate" 
        icon="Plus"
      >
        新增模板
      </el-button>
    </div>
    
    <div class="template-content">
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="3" animated />
      </div>
      
      <div v-else-if="templates.length === 0" class="empty-container">
        <el-empty description="暂无模板" />
        <el-button type="primary" @click="addTemplate">立即创建</el-button>
      </div>
      
      <div v-else class="template-list">
        <el-card 
          v-for="template in templates" 
          :key="template.id" 
          class="template-card"
          shadow="hover"
        >
          <div class="template-card-header">
            <h3>{{ template.template_name }}</h3>
            <div class="template-actions">
              <el-button 
                size="small" 
                type="primary" 
                text 
                @click="editTemplate(template.id)"
              >
                编辑
              </el-button>
              <el-button 
                size="small" 
                type="danger" 
                text 
                @click="confirmDelete(template)"
              >
                删除
              </el-button>
            </div>
          </div>
          
          <div class="template-image" @click="previewImage(template)">
            <img 
              v-if="template.topology_image" 
              :src="getImageUrl(template)" 
              :alt="template.template_name" 
              class="topology-image"
              @error="handleImageError"
            />
            <div v-else class="no-image">
              <el-icon><Picture /></el-icon>
              <span>无拓扑图</span>
            </div>
          </div>
          
          <div class="template-info">
            <p v-if="template.description">{{ template.description }}</p>
            <p v-else class="no-description">无描述</p>
            <div class="template-meta">
              <span class="date">创建时间: {{ formatDate(template.created_at) }}</span>
              <span class="creator" v-if="template.username">创建人: {{ template.username }}</span>
            </div>
          </div>
        </el-card>
      </div>
    </div>
    
    <!-- 图片预览对话框 -->
    <el-dialog
      v-model="imageDialogVisible"
      :title="currentImageTitle"
      width="80%"
      center
      destroy-on-close
      class="image-preview-dialog"
    >
      <div class="image-preview-container">
        <el-image
          :src="currentImage"
          fit="contain"
          :preview-src-list="[currentImage]"
          :initial-index="0"
          class="preview-image"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElDialog, ElImage } from 'element-plus'
import axios from 'axios'
import { Picture, Plus } from '@element-plus/icons-vue'

export default {
  name: 'TemplateView',
  components: {
    Picture,
    Plus
  },
  setup() {
    const router = useRouter()
    const templates = ref([])
    const loading = ref(true)
    const imageDialogVisible = ref(false)
    const currentImage = ref('')
    const currentImageTitle = ref('')
    
    // 获取所有模板
    const fetchTemplates = async () => {
      try {
        loading.value = true
        
        const token = localStorage.getItem('token')
        const response = await axios.get('/api/templates', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        
        if (response.data.success) {
          templates.value = response.data.templates || []
        } else {
          ElMessage.error(response.data.error || '获取模板失败')
        }
      } catch (error) {
        console.error('获取模板列表失败:', error)
        ElMessage.error('获取模板列表失败: ' + (error.message || '未知错误'))
      } finally {
        loading.value = false
      }
    }
    
    // 添加新模板
    const addTemplate = () => {
      router.push('/workspace/template/add')
    }
    
    // 编辑模板
    const editTemplate = (id) => {
      router.push(`/workspace/template/edit/${id}`)
    }
    
    // 预览图片
    const previewImage = (template) => {
      if (template.topology_image) {
        currentImage.value = getImageUrl(template)
        currentImageTitle.value = template.template_name
        imageDialogVisible.value = true
      } else {
        // 如果没有图片，点击时显示编辑页面
        viewTemplate(template.id)
      }
    }
    
    // 查看模板详情
    const viewTemplate = (id) => {
      router.push(`/workspace/template/edit/${id}`)
    }
    
    // 确认删除
    const confirmDelete = (template) => {
      ElMessageBox.confirm(
        `确定要删除模板 "${template.template_name}" 吗？此操作不可恢复。`,
        '提示',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }
      ).then(() => {
        deleteTemplate(template.id)
      }).catch(() => {})
    }
    
    // 删除模板
    const deleteTemplate = async (id) => {
      try {
        const token = localStorage.getItem('token')
        const response = await axios.post('/api/template/delete', 
          { template_id: id },
          {
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          }
        )
        
        if (response.data.success) {
          ElMessage.success('模板删除成功')
          // 刷新列表
          fetchTemplates()
        } else {
          ElMessage.error(response.data.error || '删除模板失败')
        }
      } catch (error) {
        console.error('删除模板失败:', error)
        ElMessage.error('删除模板失败: ' + (error.message || '未知错误'))
      }
    }
    
    // 获取模板图片URL
    const getImageUrl = (template) => {
      if (!template.topology_image) return null
      
      // 添加时间戳防止缓存
      const timestamp = new Date().getTime()
      return `/api/template/image?template_id=${template.id}&image_name=${template.topology_image}&t=${timestamp}`
    }
    
    // 处理图片加载错误
    const handleImageError = (event) => {
      event.target.src = '/placeholder.png' // 设置为默认图片
    }
    
    // 格式化日期
    const formatDate = (dateString) => {
      if (!dateString) return '未知'
      
      const date = new Date(dateString)
      return date.toLocaleString()
    }
    
    // 组件挂载时获取模板列表
    onMounted(() => {
      fetchTemplates()
    })
    
    return {
      templates,
      loading,
      imageDialogVisible,
      currentImage,
      currentImageTitle,
      addTemplate,
      editTemplate,
      viewTemplate,
      confirmDelete,
      getImageUrl,
      handleImageError,
      formatDate,
      previewImage
    }
  }
}
</script>

<style scoped>
.template-container {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.template-header h2 {
  margin: 0;
  font-size: 24px;
}

.template-content {
  flex: 1;
  overflow-y: auto;
}

.loading-container, .empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.empty-container .el-button {
  margin-top: 20px;
}

.template-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.template-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.template-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.template-card-header h3 {
  margin: 0;
  font-size: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
}

.template-actions {
  display: flex;
  gap: 8px;
}

.template-image {
  width: 100%;
  height: 160px;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s;
}

.template-image:hover {
  transform: scale(1.02);
}

.topology-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.no-image {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
}

.no-image .el-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.template-info {
  margin-top: 15px;
  display: flex;
  flex-direction: column;
}

.template-info p {
  margin: 0;
  margin-bottom: 10px;
  color: #606266;
  height: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.no-description {
  font-style: italic;
  color: #909399 !important;
}

.template-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}

/* 图片预览样式 */
.image-preview-dialog :deep(.el-dialog__body) {
  padding: 10px;
  overflow: auto;
  max-height: 75vh;
}

.image-preview-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 300px;
  overflow: auto;
}

.preview-image {
  max-width: 100%;
  object-fit: contain;
}

/* 确保对话框内部的滚动条显示 */
:deep(.el-dialog__body::-webkit-scrollbar) {
  width: 6px;
  height: 6px;
}

:deep(.el-dialog__body::-webkit-scrollbar-thumb) {
  background: #c0c4cc;
  border-radius: 3px;
}

:deep(.el-dialog__body::-webkit-scrollbar-track) {
  background: #f6f6f6;
}
</style> 