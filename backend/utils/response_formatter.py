import logging
import json
import traceback
from typing import Dict, Any, List

class ResponseFormatter:
    """
    格式化MCP服务器返回的响应，使其更整洁地呈现给前端
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def format_mcp_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化MCP响应数据
        
        Args:
            response: MCP服务器返回的原始响应
            
        Returns:
            格式化后的响应数据
        """
        self.logger.info("开始格式化MCP响应")
        
        # 记录原始响应，帮助调试
        self.logger.info(f"原始响应: {str(response)[:500]}...")
        
        # 检查是否有错误
        if "error" in response:
            self.logger.error(f"MCP响应包含错误: {response['error']}")
            return {
                "status": "error",
                "message": response["error"],
                "details": response.get("details", ""),
                "question": response.get("question", ""),
                "formatted_results": []
            }
        
        # 检查响应结构
        if "answer" not in response:
            self.logger.error("MCP响应缺少answer字段")
            return {
                "status": "error",
                "message": "响应格式不正确，缺少answer字段",
                "question": response.get("question", ""),
                "formatted_results": []
            }
        
        try:
            answer = response["answer"]
            question = response.get("question", "")
            
            # 记录原始响应结构，帮助调试
            self.logger.info(f"原始响应结构: {str(answer.keys())}")
            
            formatted_results = []
            
            # 检查是否有content字段，这是实际MCP响应的结构
            if "content" in answer and isinstance(answer["content"], list):
                self.logger.info(f"从content字段解析结果，找到 {len(answer['content'])} 个内容项")
                
                # 遍历content列表
                for content_item in answer["content"]:
                    # 检查是否是文本类型
                    if isinstance(content_item, dict) and content_item.get("type") == "text":
                        text_content = content_item.get("text", "")
                        self.logger.info(f"处理文本内容: {text_content[:100]}...")
                        
                        # 文本内容可能是多个JSON字符串，每行一个
                        try:
                            # 首先尝试将整个文本作为一个JSON数组解析
                            if text_content.strip().startswith("[") and text_content.strip().endswith("]"):
                                self.logger.info("尝试将文本解析为JSON数组")
                                json_array = json.loads(text_content)
                                for item in json_array:
                                    self._process_json_item(item, formatted_results)
                            else:
                                # 如果不是JSON数组，则按行分割并解析每行
                                json_lines = text_content.strip().split("\n")
                                self.logger.info(f"拆分为 {len(json_lines)} 行JSON")
                                
                                for json_line in json_lines:
                                    if not json_line.strip():
                                        continue
                                    try:
                                        # 解析每行JSON
                                        item = json.loads(json_line)
                                        self._process_json_item(item, formatted_results)
                                    except json.JSONDecodeError as je:
                                        self.logger.warning(f"JSON解析错误: {str(je)}, 行内容: {json_line[:100]}...")
                                    except Exception as e:
                                        self.logger.warning(f"处理JSON行时出错: {str(e)}, 行内容: {json_line[:100]}...")
                        except Exception as e:
                            self.logger.warning(f"处理文本内容时出错: {str(e)}")
                            self.logger.debug(traceback.format_exc())
            
            # 如果没有从content字段找到结果，尝试旧的结构
            if not formatted_results and "result" in answer and answer["result"]:
                self.logger.info("从result字段解析结果")
                results = answer["result"].get("results", [])
                
                for item in results:
                    self._process_json_item(item, formatted_results)
            
            # 按相似度排序结果
            if formatted_results:
                formatted_results.sort(key=lambda x: x["similarity"], reverse=True)
            
            # 创建最终响应
            formatted_response = {
                "status": "success",
                "message": "查询成功",
                "question": question,
                "result_count": len(formatted_results),
                "formatted_results": formatted_results
            }
            
            self.logger.info(f"MCP响应格式化完成，找到 {len(formatted_results)} 条结果")
            return formatted_response
            
        except Exception as e:
            self.logger.error(f"格式化MCP响应时出错: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return {
                "status": "error",
                "message": f"格式化响应时出错: {str(e)}",
                "question": response.get("question", ""),
                "formatted_results": []
            }
    
    def _process_json_item(self, item, formatted_results):
        """
        处理单个JSON结果项并添加到格式化结果列表
        
        Args:
            item: 单个JSON结果项
            formatted_results: 格式化结果列表，将在此列表中添加处理后的结果
        """
        try:
            # 提取核心字段
            content = item.get("content", "")
            highlight = item.get("highlight", "")
            document_keyword = item.get("document_keyword", "未知文档")
            similarity = item.get("similarity", 0)
            vector_similarity = item.get("vector_similarity", 0)
            
            # 处理高亮文本，将HTML标签替换为更友好的格式
            formatted_highlight = highlight.replace("<em>", "【").replace("</em>", "】")
            
            # 创建格式化的结果项
            formatted_item = {
                "document": document_keyword,
                "similarity": round(float(similarity), 2),
                "vector_similarity": round(float(vector_similarity), 2),
                "content": content,
                "highlight": formatted_highlight,
                "raw_highlight": highlight  # 保留原始高亮，以便前端可以选择如何显示
            }
            
            formatted_results.append(formatted_item)
            self.logger.info(f"成功解析结果项: {document_keyword}")
        except Exception as e:
            self.logger.warning(f"处理结果项时出错: {str(e)}")
            self.logger.debug(f"问题项: {str(item)[:200]}...")
    
    def format_for_display(self, formatted_response: Dict[str, Any]) -> str:
        """
        将格式化的响应转换为可读性更好的文本格式，用于日志或调试
        
        Args:
            formatted_response: 已格式化的响应数据
            
        Returns:
            格式化为文本的响应
        """
        try:
            output = []
            output.append(f"问题: {formatted_response.get('question', '未知问题')}")
            output.append(f"状态: {formatted_response.get('status', '未知状态')}")
            output.append(f"消息: {formatted_response.get('message', '')}")
            output.append(f"结果数量: {formatted_response.get('result_count', 0)}")
            output.append("")
            
            for i, item in enumerate(formatted_response.get("formatted_results", []), 1):
                output.append(f"结果 {i}:")
                output.append(f"📄 文档: {item.get('document', '未知文档')} (相似度: {item.get('similarity', 0):.2f})")
                output.append(f"🔍 内容: {item.get('content', '').replace(chr(10), ' ')}")
                output.append(f"✨ 匹配部分: {item.get('highlight', '')}")
                output.append("─" * 50)
            
            return "\n".join(output)
        except Exception as e:
            self.logger.error(f"生成显示文本时出错: {str(e)}")
            return f"格式化显示文本时出错: {str(e)}"
