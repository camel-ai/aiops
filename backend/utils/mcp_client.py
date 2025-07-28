import asyncio
import logging
from typing import Dict, Any, List
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

class MCPClient:
    def __init__(self, sse_url="http://rag.cloudet.cn:9382/sse"):
        self.sse_url = sse_url
        self.dataset_ids = [
            "b4d3be0c16a411f09945d220a28f9367",  # 确认有效的ID
            "e8e85b2e1b6011f0be3d2ec89ce5a211",
            "49eef02a1aaa11f0b8b2722aebe90565",
            "4013d7f01aaa11f08a18722aebe90565",
            "def571221aa911f08f9f722aebe90565",
            "227a634a1aa911f0a042722aebe90565"
        ]
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    async def query(self, question: str) -> Dict[str, Any]:
        """向MCP服务器发送查询并获取响应"""
        self.logger.info(f"开始查询MCP服务器，问题: {question}")
        try:
            # 使用SSE客户端连接到MCP服务器
            self.logger.info(f"连接SSE服务器: {self.sse_url}")
            async with sse_client(self.sse_url) as streams:
                self.logger.info("SSE连接成功")
                async with ClientSession(streams[0], streams[1]) as session:
                    self.logger.info("初始化MCP会话")
                    await session.initialize()
                    
                    # 获取可用工具列表
                    tools = await session.list_tools()
                    self.logger.info(f"可用工具: {tools.tools}")
                    
                    # 使用ragflow_retrieval工具查询
                    self.logger.info(f"使用数据集IDs: {self.dataset_ids}")
                    response = await session.call_tool(
                        name="ragflow_retrieval", 
                        arguments={
                            "dataset_ids": self.dataset_ids,
                            "document_ids": [],
                            "question": question
                        }
                    )
                    
                    self.logger.info(f"查询完成，响应: {response.model_dump()}")
                    return {"question": question, "answer": response.model_dump()}
                    
        except Exception as e:
            error_msg = f"MCP查询出错: {str(e)}"
            self.logger.error(error_msg)
            # 提供更详细的错误信息
            if "Connection refused" in str(e):
                error_msg = f"无法连接到MCP服务器({self.sse_url})，请检查服务器是否运行或网络连接是否正常"
            elif "Timeout" in str(e):
                error_msg = f"连接MCP服务器超时，服务器可能负载过高或网络延迟较大"
            elif "404" in str(e):
                error_msg = f"MCP服务器端点不存在，请确认SSE URL是否正确: {self.sse_url}"
            elif "403" in str(e):
                error_msg = f"无权访问MCP服务器，可能需要API密钥或其他认证"
            
            return {
                "error": error_msg,
                "details": str(e),
                "question": question,
                "server_url": self.sse_url,
                "dataset_ids": self.dataset_ids
            }

    def query_sync(self, question: str) -> Dict[str, Any]:
        """同步查询方法，使用asyncio运行异步查询"""
        self.logger.info(f"开始同步查询MCP服务器，问题: {question}")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.query(question))
            finally:
                loop.close()
            return result
        except Exception as e:
            error_msg = f"执行同步查询时出错: {str(e)}"
            self.logger.error(error_msg)
            return {
                "error": error_msg,
                "details": str(e),
                "question": question
            }
