from typing import Any, Dict, List, Optional, Union

from messages import BaseMessage, OpenAIMessage
from models import ModelManager
from memories import ChatHistoryMemory
from retrievers.rag_retriever import RAGRetriever
from .base import BaseAgent
import logging


class ChatAgent(BaseAgent):
    """Chat agent for handling user-system dialogue interactions with RAG support.
    
    This agent is responsible for processing user messages, generating responses,
    and managing the conversation flow with RAG-enhanced context.
    """
    
    def __init__(
        self,
        system_message: str,
        model_name: str = "gpt-4",
        memory: Optional[ChatHistoryMemory] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        retriever: Optional[RAGRetriever] = None,
    ):
        """Initialize a ChatAgent.
        
        Args:
            system_message: The system message that defines the agent's behavior
            model_name: The name of the model to use
            memory: Optional memory component for storing chat history
            tools: Optional list of tools available to the agent
            retriever: Optional RAG retriever for document search
        """
        self.system_message = system_message
        self.model_manager = ModelManager()
        self.model = self.model_manager.get_model(model_name)
        self.memory = memory or ChatHistoryMemory()
        self.tools = tools or []
        self.retriever = retriever
        self.logger = logging.getLogger(__name__)
        
    def reset(self) -> None:
        """Reset the agent's state."""
        self.memory.clear()
        
    def step(self, user_message: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Process a user message and generate a response."""
        try:
            # Convert string message to proper message object if needed
            if isinstance(user_message, str):
                user_message = {"role": "user", "content": user_message}
            
            # Add user message to memory
            self.memory.add_message(user_message)
            
            # Build context from memory
            context = self.memory.get_context()
            if not isinstance(context, list):
                context = [context] if context else []
            
            # 确保context中的每个消息都是字典格式
            processed_context = []
            for msg in context:
                if isinstance(msg, dict):
                    processed_context.append(msg)
                elif isinstance(msg, BaseMessage):
                    processed_context.append({
                        "role": msg.role,
                        "content": msg.content
                    })
                elif isinstance(msg, tuple) and len(msg) > 0:
                    # 处理可能是(message_list, token_count)格式的元组
                    msg_list = msg[0]
                    if isinstance(msg_list, list):
                        for sub_msg in msg_list:
                            if isinstance(sub_msg, dict):
                                processed_context.append(sub_msg)
                            elif isinstance(sub_msg, BaseMessage):
                                processed_context.append({
                                    "role": sub_msg.role,
                                    "content": sub_msg.content
                                })
                            elif isinstance(sub_msg, str):
                                processed_context.append({
                                    "role": "user",
                                    "content": sub_msg
                                })
                elif isinstance(msg, str):
                    processed_context.append({
                        "role": "user",
                        "content": msg
                    })
                else:
                    self.logger.warning(f"Unknown message type: {type(msg)}")
                    self.logger.debug(f"Raw message: {str(msg)[:200]}...")
            
            # RAG retrieval
            retrieved_docs = []
            rag_info_message = None
            
            try:
                self.logger.info(f"Starting RAG retrieval for query: {user_message['content']}")
                retrieved_docs = self.retriever.search(user_message["content"])
                self.logger.info(f"Retrieved {len(retrieved_docs)} documents from RAG")
                
                if retrieved_docs:
                    # 第一步：记录RAG检索到的文档摘要
                    rag_summary = f"找到 {len(retrieved_docs)} 个相关文档:\n"
                    for i, doc in enumerate(retrieved_docs):
                        filename = doc['metadata'].get('filename', 'unknown file')
                        similarity = doc['score']
                        content_preview = doc['content'][:100] + "..." if len(doc['content']) > 100 else doc['content']
                        rag_summary += f"文档 {i+1}: {filename} (相关度: {similarity:.2f})\n{content_preview}\n\n"
                    
                    # 创建一个助手消息，总结RAG结果
                    rag_info_message = {
                        "role": "assistant",
                        "content": rag_summary
                    }
                    processed_context.append(rag_info_message)
                    self.logger.debug(f"Added RAG summary message: {rag_summary}")
                    
                    # 第二步：添加每个文档的详细内容
                    for doc in retrieved_docs:
                        if doc.get("content"):  # Only add non-empty documents
                            # 构建文档信息
                            filename = doc['metadata'].get('filename', 'unknown file')
                            content = doc['content']
                            similarity = doc['score']
                            
                            # 添加到上下文
                            doc_message = {
                                "role": "system",
                                "content": f"以下是来自文档 {filename} 的内容 (相关度: {similarity:.2f}):\n\n{content}"
                            }
                            processed_context.append(doc_message)
                            self.logger.debug(f"Added document from {filename} with score: {similarity}")
                else:
                    # 如果没有检索到文档，添加一个提示消息
                    rag_info_message = {
                        "role": "assistant",
                        "content": "我没有找到与您问题直接相关的文档。我将基于我的通用知识回答您的问题。"
                    }
                    processed_context.append(rag_info_message)
                    self.logger.warning("No documents retrieved from RAG")
                    
            except Exception as e:
                self.logger.error(f"Error during RAG retrieval: {str(e)}", exc_info=True)
                # Continue without RAG documents
                rag_info_message = {
                    "role": "assistant",
                    "content": "检索相关文档时出现错误，我将尝试直接回答您的问题。"
                }
                processed_context.append(rag_info_message)
                
            # 添加系统消息（如果不存在）
            if not any(msg.get("role") == "system" for msg in processed_context):
                processed_context.insert(0, {
                    "role": "system",
                    "content": self.system_message
                })
            
            # 确保至少有一个用户消息
            if not any(msg.get("role") == "user" for msg in processed_context):
                processed_context.append(user_message)
            
            # 记录完整的上下文内容
            self.logger.info(f"Full context being sent to model: {len(processed_context)} messages")
            for i, msg in enumerate(processed_context):
                try:
                    self.logger.info(f"Message {i+1} - Role: {msg.get('role', 'unknown')}")
                    content_preview = msg.get('content', '')[:500]
                    self.logger.info(f"Message {i+1} - Content: {content_preview}...")
                    if len(msg.get('content', '')) > 500:
                        self.logger.debug(f"Message {i+1} - Full content: {msg.get('content', '')}")
                except Exception as e:
                    self.logger.error(f"Error logging message {i+1}: {str(e)}")
                    self.logger.debug(f"Problematic message: {str(msg)[:200]}...")
            
            # Call model with enhanced context
            try:
                # 确保传递给模型的是列表而不是元组
                self.logger.debug("Calling model generate function with processed context")
                response = self.model.generate(
                    messages=processed_context,
                    tools=self.tools,
                )
                
                # 记录模型原始响应
                self.logger.debug(f"Model raw response type: {type(response)}")
                self.logger.debug(f"Model raw response: {str(response)[:1000]}...")
                
                # Process model response
                try:
                    assistant_content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if not assistant_content:
                        assistant_content = "Sorry, I could not generate a valid response."
                        self.logger.warning("Model response structure might be invalid or content is empty.")
                        self.logger.debug(f"Raw response: {response}")

                    # 记录完整的助手响应内容
                    self.logger.debug(f"Full assistant response: {assistant_content}")
                    
                    # 创建BaseMessage对象而不是字典
                    assistant_message = BaseMessage.make_assistant_message(
                        role_name="assistant",
                        content=assistant_content
                    )
                except (IndexError, AttributeError, TypeError) as e:
                    self.logger.error(f"Error processing model response: {e}")
                    self.logger.debug(f"Raw response: {response}")
                    assistant_message = BaseMessage.make_assistant_message(
                        role_name="assistant",
                        content="Sorry, there was an error processing the response."
                    )

                # Add the processed assistant response to memory
                self.memory.add_message(assistant_message)
                
                # 如果有RAG信息消息，也添加到记忆中
                if rag_info_message:
                    rag_message = BaseMessage.make_assistant_message(
                        role_name="assistant",
                        content=rag_info_message["content"]
                    )
                    self.memory.add_message(rag_message)
                
                return {
                    "response": assistant_message,
                    "context": processed_context,
                    "retrieved_docs": retrieved_docs
                }
                
            except Exception as e:
                self.logger.error(f"Error in model generation: {str(e)}", exc_info=True)
                assistant_message = BaseMessage.make_assistant_message(
                    role_name="assistant",
                    content=f"Error in generating response: {str(e)}"
                )
                return {
                    "response": assistant_message,
                    "context": processed_context,
                    "retrieved_docs": retrieved_docs
                }
            
        except Exception as e:
            self.logger.error(f"Error in step method: {str(e)}", exc_info=True)
            assistant_message = BaseMessage.make_assistant_message(
                role_name="assistant",
                content=f"Error in processing request: {str(e)}"
            )
            return {
                "response": assistant_message,
                "context": [],
                "retrieved_docs": []
            }
