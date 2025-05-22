<template>
  <div class="edit-template-container">
    <div class="template-header">
      <h2>编辑模板</h2>
      <el-button @click="goBack" icon="Back">返回</el-button>
    </div>
    
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>
    
    <div v-else-if="!templateData" class="error-container">
      <el-empty description="未找到模板信息" />
      <el-button type="primary" @click="goBack">返回列表</el-button>
    </div>
    
    <div v-else class="template-form-container">
      <el-form 
        ref="templateFormRef" 
        :model="templateForm" 
        :rules="templateRules" 
        label-position="top"
      >
        <el-form-item label="模板名称" prop="template_name">
          <el-input v-model="templateForm.template_name" placeholder="请输入模板名称" />
        </el-form-item>
        
        <el-form-item label="模板描述" prop="template_description">
          <el-input 
            v-model="templateForm.template_description" 
            type="textarea" 
            rows="3" 
            placeholder="请输入模板描述"
          />
        </el-form-item>
        
        <el-form-item label="拓扑图">
          <el-upload
            class="template-upload"
            action="#"
            :auto-upload="false"
            :on-change="handleImageChange"
            :file-list="imageFileList"
            :limit="1"
            accept="image/*"
          >
            <template #trigger>
              <el-button type="primary">选择图片</el-button>
            </template>
            <template #tip>
              <div class="el-upload__tip">
                请上传PNG、JPG或GIF格式的拓扑图，大小不超过2MB
              </div>
            </template>
          </el-upload>
          
          <div v-if="imagePreviewUrl" class="image-preview">
            <img :src="imagePreviewUrl" alt="拓扑图预览" />
          </div>
          
          <div v-else-if="templateData.topology_image" class="image-preview">
            <img :src="getImageUrl()" alt="当前拓扑图" />
            <div class="image-caption">当前拓扑图</div>
          </div>
        </el-form-item>
        
        <el-form-item label="Terraform脚本" prop="terraform_content">
          <div class="terraform-editor">
            <el-input
              v-model="templateForm.terraform_content"
              type="textarea"
              rows="15"
              placeholder="请输入Terraform脚本内容"
              resize="none"
              style="font-family: monospace;"
            />
          </div>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            @click="submitTemplate" 
            :loading="submitting"
          >
            保存
          </el-button>
          <el-button @click="goBack">取消</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { Back } from '@element-plus/icons-vue'

export default {
  name: 'EditTemplate',
  components: {
    Back
  },
  setup() {
    const router = useRouter()
    const route = useRoute()
    const templateId = route.params.id
    
    const templateFormRef = ref(null)
    const templateData = ref(null)
    const loading = ref(true)
    const submitting = ref(false)
    
    // 表单数据
    const templateForm = reactive({
      template_name: '',
      template_description: '',
      terraform_content: ''
    })
    
    // 表单校验规则
    const templateRules = {
      template_name: [
        { required: true, message: '请输入模板名称', trigger: 'blur' },
        { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
      ],
      terraform_content: [
        { required: true, message: '请输入Terraform脚本内容', trigger: 'blur' }
      ]
    }
    
    // 上传文件列表
    const imageFileList = ref([])
    const imagePreviewUrl = ref('')
    
    // 获取模板详情
    const fetchTemplateDetails = async () => {
      try {
        loading.value = true
        
        const token = localStorage.getItem('token')
        const response = await axios.get(`/api/template/details?template_id=${templateId}`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        
        if (response.data.success && response.data.template) {
          templateData.value = response.data.template
          
          // 填充表单数据
          templateForm.template_name = templateData.value.template_name || ''
          templateForm.template_description = templateData.value.description || ''
          templateForm.terraform_content = response.data.template.terraform_content || ''
        } else {
          ElMessage.error(response.data.error || '获取模板详情失败')
        }
      } catch (error) {
        console.error('获取模板详情失败:', error)
        ElMessage.error('获取模板详情失败: ' + (error.message || '未知错误'))
      } finally {
        loading.value = false
      }
    }
    
    // 返回列表页
    const goBack = () => {
      router.push('/workspace/template')
    }
    
    // 处理图片上传
    const handleImageChange = (file) => {
      const isImage = file.raw.type.startsWith('image/')
      const isLt2M = file.raw.size / 1024 / 1024 < 2
      
      if (!isImage) {
        ElMessage.error('只能上传图片文件!')
        imageFileList.value = []
        return false
      }
      
      if (!isLt2M) {
        ElMessage.error('图片大小不能超过 2MB!')
        imageFileList.value = []
        return false
      }
      
      // 创建预览URL
      if (imagePreviewUrl.value) {
        URL.revokeObjectURL(imagePreviewUrl.value)
      }
      
      imagePreviewUrl.value = URL.createObjectURL(file.raw)
      imageFileList.value = [file]
      
      return true
    }
    
    // 获取图片URL
    const getImageUrl = () => {
      if (!templateData.value || !templateData.value.topology_image) return null
      
      // 添加时间戳防止缓存
      const timestamp = new Date().getTime()
      return `/api/template/image?template_id=${templateId}&image_name=${templateData.value.topology_image}&t=${timestamp}`
    }
    
    // 提交模板
    const submitTemplate = async () => {
      if (!templateFormRef.value) return
      
      await templateFormRef.value.validate(async (valid) => {
        if (!valid) {
          ElMessage.warning('请填写必填项')
          return
        }
        
        try {
          submitting.value = true
          
          // 创建FormData对象
          const formData = new FormData()
          formData.append('template_id', templateId)
          formData.append('template_name', templateForm.template_name)
          formData.append('template_description', templateForm.template_description)
          
          // 添加拓扑图
          if (imageFileList.value.length > 0) {
            formData.append('topology_image', imageFileList.value[0].raw)
          }
          
          // 添加Terraform内容
          const terraformBlob = new Blob([templateForm.terraform_content], { type: 'text/plain' })
          formData.append('terraform_file', terraformBlob, 'main.tf')
          
          // 发送请求
          const token = localStorage.getItem('token')
          const response = await axios.post('/api/template/update', formData, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'multipart/form-data'
            }
          })
          
          if (response.data.success) {
            ElMessage.success('模板更新成功')
            router.push('/workspace/template')
          } else {
            ElMessage.error(response.data.error || '更新模板失败')
          }
        } catch (error) {
          console.error('提交模板失败:', error)
          ElMessage.error('提交模板失败: ' + (error.message || '未知错误'))
        } finally {
          submitting.value = false
        }
      })
    }
    
    // 组件挂载时获取模板详情
    onMounted(() => {
      if (templateId) {
        fetchTemplateDetails()
      } else {
        loading.value = false
        ElMessage.error('模板ID不能为空')
      }
    })
    
    return {
      templateFormRef,
      templateForm,
      templateRules,
      templateData,
      loading,
      submitting,
      imageFileList,
      imagePreviewUrl,
      goBack,
      handleImageChange,
      getImageUrl,
      submitTemplate
    }
  }
}
</script>

<style scoped>
.edit-template-container {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
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

.loading-container, .error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.error-container .el-button {
  margin-top: 20px;
}

.template-form-container {
  max-width: 800px;
}

.image-preview {
  margin-top: 15px;
  border: 1px dashed #dcdfe6;
  padding: 10px;
  text-align: center;
  border-radius: 4px;
  position: relative;
}

.image-preview img {
  max-width: 100%;
  max-height: 200px;
}

.image-caption {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: rgba(0, 0, 0, 0.5);
  color: white;
  padding: 5px;
  font-size: 12px;
}

.terraform-editor {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.el-form-item {
  margin-bottom: 25px;
}
</style> 