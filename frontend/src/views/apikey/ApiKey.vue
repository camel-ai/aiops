<template>
  <div class="apikey-container">
    <div class="header">
      <h2>API-KEY 管理</h2>
      <el-button type="primary" @click="showAddForm">新增KEY</el-button>
    </div>
    
    <div class="key-list">
      <el-table :data="keyList" style="width: 100%" v-loading="loading">
        <el-table-column prop="apikey_name" label="名称" width="120"></el-table-column>
        <el-table-column prop="cloud" label="云平台" width="100">
          <template #default="scope">
            <el-tag>{{ scope.row.cloud }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ak" label="Access Key" width="180">
          <template #default="scope">
            <div class="key-text">
              {{ maskKey(scope.row.ak) }}
              <el-button size="small" text @click="copyText(scope.row.ak)">复制</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sk" label="Secret Key" width="180">
          <template #default="scope">
            <div class="key-text">
              {{ maskKey(scope.row.sk) }}
              <el-button size="small" text @click="copyText(scope.row.sk)">复制</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" show-overflow-tooltip></el-table-column>
        <el-table-column prop="createtime" label="创建时间" width="180"></el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button size="small" type="primary" @click="editKey(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteKey(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 添加/编辑API KEY的对话框 -->
    <el-dialog
      :title="isEditing ? '编辑API密钥' : '新增API密钥'"
      v-model="dialogVisible"
      width="500px"
      @close="resetForm"
    >
      <el-form :model="keyForm" label-width="120px">
        <el-form-item label="API 名称" required>
          <el-input v-model="keyForm.apikey_name" placeholder="请输入API名称"></el-input>
        </el-form-item>
        
        <el-form-item label="云平台" required>
          <el-select v-model="keyForm.cloud" placeholder="请选择云平台" v-loading="loadingClouds">
            <el-option 
              v-for="cloud in cloudList" 
              :key="cloud.name" 
              :label="cloud.name" 
              :value="cloud.name">
            </el-option>
          </el-select>
        </el-form-item>
        
        <el-form-item label="Access Key (AK)" required>
          <el-input v-model="keyForm.ak" placeholder="请输入Access Key"></el-input>
        </el-form-item>
        
        <el-form-item label="Secret Key (SK)" required>
          <el-input v-model="keyForm.sk" type="password" placeholder="请输入Secret Key" show-password></el-input>
        </el-form-item>
        
        <el-form-item label="备注">
          <el-input v-model="keyForm.remark" type="textarea" :rows="2" placeholder="请输入备注信息"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveKey">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import axios from 'axios';
import { useStore } from 'vuex';

export default {
  name: 'ApiKeyView',
  setup() {
    const store = useStore();
    const keyForm = ref({
      id: null,
      apikey_name: '',
      cloud: '',
      ak: '',
      sk: '',
      remark: ''
    });
    
    const keyList = ref([]);
    const cloudList = ref([]);
    const isEditing = ref(false);
    const dialogVisible = ref(false);
    const loading = ref(false);
    const loadingClouds = ref(false);
    
    // 显示添加表单
    const showAddForm = () => {
      isEditing.value = false;
      resetForm();
      dialogVisible.value = true;
      
      // 确保云平台列表已加载
      if (cloudList.value.length === 0) {
        loadCloudList();
      }
    };
    
    // 加载云平台列表
    const loadCloudList = async () => {
      loadingClouds.value = true;
      try {
        // 尝试从Vuex store获取云列表
        let clouds = store.state.clouds;
        
        // 如果store中没有云列表，则从API获取
        if (!clouds || clouds.length === 0) {
          await store.dispatch('fetchClouds');
          clouds = store.state.clouds;
        }
        
        if (clouds && clouds.length > 0) {
          cloudList.value = clouds;
          console.log('云平台列表加载成功:', cloudList.value);
        } else {
          // 如果API获取失败，回退到默认列表
          console.warn('从API获取云平台列表失败，使用默认列表');
          cloudList.value = [
            { id: 1, name: 'AWS' },
            { id: 2, name: 'AZURE' },
            { id: 3, name: '阿里云' },
            { id: 4, name: '华为云' },
            { id: 5, name: '腾讯云' },
            { id: 6, name: '百度云' },
            { id: 7, name: '火山云' },
            { id: 8, name: '四维云' }
          ];
        }
      } catch (error) {
        console.error('加载云平台列表出错:', error);
        ElMessage.error('获取云平台列表失败');
        
        // 出错时也回退到默认列表
        cloudList.value = [
          { id: 1, name: 'AWS' },
          { id: 2, name: 'AZURE' },
          { id: 3, name: '阿里云' },
          { id: 4, name: '华为云' },
          { id: 5, name: '腾讯云' },
          { id: 6, name: '百度云' },
          { id: 7, name: '火山云' },
          { id: 8, name: '四维云' }
        ];
      } finally {
        loadingClouds.value = false;
      }
    };
    
    // 加载API密钥列表
    const loadApiKeys = async () => {
      loading.value = true;
      try {
        const response = await axios.get('/api/apikeys');
        if (response.data.success) {
          keyList.value = response.data.keys || [];
        } else {
          ElMessage.error(response.data.error || '获取密钥列表失败');
        }
      } catch (error) {
        console.error('获取API密钥列表出错:', error);
        ElMessage.error('获取密钥列表失败');
      } finally {
        loading.value = false;
      }
    };
    
    // 保存API KEY
    const saveKey = async () => {
      // 表单验证
      if (!keyForm.value.apikey_name) {
        ElMessage.warning('请输入名称');
        return;
      }
      
      if (!keyForm.value.cloud) {
        ElMessage.warning('请选择云平台');
        return;
      }
      
      if (!keyForm.value.ak) {
        ElMessage.warning('请输入Access Key');
        return;
      }
      
      if (!keyForm.value.sk) {
        ElMessage.warning('请输入Secret Key');
        return;
      }
      
      try {
        if (isEditing.value) {
          // 更新现有记录
          const keyId = keyForm.value.id;
          const response = await axios.put(`/api/apikeys/${keyId}`, keyForm.value);
          if (response.data.success) {
            ElMessage.success('密钥更新成功');
            dialogVisible.value = false;
            await loadApiKeys(); // 重新加载列表
          } else {
            ElMessage.error(response.data.error || '更新密钥失败');
          }
        } else {
          // 添加新记录
          const response = await axios.post('/api/apikeys', keyForm.value);
          if (response.data.success) {
            ElMessage.success('密钥保存成功');
            dialogVisible.value = false;
            await loadApiKeys(); // 重新加载列表
          } else {
            ElMessage.error(response.data.error || '保存密钥失败');
          }
        }
      } catch (error) {
        console.error('保存API密钥出错:', error);
        ElMessage.error('操作失败，请稍后再试');
      }
    };
    
    // 重置表单
    const resetForm = () => {
      keyForm.value = {
        id: null,
        apikey_name: '',
        cloud: '',
        ak: '',
        sk: '',
        remark: ''
      };
    };
    
    // 编辑KEY
    const editKey = (key) => {
      // 确保云平台列表已加载
      if (cloudList.value.length === 0) {
        loadCloudList();
      }
      
      keyForm.value = { ...key };
      isEditing.value = true;
      dialogVisible.value = true;
    };
    
    // 删除KEY
    const deleteKey = (key) => {
      ElMessageBox.confirm(
        `确定要删除"${key.apikey_name}"的密钥吗？`,
        '删除确认',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }
      ).then(async () => {
        try {
          const response = await axios.delete(`/api/apikeys/${key.id}`);
          if (response.data.success) {
            ElMessage.success('密钥删除成功');
            await loadApiKeys(); // 重新加载列表
          } else {
            ElMessage.error(response.data.error || '删除密钥失败');
          }
        } catch (error) {
          console.error('删除API密钥出错:', error);
          ElMessage.error('删除密钥失败');
        }
      }).catch(() => {
        // 取消删除
      });
    };
    
    // 复制文本
    const copyText = (text) => {
      navigator.clipboard.writeText(text).then(() => {
        ElMessage.success('已复制到剪贴板');
      });
    };
    
    // 掩盖KEY,只显示前6位和后4位
    const maskKey = (key) => {
      if (!key) return '';
      if (key.length <= 10) return key;
      return key.substring(0, 6) + '****' + key.substring(key.length - 4);
    };
    
    onMounted(() => {
      // 加载API密钥列表
      loadApiKeys();
      
      // 加载云平台列表
      loadCloudList();
    });
    
    return {
      keyForm,
      keyList,
      cloudList,
      isEditing,
      dialogVisible,
      loading,
      loadingClouds,
      showAddForm,
      saveKey,
      resetForm,
      editKey,
      deleteKey,
      copyText,
      maskKey
    };
  }
};
</script>

<style scoped>
.apikey-container {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.key-list {
  margin-top: 20px;
}

.key-text {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: monospace;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style> 