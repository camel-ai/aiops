from abc import ABC, abstractmethod
from typing import Any, Callable, List, Dict, Optional

DEFAULT_TOP_K_RESULTS = 5


def _query_unimplemented(self, *input: Any) -> None:
    """Defines the query behavior performed at every call.

    Query the results. Subclasses should implement this
    method according to their specific needs.

    It should be overridden by all subclasses.
    """
    raise NotImplementedError(
        f"Retriever [{type(self).__name__}] is missing the required "
        "\"query\" function"
    )


def _process_unimplemented(self, *input: Any) -> None:
    """Defines the process behavior performed at every call.

    Processes content from a file or URL, divides it into chunks,
    then stored internally. This method must be called before 
    executing queries with the retriever.

    Should be overridden by all subclasses.
    """
    raise NotImplementedError(
        f"Retriever [{type(self).__name__}] is missing the required "
        "\"process\" function"
    )


class BaseRetriever(ABC):
    """Abstract base class for implementing various types of information retrievers.
    
    This class defines the interface for retrievers that can process documents
    and retrieve relevant information based on queries.
    """

    @abstractmethod
    def __init__(self) -> None:
        """Initialize a BaseRetriever."""
        pass

    process: Callable[..., Any] = _process_unimplemented
    query: Callable[..., Any] = _query_unimplemented
    
    def get_relevant_documents(
        self, 
        query: str, 
        top_k: int = DEFAULT_TOP_K_RESULTS
    ) -> List[Dict[str, Any]]:
        """Get documents relevant to the query.
        
        Args:
            query: The query string.
            top_k: Number of top results to return.
            
        Returns:
            List[Dict[str, Any]]: List of relevant documents.
        """
        return self.query(query, top_k=top_k)
