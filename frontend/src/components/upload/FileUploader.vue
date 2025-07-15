<template>
  <div class="file-upload-container">
    <div class="upload-preview-container">
      <div class="upload-preview" v-if="files.length > 0">
        <div v-for="(file, index) in files" :key="index" class="uploaded-file">
          <img :src="file.thumbnail_url" :alt="file.original_name" class="thumbnail-preview" />
          <span class="delete-file" @click="removeFile(index)">×</span>
        </div>
      </div>
    </div>
    <el-button 
      class="upload-button" 
      @click="triggerFileUpload"
      :loading="uploading"
      size="small"
      icon="Plus"
      style="min-width: 40px; height: 40px; padding: 0 10px; align-self: flex-end; margin-bottom: 5px;"
    >
      <i class="el-icon-upload"></i>
    </el-button>
    <input
      type="file"
      ref="fileInput"
      multiple
      accept="image/*"
      style="display: none"
      @change="handleFileUpload"
    />
  </div>
</template>

<script>
import { ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

export default {
  name: 'FileUploader',
  props: {
    modelValue: {
      type: Array,
      default: () => []
    }
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const fileInput = ref(null)
    const uploading = ref(false)
    
    // 计算属性-本地文件列表
    const files = ref(props.modelValue || [])
    
    // 监听modelValue变化，实时更新本地文件列表
    watch(() => props.modelValue, (newVal) => {
      console.log('FileUploader: modelValue变化', newVal);
      files.value = newVal || [];
    }, { deep: true });
    
    // 触发文件选择
    const triggerFileUpload = () => {
      if (fileInput.value) {
        fileInput.value.click()
      }
    }
    
    // 处理文件上传
    const handleFileUpload = async (event) => {
      const selectedFiles = event.target.files
      if (!selectedFiles || selectedFiles.length === 0) return
      
      uploading.value = true
      
      try {
        const formData = new FormData()
        // 添加所有文件到表单
        for (let i = 0; i < selectedFiles.length; i++) {
          formData.append('files', selectedFiles[i])
        }
        
        // 发送请求
        const token = localStorage.getItem('token')
        const response = await axios.post('/api/chat/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
            'Authorization': `Bearer ${token}`
          }
        })
        
        // 处理响应
        if (response.data && response.data.success) {
          // 将上传成功的文件添加到列表
          const newFiles = [...files.value, ...response.data.files]
          files.value = newFiles
          emit('update:modelValue', newFiles)
          ElMessage.success(`成功上传 ${response.data.files.length} 个文件`)
        } else {
          ElMessage.error(response.data?.error || '文件上传失败')
        }
      } catch (error) {
        console.error('文件上传失败:', error)
        ElMessage.error('文件上传失败: ' + (error.response?.data?.error || error.message || '未知错误'))
      } finally {
        uploading.value = false
        // 清除文件输入以允许上传相同的文件
        if (fileInput.value) {
          fileInput.value.value = ''
        }
      }
    }
    
    // 移除文件
    const removeFile = (index) => {
      const newFiles = files.value.filter((_, i) => i !== index)
      files.value = newFiles
      emit('update:modelValue', newFiles)
    }
    
    return {
      fileInput,
      uploading,
      files,
      triggerFileUpload,
      handleFileUpload,
      removeFile
    }
  }
}
</script>

<style scoped>
.file-upload-container {
  display: flex;
  align-items: flex-start;
  position: relative;
}

.upload-preview-container {
  position: absolute;
  bottom: 100%;
  left: 0;
  width: 100%;
  min-height: 10px;
  z-index: 10;
}

.upload-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 5px;
  padding: 5px;
  background-color: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.uploaded-file {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 2px;
}

.thumbnail-preview {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
}

.delete-file {
  position: absolute;
  top: -3px;
  right: -3px;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 50%;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #f56c6c;
  font-weight: bold;
  font-size: 12px;
}

.delete-file:hover {
  background-color: #f56c6c;
  color: white;
}

.upload-button {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style> 