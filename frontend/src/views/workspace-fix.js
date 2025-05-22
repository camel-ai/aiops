// 文件上传相关方法 - 添加到setup函数中
const triggerFileUpload = () => {
  if (fileInput.value) {
    fileInput.value.click();
  }
};

const handleFileUpload = async (event) => {
  const files = event.target.files;
  if (!files || files.length === 0) return;
  
  uploading.value = true;
  
  try {
    const formData = new FormData();
    // 添加所有文件到表单
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }
    
    // 发送请求
    const token = localStorage.getItem('token');
    const response = await axios.post('/api/chat/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        'Authorization': `Bearer ${token}`
      }
    });
    
    // 处理响应
    if (response.data && response.data.success) {
      // 将上传成功的文件添加到列表
      uploadedFiles.value = [...uploadedFiles.value, ...response.data.files];
      ElMessage.success(`成功上传 ${response.data.files.length} 个文件`);
    } else {
      ElMessage.error(response.data?.error || '文件上传失败');
    }
  } catch (error) {
    console.error('文件上传失败:', error);
    ElMessage.error('文件上传失败: ' + (error.response?.data?.error || error.message || '未知错误'));
  } finally {
    uploading.value = false;
    // 清除文件输入以允许上传相同的文件
    if (fileInput.value) {
      fileInput.value.value = '';
    }
  }
};

const removeUploadedFile = (index) => {
  // 从列表中移除指定索引的文件
  uploadedFiles.value = uploadedFiles.value.filter((_, i) => i !== index);
};

// 在返回对象中添加的文件上传相关属性和方法 - 添加到return对象中
// fileInput,
// uploadedFiles,
// uploading,
// triggerFileUpload,
// handleFileUpload,
// removeUploadedFile, 