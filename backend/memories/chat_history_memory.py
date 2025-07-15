from typing import Dict, List, Optional, Tuple, Any, Union
import mysql.connector
from datetime import datetime

from messages import BaseMessage, OpenAIMessage
from .base import AgentMemory, BaseContextCreator
from .records import MemoryRecord, ContextRecord


class SimpleContextCreator(BaseContextCreator):
    """A simple context creator that selects messages based on token limit.
    
    This class implements a basic strategy for creating context from memory records.
    """
    
    def __init__(self, token_limit_value: int = 4000):
        """Initialize the SimpleContextCreator.
        
        Args:
            token_limit_value (int): Maximum number of tokens allowed in context.
        """
        self._token_limit = token_limit_value
        
    @property
    def token_limit(self) -> int:
        """Returns the maximum number of tokens allowed in the generated context."""
        return self._token_limit
        
    def create_context(
        self,
        records: List[Dict[str, Any]],
    ) -> Tuple[List[OpenAIMessage], int]:
        """Creates conversational context from the provided records.
        
        This implementation simply takes the most recent records that fit within
        the token limit. A more sophisticated implementation would use token counting.
        
        Args:
            records (List[Dict[str, Any]]): A list of context records.
            
        Returns:
            Tuple[List[OpenAIMessage], int]: A tuple containing the constructed
                context in OpenAIMessage format and the estimated token count.
        """
        messages = []
        total_tokens = 0
        
        # Simple token estimation (very rough)
        for record in records:
            # 从记录中获取消息对象
            message = record.get("message", {})
            
            # 处理 BaseMessage 对象
            if hasattr(message, 'role_type') and hasattr(message, 'content'):
                # 如果是 BaseMessage 对象，转换为字典格式
                role = message.role_type.lower()
                content = message.content
                # 将 BaseMessage 转换为 OpenAI 消息格式
                message_dict = {"role": role, "content": content}
                # 使用字典格式进行估算
                estimated_tokens = len(content) // 4
            else:
                # 处理字典格式的消息
                content = ""
                if isinstance(message, dict) and "content" in message:
                    content = message.get("content", "")
                else:
                    # 尝试其他可能的格式
                    try:
                        if hasattr(message, "get"):
                            content = message.get("content", "")
                        elif hasattr(message, "content"):
                            content = message.content
                        else:
                            content = str(message)
                    except:
                        content = str(message)
                
                message_dict = message  # 保留原始消息
                # 估算 tokens
                estimated_tokens = len(content) // 4
            
            if total_tokens + estimated_tokens <= self.token_limit:
                messages.append(message_dict)
                total_tokens += estimated_tokens
            else:
                break
                
        return messages, total_tokens


class ChatHistoryMemory(AgentMemory):
    """Memory component for storing and managing chat history.
    
    This class implements the AgentMemory interface for chat history storage.
    It can store messages in memory or in a MySQL database.
    """
    
    def __init__(
        self, 
        agent_id_value: Optional[str] = None,
        db_config: Optional[Dict[str, Any]] = None,
        token_limit: int = 4000
    ):
        """Initialize the ChatHistoryMemory.
        
        Args:
            agent_id_value (Optional[str]): ID of the agent using this memory.
            db_config (Optional[Dict[str, Any]]): MySQL database configuration.
            token_limit (int): Maximum token limit for context creation.
        """
        self._agent_id = agent_id_value
        self._db_config = db_config
        self._token_limit = token_limit
        self._messages = []
        self._context_creator = SimpleContextCreator(token_limit)
        
        # Initialize database connection if config is provided
        self._db_connection = None
        if db_config:
            self._init_db_connection()
            
    def _init_db_connection(self):
        """Initialize the database connection and create tables if needed."""
        try:
            self._db_connection = mysql.connector.connect(**self._db_config)
            cursor = self._db_connection.cursor()
            
            # Create chat_history table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    agent_id VARCHAR(255),
                    role VARCHAR(50),
                    content TEXT,
                    timestamp DATETIME,
                    metadata TEXT
                )
            """)
            self._db_connection.commit()
            cursor.close()
        except Exception as e:
            print(f"Database connection error: {str(e)}")
            self._db_connection = None
    
    @property
    def agent_id(self) -> Optional[str]:
        """Returns the agent ID associated with this memory."""
        return self._agent_id
        
    @agent_id.setter
    def agent_id(self, val: Optional[str]) -> None:
        """Sets the agent ID associated with this memory."""
        self._agent_id = val
    
    def write_records(self, records: List[Dict[str, Any]]) -> None:
        """Writes records to the memory.
        
        Args:
            records (List[Dict[str, Any]]): Records to be added to the memory.
        """
        # Store in memory
        self._messages.extend(records)
        
        # Store in database if available
        if self._db_connection:
            try:
                cursor = self._db_connection.cursor()
                for record in records:
                    message = record.get("message", {})
                    role = message.get("role", "")
                    content = message.get("content", "")
                    metadata = str(record.get("metadata", {}))
                    
                    cursor.execute("""
                        INSERT INTO chat_history 
                        (agent_id, role, content, timestamp, metadata)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        self._agent_id,
                        role,
                        content,
                        datetime.now(),
                        metadata
                    ))
                self._db_connection.commit()
                cursor.close()
            except Exception as e:
                print(f"Database write error: {str(e)}")
    
    def add_message(self, message: Union[BaseMessage, Dict[str, Any]]) -> None:
        """Add a message to the chat history.
        
        Args:
            message: The message to add to history. Can be a BaseMessage object or a dictionary.
        """
        # 处理不同的消息格式
        message_to_store = message
        
        # 如果已经是字典格式，直接使用
        if isinstance(message, dict):
            # 已经是字典格式
            pass
        # 如果是 BaseMessage 对象，保留原始对象
        elif hasattr(message, 'role_type') and hasattr(message, 'content'):
            # 是 BaseMessage 对象，保留原始对象
            pass
        else:
            # 尝试转换为字典格式
            try:
                if hasattr(message, 'to_dict'):
                    message_to_store = message.to_dict()
                elif hasattr(message, 'to_openai_message'):
                    message_to_store = message.to_openai_message()
                else:
                    # 最后尝试创建一个简单的字典
                    message_to_store = {
                        "role": getattr(message, "role", "user"),
                        "content": str(getattr(message, "content", message))
                    }
            except Exception as e:
                # 如果转换失败，创建一个简单的默认字典
                message_to_store = {
                    "role": "user",
                    "content": str(message)
                }
        
        # 创建记录
        record = {
            "message": message_to_store,
            "timestamp": datetime.now().isoformat(),
            "metadata": {}
        }
        
        # 写入记录
        self.write_record(record)
    
    def clear(self) -> None:
        """Clears all messages from the memory."""
        self._messages = []
        
        # Clear from database if available
        if self._db_connection and self._agent_id:
            try:
                cursor = self._db_connection.cursor()
                cursor.execute(
                    "DELETE FROM chat_history WHERE agent_id = %s",
                    (self._agent_id,)
                )
                self._db_connection.commit()
                cursor.close()
            except Exception as e:
                print(f"Database clear error: {str(e)}")
    
    def retrieve(self) -> List[Dict[str, Any]]:
        """Get a record list from the memory for creating model context.
        
        Returns:
            List[Dict[str, Any]]: A record list for creating model context.
        """
        # If we have in-memory messages, return those
        if self._messages:
            return self._messages
            
        # Otherwise try to retrieve from database
        if self._db_connection and self._agent_id:
            try:
                cursor = self._db_connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT role, content, timestamp, metadata 
                    FROM chat_history 
                    WHERE agent_id = %s
                    ORDER BY timestamp ASC
                    """,
                    (self._agent_id,)
                )
                
                records = []
                for row in cursor.fetchall():
                    record = {
                        "message": {
                            "role": row["role"],
                            "content": row["content"]
                        },
                        "timestamp": row["timestamp"].isoformat(),
                        "metadata": row["metadata"]
                    }
                    records.append(record)
                
                cursor.close()
                return records
            except Exception as e:
                print(f"Database retrieve error: {str(e)}")
                
        return []
    
    def get_context_creator(self) -> BaseContextCreator:
        """Gets context creator.
        
        Returns:
            BaseContextCreator: A model context creator.
        """
        return self._context_creator
