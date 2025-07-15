<template>
  <div class="add-template-container">
    <div class="template-header">
      <h2>新增模板</h2>
      <el-button @click="goBack" icon="Back">返回</el-button>
    </div>
    
    <div class="template-form-container">
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
        </el-form-item>
        
        <el-form-item label="Terraform脚本" prop="terraform_file">
          <el-upload
            class="terraform-upload"
            action="#"
            :auto-upload="false"
            :on-change="handleTerraformChange"
            :file-list="terraformFileList"
            :limit="1"
            accept=".tf,.tfvars,.json"
          >
            <template #trigger>
              <el-button type="primary">选择文件</el-button>
            </template>
            <template #tip>
              <div class="el-upload__tip">
                请上传Terraform配置文件(.tf/.tfvars)或JSON格式
              </div>
            </template>
          </el-upload>
          
          <div v-if="terraformContent" class="terraform-preview">
            <div class="preview-header">
              <span>脚本预览</span>
              <el-button size="small" text @click="editTerraform">编辑</el-button>
            </div>
            <pre><code>{{ terraformContent }}</code></pre>
          </div>
          
          <el-dialog
            v-model="showTerraformEditor"
            title="编辑Terraform脚本"
            width="80%"
          >
            <el-input
              v-model="terraformContent"
              type="textarea"
              rows="20"
              placeholder="请输入Terraform脚本内容"
              resize="none"
              style="font-family: monospace;"
            />
            <template #footer>
              <span class="dialog-footer">
                <el-button @click="showTerraformEditor = false">取消</el-button>
                <el-button type="primary" @click="saveTerraformContent">
                  确认
                </el-button>
              </span>
            </template>
          </el-dialog>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            @click="submitTemplate" 
            :loading="submitting"
          >
            提交
          </el-button>
          <el-button @click="goBack">取消</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { Back } from '@element-plus/icons-vue'

export default {
  name: 'AddTemplate',
  components: {
    Back
  },
  setup() {
    const router = useRouter()
    const templateFormRef = ref(null)
    
    // 表单数据
    const templateForm = reactive({
      template_name: '',
      template_description: ''
    })
    
    // 表单校验规则
    const templateRules = {
      template_name: [
        { required: true, message: '请输入模板名称', trigger: 'blur' },
        { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
      ]
    }
    
    // 上传文件列表
    const imageFileList = ref([])
    const terraformFileList = ref([])
    
    // 预览数据
    const imagePreviewUrl = ref('')
    const terraformContent = ref('')
    
    // Terraform编辑器
    const showTerraformEditor = ref(false)
    
    // 提交状态
    const submitting = ref(false)
    
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
    
    // 处理Terraform文件上传
    const handleTerraformChange = (file) => {
      const validExtensions = ['.tf', '.tfvars', '.json']
      const extension = '.' + file.name.split('.').pop().toLowerCase()
      
      if (!validExtensions.includes(extension)) {
        ElMessage.error('只能上传Terraform配置文件(.tf/.tfvars)或JSON文件!')
        terraformFileList.value = []
        return false
      }
      
      const reader = new FileReader()
      reader.onload = (e) => {
        terraformContent.value = e.target.result
      }
      reader.readAsText(file.raw)
      
      terraformFileList.value = [file]
      return true
    }
    
    // 编辑Terraform内容
    const editTerraform = () => {
      showTerraformEditor.value = true
    }
    
    // 保存Terraform内容
    const saveTerraformContent = () => {
      showTerraformEditor.value = false
    }
    
    // 提交模板
    const submitTemplate = async () => {
      if (!templateFormRef.value) return
      
      await templateFormRef.value.validate(async (valid) => {
        if (!valid) {
          ElMessage.warning('请填写必填项')
          return
        }
        
        if (terraformFileList.value.length === 0 && !terraformContent.value) {
          ElMessage.warning('请上传或编辑Terraform脚本')
          return
        }
        
        try {
          submitting.value = true
          
          // 创建FormData对象
          const formData = new FormData()
          formData.append('template_name', templateForm.template_name)
          formData.append('template_description', templateForm.template_description)
          
          // 添加拓扑图
          if (imageFileList.value.length > 0) {
            formData.append('topology_image', imageFileList.value[0].raw)
          }
          
          // 添加Terraform文件
          if (terraformFileList.value.length > 0) {
            formData.append('terraform_file', terraformFileList.value[0].raw)
          } else if (terraformContent.value) {
            // 如果没有上传文件但有编辑的内容，创建一个新的文件对象
            const terraformBlob = new Blob([terraformContent.value], { type: 'text/plain' })
            formData.append('terraform_file', terraformBlob, 'main.tf')
          }
          
          // 发送请求
          const token = localStorage.getItem('token')
          const response = await axios.post('/api/template/add', formData, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'multipart/form-data'
            }
          })
          
          if (response.data.success) {
            ElMessage.success('模板添加成功')
            router.push('/workspace/template')
          } else {
            ElMessage.error(response.data.error || '添加模板失败')
          }
        } catch (error) {
          console.error('提交模板失败:', error)
          ElMessage.error('提交模板失败: ' + (error.message || '未知错误'))
        } finally {
          submitting.value = false
        }
      })
    }
    
    return {
      templateFormRef,
      templateForm,
      templateRules,
      imageFileList,
      terraformFileList,
      imagePreviewUrl,
      terraformContent,
      showTerraformEditor,
      submitting,
      goBack,
      handleImageChange,
      handleTerraformChange,
      editTerraform,
      saveTerraformContent,
      submitTemplate
    }
  }
}
</script>

<style scoped>
.add-template-container {
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

.template-form-container {
  max-width: 800px;
}

.image-preview {
  margin-top: 15px;
  border: 1px dashed #dcdfe6;
  padding: 10px;
  text-align: center;
  border-radius: 4px;
}

.image-preview img {
  max-width: 100%;
  max-height: 200px;
}

.terraform-preview {
  margin-top: 15px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 15px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
}

.terraform-preview pre {
  margin: 0;
  padding: 15px;
  background-color: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
  overflow-x: auto;
  max-height: 300px;
}

.terraform-preview code {
  white-space: pre-wrap;
}

.el-form-item {
  margin-bottom: 25px;
}
</style> 