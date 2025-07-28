<template>
  <div class="mermaid-container">
    <div class="diagram-header">
      <h4>生成的拓扑图</h4>
      <div class="diagram-actions">
        <!-- 移除按钮 -->
      </div>
    </div>
    <div v-if="showDebug" class="debug-info">
      <div>代码长度: {{ code.length }}</div>
      <div>渲染状态: {{ renderStatus }}</div>
      <div v-if="errorInfo">错误信息: {{ errorInfo }}</div>
    </div>
    <div class="diagram-content">
      <!-- 直接渲染区域 - 添加点击事件 -->
      <div ref="renderContainer" class="render-container" @click="showFullScreenDiagram"></div>
      
      <!-- 作为备用，直接显示代码 -->
      <div class="code-container">
        <pre class="code-block">{{ code }}</pre>
      </div>
    </div>
    
    <!-- 全屏弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      title="拓扑图详情"
      width="90%"
      :close-on-click-modal="false"
      :show-close="true"
      :destroy-on-close="true"
      class="diagram-dialog"
    >
      <div class="fullscreen-diagram-container">
        <div 
          ref="fullScreenDiagram" 
          class="fullscreen-diagram"
          v-loading="isLoading"
          element-loading-text="拓扑图渲染中..."
        ></div>
      </div>
      <div class="zoom-controls">
        <el-button-group>
          <el-button @click="zoomIn" type="primary" plain>
            <i class="el-icon-zoom-in"></i> 放大
          </el-button>
          <el-button @click="resetZoom" type="primary" plain>
            <i class="el-icon-refresh"></i> 重置
          </el-button>
          <el-button @click="zoomOut" type="primary" plain>
            <i class="el-icon-zoom-out"></i> 缩小
          </el-button>
          <el-button @click="downloadDiagram" type="success" plain>
            <i class="el-icon-download"></i> 下载
          </el-button>
        </el-button-group>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import mermaid from 'mermaid'

export default {
  name: 'MermaidDiagram',
  props: {
    code: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const renderContainer = ref(null)
    const showDebug = ref(true)
    const renderStatus = ref('等待渲染')
    const errorInfo = ref('')
    
    // 弹窗相关
    const dialogVisible = ref(false)
    const fullScreenDiagram = ref(null)
    const isLoading = ref(false)
    const currentScale = ref(1)
    const dragState = ref({
      isDragging: false,
      startX: 0,
      startY: 0,
      translateX: 0,
      translateY: 0
    })
    
    // 初始化Mermaid
    const initMermaid = () => {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: 'default',
          securityLevel: 'loose',
          logLevel: 1,
          flowchart: { 
            useMaxWidth: false,
            htmlLabels: true,
            curve: 'basis', // 使用平滑曲线
            padding: 15,
            nodeSpacing: 50,
            rankSpacing: 80
          },
          fontFamily: 'monospace',
          fontSize: 14
        })
        renderStatus.value = 'Mermaid初始化完成'
        console.log('Mermaid初始化成功，版本:', mermaid.version)
      } catch (error) {
        console.error('Mermaid初始化错误:', error)
        renderStatus.value = `初始化错误: ${error.message}`
        errorInfo.value = error.message
      }
    }
    
    // 显示全屏图表
    const showFullScreenDiagram = () => {
      dialogVisible.value = true
      
      // 等Dialog挂载后渲染
      setTimeout(() => {
        renderFullScreenDiagram()
      }, 100)
    }
    
    // 渲染全屏图表
    const renderFullScreenDiagram = async () => {
      if (!fullScreenDiagram.value) return
      
      isLoading.value = true
      
      try {
        // 清空容器
        fullScreenDiagram.value.innerHTML = ''
        
        // 处理代码
        let processedCode = processCode(props.code)
        
        // 创建容器
        const container = document.createElement('div')
        container.className = 'mermaid'
        container.textContent = processedCode
        fullScreenDiagram.value.appendChild(container)
        
        // 重置变换
        resetZoom()
        
        // 渲染
        await mermaid.init(undefined, '.fullscreen-diagram .mermaid')
        
        // 添加拖拽事件
        setupDragEvents()
        
        isLoading.value = false
      } catch (error) {
        console.error('全屏图表渲染错误:', error)
        isLoading.value = false
      }
    }
    
    // 预处理Mermaid代码
    const processCode = (code) => {
      // 保留最简单的预处理
      let processedCode = code;
      
      // 移除可能的Markdown代码块标记
      if (processedCode.includes('```mermaid')) {
        processedCode = processedCode.replace('```mermaid', '').replace('```', '');
      } else if (processedCode.includes('```')) {
        processedCode = processedCode.replace(/```/g, '');
      }
      
      // 清理多余空格和空行
      const lines = processedCode.split('\n');
      const cleanedLines = lines.map(line => line.trim()).filter(line => line !== '');
      
      return cleanedLines.join('\n');
    }
    
    // 缩放和拖拽功能
    const zoomIn = () => {
      currentScale.value += 0.1
      applyTransform()
    }
    
    const zoomOut = () => {
      currentScale.value = Math.max(0.1, currentScale.value - 0.1)
      applyTransform()
    }
    
    const resetZoom = () => {
      currentScale.value = 1
      dragState.value.translateX = 0
      dragState.value.translateY = 0
      applyTransform()
    }
    
    const applyTransform = () => {
      if (!fullScreenDiagram.value) return
      
      const el = fullScreenDiagram.value.querySelector('.mermaid svg')
      if (el) {
        el.style.transform = `scale(${currentScale.value}) translate(${dragState.value.translateX}px, ${dragState.value.translateY}px)`
      }
    }
    
    // 设置拖拽事件
    const setupDragEvents = () => {
      if (!fullScreenDiagram.value) return
      
      const svgElement = fullScreenDiagram.value.querySelector('.mermaid svg')
      if (!svgElement) return
      
      // 添加鼠标样式
      svgElement.style.cursor = 'grab'
      
      const onMouseDown = (e) => {
        dragState.value.isDragging = true
        dragState.value.startX = e.clientX
        dragState.value.startY = e.clientY
        svgElement.style.cursor = 'grabbing'
        e.preventDefault()
      }
      
      const onMouseMove = (e) => {
        if (!dragState.value.isDragging) return
        
        const dx = e.clientX - dragState.value.startX
        const dy = e.clientY - dragState.value.startY
        
        dragState.value.translateX += dx / currentScale.value
        dragState.value.translateY += dy / currentScale.value
        
        dragState.value.startX = e.clientX
        dragState.value.startY = e.clientY
        
        applyTransform()
      }
      
      const onMouseUp = () => {
        dragState.value.isDragging = false
        svgElement.style.cursor = 'grab'
      }
      
      svgElement.addEventListener('mousedown', onMouseDown)
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
      
      // 在弹窗关闭时移除事件监听
      const cleanup = () => {
        document.removeEventListener('mousemove', onMouseMove)
        document.removeEventListener('mouseup', onMouseUp)
        svgElement.removeEventListener('mousedown', onMouseDown)
      }
      
      // 监听弹窗状态
      watch(dialogVisible, (val) => {
        if (!val) {
          cleanup()
        }
      })
    }
      
    // 使用Mermaid直接渲染
    const renderWithMermaid = async () => {
      if (!renderContainer.value || !props.code) return;
      
      renderStatus.value = '开始渲染';
      errorInfo.value = '';
      
      try {
        // 清空容器
        renderContainer.value.innerHTML = '';
        
        // 处理代码
        let processedCode = processCode(props.code);
        
        // 创建渲染容器
        const container = document.createElement('div');
        container.className = 'mermaid';
        container.textContent = processedCode;
        
        // 添加到DOM
        renderContainer.value.appendChild(container);
        
        // 使用Mermaid渲染
        await mermaid.init(undefined, '.mermaid');
        
        renderStatus.value = '渲染完成';
        console.log('Mermaid渲染完成');
        
      } catch (error) {
        console.error('Mermaid渲染错误:', error);
        renderStatus.value = `渲染失败: ${error.message}`;
        errorInfo.value = error.message;
        
        // 尝试使用备用方法渲染
        renderWithScript();
      }
    }
    
    // 使用脚本加载和渲染mermaid (备用方法)
    const renderWithScript = () => {
      if (!renderContainer.value || !props.code) return;
      
      renderStatus.value = '使用备用方法渲染';
      
      try {
        // 清空容器
        renderContainer.value.innerHTML = '';
        
        // 创建脚本元素
        const script = document.createElement('script');
        script.type = 'text/javascript';
        
        // 准备渲染函数
        const renderId = `mermaid-${Date.now()}`;
        const containerSelector = `#${renderId}`;
        
        // 创建容器元素
        const container = document.createElement('div');
        container.id = renderId;
        container.className = 'mermaid';
        container.textContent = props.code;
        
        // 添加到DOM
        renderContainer.value.appendChild(container);
        
        // 使用动态加载的mermaid库进行渲染
        // eslint-disable-next-line
        script.textContent = `
          // 动态加载mermaid库
          if (typeof mermaid === 'undefined') {
            console.log('需要动态加载mermaid库');
            const mermaidScript = document.createElement('script');
            mermaidScript.src = 'https://cdn.jsdelivr.net/npm/mermaid@9.4.3/dist/mermaid.min.js';
            mermaidScript.onload = function() {
              console.log('Mermaid库加载成功');
              
              // 初始化mermaid
              mermaid.initialize({
                startOnLoad: true,
                theme: 'default',
                securityLevel: 'loose',
                logLevel: 1,
                flowchart: { 
                  useMaxWidth: false,
                  htmlLabels: true,
                  curve: 'basis',
                  padding: 15,
                  nodeSpacing: 50,
                  rankSpacing: 80
                },
                fontFamily: 'monospace',
                fontSize: 14
              });
              
              try {
                // 使用mermaid渲染
                setTimeout(() => {
                  mermaid.init(undefined, '${containerSelector}');
                  console.log('Mermaid渲染完成');
                }, 500);
              } catch (e) {
                console.error('Mermaid渲染错误:', e);
              }
            };
            
            document.head.appendChild(mermaidScript);
          } else {
            console.log('使用已加载的mermaid库');
            try {
              // 初始化mermaid
              mermaid.initialize({
                startOnLoad: false,
                theme: 'default',
                securityLevel: 'loose',
                logLevel: 1,
                flowchart: { 
                  useMaxWidth: false,
                  htmlLabels: true,
                  curve: 'basis',
                  padding: 15,
                  nodeSpacing: 50,
                  rankSpacing: 80
                },
                fontFamily: 'monospace',
                fontSize: 14
              });
              
              // 使用mermaid渲染
              setTimeout(() => {
                mermaid.init(undefined, '${containerSelector}');
                console.log('Mermaid渲染完成');
              }, 500);
            } catch (e) {
              console.error('Mermaid渲染错误:', e);
            }
          }
        `;
        
        // 添加脚本到DOM
        document.head.appendChild(script);
        
        renderStatus.value = '备用渲染脚本已执行';
      } catch (error) {
        console.error('备用渲染错误：', error);
        renderStatus.value = `备用渲染失败: ${error.message}`;
        errorInfo.value = error.message;
      }
    }
    
    // 下载拓扑图
    const downloadDiagram = () => {
      if (!fullScreenDiagram.value) return
      
      try {
        // 获取SVG元素
        const svgElement = fullScreenDiagram.value.querySelector('.mermaid svg')
        if (!svgElement) {
          ElMessage.error('无法找到SVG图形')
          return
        }
        
        // 创建SVG副本避免修改原始SVG
        const svgClone = svgElement.cloneNode(true)
        
        // 获取外围的SVG内容
        const svgContent = svgClone.outerHTML
        
        // 创建Blob对象
        const blob = new Blob([svgContent], { type: 'image/svg+xml' })
        
        // 创建下载链接
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `topology_diagram_${new Date().getTime()}.svg`
        
        // 触发下载
        document.body.appendChild(link)
        link.click()
        
        // 清理
        setTimeout(() => {
          document.body.removeChild(link)
          URL.revokeObjectURL(url)
        }, 100)
        
        ElMessage.success('拓扑图下载成功')
      } catch (error) {
        console.error('下载拓扑图时出错:', error)
        ElMessage.error(`下载失败: ${error.message}`)
      }
    }
    
    // 组件挂载时渲染
    onMounted(() => {
      console.log('MermaidDiagram组件挂载')
      initMermaid()
      
      if (props.code) {
        console.log('发现图表代码，长度:', props.code.length)
        // 添加短暂延时，确保DOM完全准备好
        setTimeout(() => {
          renderWithMermaid()
        }, 100)
      }
    })
    
    // 监听代码变化
    watch(() => props.code, (newCode) => {
      if (newCode) {
        console.log('图表代码已更新，长度:', newCode.length)
        // 添加短暂延时，确保DOM完全准备好
        setTimeout(() => {
          renderWithMermaid()
        }, 100)
      }
    })
    
    return {
      renderContainer,
      showDebug,
      renderStatus,
      errorInfo,
      dialogVisible,
      fullScreenDiagram,
      isLoading,
      showFullScreenDiagram,
      zoomIn,
      zoomOut,
      resetZoom,
      downloadDiagram
    }
  }
}
</script>

<style scoped>
.mermaid-container {
  width: 100%;
  margin: 16px 0;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.diagram-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.diagram-header h4 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

/* 简化操作区域样式 */
.diagram-actions {
  display: flex;
}

.debug-info {
  font-family: monospace;
  background-color: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 4px;
  padding: 10px;
  margin: 10px;
  color: #606266;
  font-size: 12px;
}

.diagram-content {
  padding: 16px;
  min-height: 350px;
  overflow: auto;
  background-color: white;
}

.render-container {
  width: 100%;
  min-height: 200px;
  margin-bottom: 20px;
  padding: 10px;
  background-color: #f9f9f9;
  border-radius: 4px;
  border: 1px dashed #dcdfe6;
  cursor: pointer; /* 添加指针样式表明可点击 */
  transition: all 0.3s;
}

.render-container:hover {
  background-color: #f0f0f0;
  box-shadow: 0 0 8px rgba(0, 0, 0, 0.1);
}

.code-container {
  margin-top: 20px;
  border-top: 1px solid #ebeef5;
  padding-top: 20px;
}

.code-block {
  font-family: 'Courier New', Courier, monospace;
  background-color: #f8f8f8;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 15px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}

/* 确保mermaid生成的SVG能完整显示 */
:deep(.mermaid svg) {
  width: 100% !important;
  height: auto !important;
  min-height: 200px !important;
  max-width: 100% !important;
}

:deep(.mermaid) {
  overflow: visible !important;
}

/* 全屏弹窗样式 */
.diagram-dialog {
  display: flex;
  flex-direction: column;
}

.fullscreen-diagram-container {
  height: 70vh;
  overflow: hidden;
  position: relative;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background-color: #f9f9f9;
}

.fullscreen-diagram {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
}

:deep(.fullscreen-diagram .mermaid) {
  max-width: 100%;
  max-height: 100%;
  transform-origin: center center;
}

:deep(.fullscreen-diagram .mermaid svg) {
  width: auto !important;
  max-width: none !important;
  height: auto !important;
  min-height: auto !important;
  transform-origin: center center;
  transition: transform 0.1s;
}

.zoom-controls {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style> 