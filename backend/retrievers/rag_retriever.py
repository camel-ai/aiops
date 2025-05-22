import logging
from typing import Dict, List, Optional
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
import asyncio
from anyio import run, CancelScope, fail_after
import json

class RAGRetriever:
    """RAG retriever for querying RAGFlow service using MCP client."""
    
    def __init__(self, endpoint: str = "http://rag.cloudet.cn:9382/sse", 
                 dataset_ids: List[str] = None,
                 timeout: float = 30.0):
        self.endpoint = endpoint
        # 设置默认数据集列表
        if dataset_ids is None:
            self.dataset_ids = [
                "b4d3be0c16a411f09945d220a28f9367",  # 原始数据集
                "e8e85b2e1b6011f0be3d2ec89ce5a211",
                "49eef02a1aaa11f0b8b2722aebe90565",
                "4013d7f01aaa11f08a18722aebe90565",
                "def571221aa911f08f9f722aebe90565",
                "227a634a1aa911f0a042722aebe90565"
            ]
        else:
            self.dataset_ids = dataset_ids
        self.timeout = timeout  # 设置超时时间（秒）
        self.logger = logging.getLogger(__name__)
        
    async def _search_async(self, query: str) -> List[Dict]:
        """Asynchronous search implementation using MCP client."""
        documents = []
        
        try:
            self.logger.debug(f"Starting async RAG retrieval for query: {query}")
            
            # 使用 fail_after 设置超时
            try:
                with fail_after(self.timeout):
                    async with sse_client(self.endpoint) as streams:
                        async with ClientSession(streams[0], streams[1]) as session:
                            try:
                                # 初始化会话
                                await session.initialize()
                                
                                # 调用 RAG 工具 - 使用多个数据集
                                self.logger.debug(f"Calling RAGFlow tool with query: {query} across {len(self.dataset_ids)} datasets")
                                response = await session.call_tool(
                                    name="ragflow_retrieval",
                                    arguments={
                                        "dataset_ids": self.dataset_ids,
                                        "document_ids": [],
                                        "question": query
                                    }
                                )
                                
                                # 记录完整原始响应
                                self.logger.debug(f"Raw RAGFlow response type: {type(response)}")
                                
                                # 处理响应数据
                                raw_data = None
                                raw_results = []
                                
                                if hasattr(response, 'model_dump'):
                                    # 获取完整响应
                                    raw_data = response.model_dump()
                                    self.logger.debug(f"Response data type: {type(raw_data)}")
                                    
                                    # 打印完整响应进行调试
                                    self.logger.debug(f"Raw response data: {raw_data}")
                                    
                                    # 提取内容字段
                                    if isinstance(raw_data, dict):
                                        # 检查 content 字段
                                        content_data = raw_data.get('content', [])
                                        if isinstance(content_data, list) and content_data:
                                            self.logger.info(f"Found {len(content_data)} content items")
                                            
                                            # 处理每个内容项
                                            for item in content_data:
                                                if isinstance(item, dict) and 'text' in item:
                                                    text = item.get('text', '')
                                                    self.logger.debug(f"Found text content of length {len(text)}")
                                                    
                                                    # 尝试解析 JSON 内容
                                                    if text and '\n' in text:
                                                        # 多行 JSON
                                                        lines = [line for line in text.strip().split('\n') if line.strip()]
                                                        self.logger.debug(f"Split into {len(lines)} JSON lines")
                                                        
                                                        for line in lines:
                                                            try:
                                                                json_obj = json.loads(line)
                                                                if json_obj:
                                                                    raw_results.append(json_obj)
                                                                    self.logger.debug(f"Successfully parsed JSON line: {str(json_obj)[:100]}...")
                                                            except json.JSONDecodeError:
                                                                self.logger.warning(f"Failed to parse JSON line: {line[:100]}...")
                                                    else:
                                                        # 单个 JSON
                                                        try:
                                                            json_obj = json.loads(text)
                                                            if json_obj:
                                                                if isinstance(json_obj, list):
                                                                    raw_results.extend(json_obj)
                                                                    self.logger.debug(f"Added {len(json_obj)} results from single JSON array")
                                                                else:
                                                                    raw_results.append(json_obj)
                                                                    self.logger.debug(f"Added single JSON object: {str(json_obj)[:100]}...")
                                                        except json.JSONDecodeError:
                                                            self.logger.warning(f"Failed to parse JSON: {text[:100]}...")
                                        
                                        # 检查 results 字段
                                        results_data = raw_data.get('results', [])
                                        if results_data:
                                            self.logger.info(f"Found {len(results_data)} items in results field")
                                            if isinstance(results_data, list):
                                                raw_results.extend(results_data)
                                
                                # 如果没有找到结果，尝试其他方法
                                if not raw_results and hasattr(response, 'results'):
                                    results = response.results
                                    if results:
                                        self.logger.info(f"Found {len(results)} results via direct access")
                                        raw_results = results
                                
                                # 处理原始结果
                                self.logger.info(f"Total raw results found: {len(raw_results)}")
                                
                                # 处理每个结果
                                for result in raw_results:
                                    try:
                                        # 如果是字符串，尝试解析成 JSON
                                        if isinstance(result, str):
                                            try:
                                                result = json.loads(result)
                                                self.logger.debug(f"Parsed string result into JSON object: {str(result)[:100]}...")
                                            except json.JSONDecodeError:
                                                self.logger.warning(f"Failed to parse result as JSON: {result[:100]}...")
                                                continue
                                        
                                        # 确保是字典格式
                                        if not isinstance(result, dict):
                                            self.logger.warning(f"Result is not a dictionary: {type(result)}")
                                            continue
                                        
                                        # 提取内容 - 尝试多种可能的字段名
                                        content = None
                                        if 'content' in result:
                                            content = result.get('content')
                                        elif 'text' in result:
                                            content = result.get('text')
                                        elif 'document' in result:
                                            content = result.get('document')
                                        
                                        # 如果内容是字典，可能需要进一步提取
                                        if isinstance(content, dict):
                                            if 'content' in content:
                                                content = content.get('content')
                                            elif 'text' in content:
                                                content = content.get('text')
                                        
                                        if not content:
                                            self.logger.warning(f"Empty content in result: {str(result)[:200]}...")
                                            continue
                                        
                                        # 确保内容是字符串
                                        if not isinstance(content, str):
                                            content = str(content)
                                        
                                        # 提取元数据 - 尝试多种可能的字段名
                                        metadata = {}
                                        
                                        # 处理各种可能的数据集ID字段
                                        dataset_id = None
                                        if 'dataset_id' in result:
                                            dataset_id = result.get('dataset_id')
                                        elif 'datasetId' in result:
                                            dataset_id = result.get('datasetId')
                                        metadata['dataset_id'] = dataset_id or self.dataset_ids[0]
                                        
                                        # 处理各种可能的文档ID字段
                                        document_id = None
                                        if 'document_id' in result:
                                            document_id = result.get('document_id')
                                        elif 'documentId' in result:
                                            document_id = result.get('documentId')
                                        elif 'id' in result:
                                            document_id = result.get('id')
                                        metadata['document_id'] = document_id or 'unknown_doc_id'
                                        
                                        # 处理各种可能的文件名字段
                                        filename = None
                                        if 'document_keyword' in result:
                                            filename = result.get('document_keyword')
                                        elif 'filename' in result:
                                            filename = result.get('filename')
                                        elif 'file' in result:
                                            filename = result.get('file')
                                        elif 'title' in result:
                                            filename = result.get('title')
                                        metadata['filename'] = filename or 'unknown file'
                                        
                                        # 处理各种可能的相似度/分数字段
                                        score = 0.0
                                        if 'similarity' in result:
                                            score = float(result.get('similarity', 0.0))
                                        elif 'score' in result:
                                            score = float(result.get('score', 0.0))
                                        elif 'relevance' in result:
                                            score = float(result.get('relevance', 0.0))
                                        
                                        # 准备文档对象
                                        doc = {
                                            "content": content,
                                            "metadata": metadata,
                                            "score": score
                                        }
                                        
                                        documents.append(doc)
                                        self.logger.debug(f"Added document: {metadata['filename']} with {len(content)} chars")
                                    
                                    except Exception as e:
                                        self.logger.error(f"Error processing result: {str(e)}", exc_info=True)
                                        self.logger.debug(f"Problematic result: {str(result)[:200]}...")
                                        continue
                            
                            except asyncio.CancelledError:
                                self.logger.warning("RAG retrieval operation was cancelled")
                                raise
                            except Exception as e:
                                self.logger.error(f"Error during RAG session: {str(e)}")
                                raise
            except TimeoutError:
                self.logger.warning(f"RAG retrieval timed out after {self.timeout} seconds")
        
        except asyncio.CancelledError:
            self.logger.warning("RAG retrieval cancelled (timeout or external cancellation)")
        except Exception as e:
            self.logger.error(f"Error in RAG retrieval: {str(e)}", exc_info=True)
        
        self.logger.info(f"RAG retrieval completed with {len(documents)} documents")
        return documents
        
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search for relevant documents using RAGFlow service.
        
        Args:
            query: The search query
            top_k: Number of results to return
            
        Returns:
            List of relevant documents with their content and metadata
        """
        self.logger.debug(f"Sending request to RAGFlow service: {self.endpoint} with query: {query}")
        self.logger.info(f"Searching across {len(self.dataset_ids)} datasets: {self.dataset_ids}")
        
        documents = []
        try:
            # Run the async function in the event loop with error handling
            documents = run(self._search_async, query)
            self.logger.info(f"RAG search completed with {len(documents)} documents")
            
            # 检查是否获取到文档
            if not documents:
                self.logger.warning("No documents retrieved from any dataset")
            
            # 按相关度排序，并保留前 top_k 个
            if documents:
                # 确保所有文档都有有效的分数
                for doc in documents:
                    if "score" not in doc or doc["score"] is None:
                        doc["score"] = 0.0
                    elif not isinstance(doc["score"], (int, float)):
                        try:
                            doc["score"] = float(doc["score"])
                        except (ValueError, TypeError):
                            doc["score"] = 0.0
                
                # 排序并限制返回数量
                sorted_docs = sorted(documents, key=lambda x: float(x.get("score", 0.0)), reverse=True)
                return sorted_docs[:top_k] if len(sorted_docs) > top_k else sorted_docs
        except Exception as e:
            self.logger.error(f"Error in RAG search: {str(e)}", exc_info=True)
            
        return documents 