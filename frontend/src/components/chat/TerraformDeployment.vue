<template>
  <div class="terraform-container">
    <div class="terraform-header">
      <h4>生成的Terraform代码</h4>
      <div class="terraform-actions">
        <!-- 移除复制代码按钮 -->
      </div>
    </div>
    
    <div class="terraform-editor">
      <el-input
        type="textarea"
        v-model="terraformCode"
        :rows="15"
        placeholder="Terraform代码将显示在这里"
        spellcheck="false"
      ></el-input>
    </div>
    
    <div class="terraform-footer">
      <div class="deploy-form">
        <el-input 
          v-model="deployName" 
          placeholder="部署名称" 
          class="deploy-name" 
          size="small"
        ></el-input>
        
        <!-- 添加API密钥选择下拉框 -->
        <el-select
          v-model="selectedApiKey"
          placeholder="请选择API密钥"
          size="small"
          class="api-key-select"
          @change="handleApiKeyChange"
          :loading="loadingApiKeys"
        >
          <el-option
            v-for="item in apiKeys"
            :key="item.id"
            :label="item.apikey_name"
            :value="item.id"
          />
        </el-select>
        
        <el-button 
          type="primary" 
          @click="startDeploy" 
          :loading="isDeploying"
          :disabled="!terraformCode || isDeploying || !selectedApiKey"
        >
          {{ isDeploying ? '正在部署...' : '确定执行' }}
        </el-button>
      </div>
    </div>
    
    <!-- 部署状态对话框 -->
    <el-dialog
      v-model="deploymentDialogVisible"
      title="部署状态"
      width="80%"
      :close-on-click-modal="false"
      @closed="handleDialogClosed"
    >
      <div class="deployment-status">
        <div class="status-header">
          <h3>部署ID: {{ currentDeployId }}</h3>
          <div class="status-badge" :class="deploymentStatusClass">
            {{ deploymentStatusText }}
          </div>
        </div>
        
        <el-steps :active="activeStep" finish-status="success" align-center>
          <el-step title="准备中" description="创建部署资源"></el-step>
          <el-step title="初始化" description="Terraform初始化"></el-step>
          <el-step title="规划中" description="Terraform规划"></el-step>
          <el-step title="应用/清理" description="Terraform应用或清理资源"></el-step>
          <el-step title="完成" description="部署完成"></el-step>
        </el-steps>
        
        <div class="deployment-log" v-if="deploymentError">
          <h4>错误信息</h4>
          <pre class="error-log">{{ deploymentError }}</pre>
        </div>
        
        <div class="deployment-summary" v-if="deploymentSummary">
          <h4>部署摘要</h4>
          <div class="outputs" v-if="deploymentSummary.outputs">
            <h5>输出变量</h5>
            <pre class="output-block">{{ JSON.stringify(deploymentSummary.outputs, null, 2) }}</pre>
          </div>
        </div>
      </div>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="deploymentDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="viewDeploymentDetails" v-if="deploymentStatus === 'completed'">
            查看详情
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, watch, computed, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
import axios from 'axios';

export default {
  name: 'TerraformDeployment',
  props: {
    code: {
      type: String,
      required: true
    },
    description: {
      type: String,
      default: ''
    }
  },
  emits: ['deploy-started', 'deploy-completed', 'deploy-failed'],
  setup(props, { emit }) {
    // 编辑器状态
    const terraformCode = ref(props.code);
    const deployName = ref('');
    
    // 部署状态
    const isDeploying = ref(false);
    const deploymentDialogVisible = ref(false);
    const currentDeployId = ref('');
    const deploymentStatus = ref('');
    const deploymentError = ref('');
    const deploymentSummary = ref(null);
    const statusCheckInterval = ref(null);
    const activeStep = ref(0);
    
    // API密钥相关
    const apiKeys = ref([]);
    const selectedApiKey = ref('');
    const loadingApiKeys = ref(false);
    
    // 监听代码变化
    watch(() => props.code, (newCode) => {
      terraformCode.value = newCode;
    });
    
    // 监听部署状态变化
    watch(deploymentStatus, (newStatus) => {
      // 当状态为失败时，确保重置部署中状态
      if (newStatus === 'failed') {
        isDeploying.value = false;
      }
    });
    
    // 监听对话框可见性
    watch(deploymentDialogVisible, (newVisible) => {
      // 当对话框关闭时，检查是否还在部署中
      if (!newVisible && isDeploying.value) {
        // 如果对话框被用户关闭但仍在部署，重置状态
        resetDeploymentState();
      }
    });
    
    // 重置部署状态
    const resetDeploymentState = () => {
      // 清除轮询定时器
      if (statusCheckInterval.value) {
        clearInterval(statusCheckInterval.value);
        statusCheckInterval.value = null;
      }
      
      // 重置部署状态
      isDeploying.value = false;
      
      // 如果对话框仍然打开，则关闭它
      if (deploymentDialogVisible.value) {
        deploymentDialogVisible.value = false;
      }
    };
    
    // 对话框关闭处理
    const handleDialogClosed = () => {
      // 确保重置部署状态
      resetDeploymentState();
    };
    
    // 加载API密钥列表
    const loadApiKeys = async () => {
      try {
        loadingApiKeys.value = true;
        const response = await axios.get('/api/apikeys');
        if (response.data && response.data.keys) {
          apiKeys.value = response.data.keys;
          if (apiKeys.value.length > 0) {
            selectedApiKey.value = apiKeys.value[0].id;
          }
        }
      } catch (error) {
        console.error('加载API密钥失败:', error);
        ElMessage.error('无法加载API密钥列表');
      } finally {
        loadingApiKeys.value = false;
      }
    };
    
    // API密钥变更处理
    const handleApiKeyChange = (value) => {
      selectedApiKey.value = value;
    };
    
    // 开始部署
    const startDeploy = async () => {
      if (!terraformCode.value) {
        ElMessage.warning('请先生成Terraform代码');
        return;
      }
      
      if (!selectedApiKey.value) {
        ElMessage.warning('请选择API密钥');
        return;
      }
      
      try {
        isDeploying.value = true;
        emit('deploy-started');
        
        // 添加安全超时，确保按钮状态最终会重置
        const safetyTimeout = setTimeout(() => {
          if (isDeploying.value) {
            console.warn('部署状态未在预期时间内重置，执行安全重置');
            isDeploying.value = false;
          }
        }, 600000); // 10分钟超时
        
        // 创建请求配置，增加超时时间
        const requestConfig = {
          timeout: 60000, // 60秒超时
          headers: {
            'Content-Type': 'application/json'
          }
        };
        
        // 分批发送代码，避免请求体过大
        const codeParts = terraformCode.value.length > 10000 ? 
          Math.ceil(terraformCode.value.length / 10000) : 1;
        
        let deployId = null;
        
        if (codeParts > 1) {
          // 如果代码较大，分片发送
          const firstPart = {
            terraform_code_part: terraformCode.value.substring(0, 10000),
            deploy_name: deployName.value || '通过AI生成的部署',
            description: props.description || '通过AI生成的部署',
            api_key_id: selectedApiKey.value,
            is_multipart: true,
            total_parts: codeParts,
            part_index: 0
          };
          
          // 发送第一部分
          const initResponse = await axios.post('/api/terraform/deploy/init', firstPart, requestConfig);
          
          if (!initResponse.data.success) {
            throw new Error(initResponse.data.message || '初始化部署失败');
          }
          
          deployId = initResponse.data.deploy_id;
          
          // 发送剩余部分
          for (let i = 1; i < codeParts; i++) {
            const start = i * 10000;
            const end = Math.min((i + 1) * 10000, terraformCode.value.length);
            
            const partData = {
              deploy_id: deployId,
              terraform_code_part: terraformCode.value.substring(start, end),
              part_index: i
            };
            
            const partResponse = await axios.post('/api/terraform/deploy/part', partData, requestConfig);
            
            if (!partResponse.data.success) {
              throw new Error(partResponse.data.message || `发送代码分片${i}失败`);
            }
          }
          
          // 完成所有部分上传后，启动部署
          const finalResponse = await axios.post('/api/terraform/deploy/complete', {
            deploy_id: deployId
          }, requestConfig);
          
          if (!finalResponse.data.success) {
            throw new Error(finalResponse.data.message || '完成部署请求失败');
          }
          
          // 使用finalResponse作为主要响应
          deployId = finalResponse.data.deploy_id;
        } else {
          // 如果代码不大，直接发送
          const response = await axios.post('/api/terraform/deploy', {
            code: terraformCode.value, // 改为使用'code'作为参数名，与后端匹配
            deploy_name: deployName.value || '通过AI生成的部署',
            description: props.description || '通过AI生成的部署',
            api_key_id: selectedApiKey.value
          }, requestConfig);
          
          if (!response.data.success) {
            throw new Error(response.data.message || '启动部署失败');
          }
          
          deployId = response.data.deploy_id;
        }
        
        if (deployId) {
          currentDeployId.value = deployId;
          deploymentStatus.value = 'pending';
          deploymentDialogVisible.value = true;
          activeStep.value = 0;
          
          // 开始轮询部署状态
          startPollingDeploymentStatus();
          
          ElMessage.success('部署任务已启动');
        } else {
          throw new Error('未获取到部署ID');
        }
      } catch (error) {
        console.error('部署出错:', error);
        let errorMessage = '网络错误';
        
        if (error.response) {
          // 服务器返回错误
          if (error.response.status === 502) {
            errorMessage = 'Bad Gateway错误：请求超时或服务器暂时无法处理请求';
          } else {
            errorMessage = error.response.data?.message || `服务器错误(${error.response.status})`;
          }
        } else if (error.request) {
          // 请求发送但没有收到响应
          errorMessage = '服务器无响应，请检查网络连接或服务器状态';
        } else {
          // 请求配置出错
          errorMessage = error.message || '请求配置错误';
        }
        
        ElMessage.error(`部署出错: ${errorMessage}`);
        isDeploying.value = false;
        emit('deploy-failed', errorMessage);
      }
    };
    
    // 轮询部署状态
    const startPollingDeploymentStatus = () => {
      // 清除可能存在的定时器
      if (statusCheckInterval.value) {
        clearInterval(statusCheckInterval.value);
      }
      
      // 轮询计数器
      let pollCount = 0;
      const maxPollCount = 200; // 最大轮询次数
      let consecutiveFailures = 0; // 连续失败次数
      const maxConsecutiveFailures = 3; // 最大连续失败次数
      
      // 设置新的定时器，每10秒查询一次，最多轮询100次
      statusCheckInterval.value = setInterval(async () => {
        // 增加轮询次数
        pollCount++;
        
        // 检查是否超过最大轮询次数
        if (pollCount > maxPollCount) {
          clearInterval(statusCheckInterval.value);
          statusCheckInterval.value = null;
          isDeploying.value = false;
          ElMessage.warning(`已达到最大轮询次数(${maxPollCount})，请在部署列表中查看最终状态`);
          return;
        }
        
        try {
          const response = await axios.get(`/api/terraform/status?deploy_id=${currentDeployId.value}`);
          
          // 重置连续失败计数
          consecutiveFailures = 0;
          
          if (response.data.success) {
            const deployment = response.data.deployment;
            deploymentStatus.value = deployment.status;
            
            // 更新部署错误信息
            if (deployment.error_message) {
              deploymentError.value = deployment.error_message;
            }
            
            // 更新部署摘要
            if (deployment.deployment_summary) {
              try {
                if (typeof deployment.deployment_summary === 'string') {
                  deploymentSummary.value = JSON.parse(deployment.deployment_summary);
                } else {
                  deploymentSummary.value = deployment.deployment_summary;
                }
              } catch (e) {
                deploymentSummary.value = { raw: deployment.deployment_summary };
              }
            }
            
            // 更新步骤
            updateActiveStep(deployment.status);
            
            // 如果部署完成或失败，停止轮询
            if (['completed', 'failed'].includes(deployment.status)) {
              clearInterval(statusCheckInterval.value);
              statusCheckInterval.value = null;
              isDeploying.value = false;
              
              if (deployment.status === 'completed') {
                emit('deploy-completed', currentDeployId.value);
                ElMessage.success('部署成功完成');
              } else if (deployment.status === 'failed') {
                emit('deploy-failed', deployment.error_message);
                ElMessage.error(`部署失败: ${deployment.error_message}`);
              }
            }
          } else {
            console.error('获取部署状态失败:', response.data.message);
            // 如果API返回失败但没有具体状态，也需要更新状态
            deploymentError.value = response.data.message || '获取部署状态失败';
            
            // 增加连续失败计数
            consecutiveFailures++;
            
            // 如果连续失败次数过多，认为部署出现问题
            if (consecutiveFailures >= maxConsecutiveFailures) {
              deploymentStatus.value = 'failed';
              clearInterval(statusCheckInterval.value);
              statusCheckInterval.value = null;
              isDeploying.value = false;
              emit('deploy-failed', '连续多次获取部署状态失败，请检查网络或服务器状态');
              ElMessage.error('连续多次获取部署状态失败，部署可能已失败');
            }
          }
        } catch (error) {
          console.error('轮询部署状态出错:', error);
          // 增加连续失败计数
          consecutiveFailures++;
          
          // 如果多次请求失败（例如服务器返回502错误），则停止轮询并更新状态
          pollCount += 10; // 加速达到最大轮询次数
          
          // 设置错误信息
          deploymentError.value = `轮询部署状态出错: ${error.message || '网络请求失败'}`;
          
          // 如果连续失败次数过多，终止轮询并标记部署失败
          if (consecutiveFailures >= maxConsecutiveFailures) {
            deploymentStatus.value = 'failed';
            clearInterval(statusCheckInterval.value);
            statusCheckInterval.value = null;
            isDeploying.value = false;
            emit('deploy-failed', error.message);
            ElMessage.error(`无法获取部署状态，部署可能已失败: ${error.message || '网络请求失败'}`);
          }
        }
      }, 20000); // 将轮询间隔改为20秒
    };
    
    // 更新激活的步骤
    const updateActiveStep = (status) => {
      switch (status) {
        case 'pending':
          activeStep.value = 0;
          break;
        case 'initializing':
          activeStep.value = 1;
          break;
        case 'planning':
          activeStep.value = 2;
          break;
        case 'applying':
          activeStep.value = 3;
          break;
        case 'cleaning':
          activeStep.value = 3; // 清理资源也使用应用中的步骤
          break;
        case 'completed':
          activeStep.value = 4;
          break;
        case 'failed':
          // 保持在当前步骤，但显示错误状态
          break;
      }
    };
    
    // 查看部署详情
    const viewDeploymentDetails = () => {
      // 这里可以跳转到部署详情页面
      window.open(`/deployments/${currentDeployId.value}`, '_blank');
    };
    
    // 计算部署状态样式
    const deploymentStatusClass = computed(() => {
      switch (deploymentStatus.value) {
        case 'pending':
        case 'initializing':
        case 'planning':
        case 'applying':
        case 'cleaning':
          return 'status-in-progress';
        case 'completed':
          return 'status-success';
        case 'failed':
          return 'status-error';
        default:
          return '';
      }
    });
    
    // 计算部署状态文本
    const deploymentStatusText = computed(() => {
      switch (deploymentStatus.value) {
        case 'pending':
          return '准备中';
        case 'initializing':
          return '初始化中';
        case 'planning':
          return '规划中';
        case 'applying':
          return '应用中';
        case 'cleaning':
          return '清理资源中';
        case 'completed':
          return '已完成';
        case 'failed':
          return '失败';
        default:
          return '未知状态';
      }
    });
    
    // 组件加载时获取API密钥列表
    onMounted(() => {
      loadApiKeys();
    });
    
    // 组件卸载时清除定时器
    onUnmounted(() => {
      if (statusCheckInterval.value) {
        clearInterval(statusCheckInterval.value);
        statusCheckInterval.value = null;
      }
    });
    
    return {
      terraformCode,
      deployName,
      isDeploying,
      startDeploy,
      resetDeploymentState,
      handleDialogClosed,
      
      // API密钥相关
      apiKeys,
      selectedApiKey,
      loadingApiKeys,
      handleApiKeyChange,
      
      // 部署状态相关
      deploymentDialogVisible,
      currentDeployId,
      deploymentStatus,
      deploymentError,
      deploymentSummary,
      activeStep,
      deploymentStatusClass,
      deploymentStatusText,
      viewDeploymentDetails
    };
  }
};
</script>

<style scoped>
.terraform-container {
  width: 100%;
  margin: 16px 0;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background-color: white;
}

.terraform-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.terraform-header h4 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

.terraform-actions {
  display: flex;
  gap: 8px;
}

.terraform-editor {
  padding: 16px;
}

.terraform-editor :deep(.el-textarea__inner) {
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
  line-height: 1.5;
}

.terraform-footer {
  padding: 16px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  border-top: 1px solid #e4e7ed;
}

.deploy-form {
  display: flex;
  align-items: center;
  gap: 12px;
}

.deploy-name {
  width: 200px;
}

.api-key-select {
  width: 200px;
}

/* 部署状态对话框样式 */
.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 14px;
}

.status-in-progress {
  background-color: #e6f7ff;
  color: #1890ff;
}

.status-success {
  background-color: #f6ffed;
  color: #52c41a;
}

.status-error {
  background-color: #fff2f0;
  color: #f5222d;
}

.deployment-log {
  margin-top: 24px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  padding: 16px;
}

.error-log {
  background-color: #fff2f0;
  color: #f5222d;
  padding: 12px;
  border-radius: 4px;
  font-family: 'Courier New', Courier, monospace;
  white-space: pre-wrap;
  font-size: 14px;
  overflow-x: auto;
}

.deployment-summary {
  margin-top: 24px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  padding: 16px;
}

.output-block {
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-family: 'Courier New', Courier, monospace;
  white-space: pre-wrap;
  font-size: 14px;
  overflow-x: auto;
}
</style> 