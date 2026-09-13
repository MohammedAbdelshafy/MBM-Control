from typing import Dict, Any

class RagFlowAdapter:
    """
    Adapter for infiniflow/ragflow.
    Exposes RAG_ENGINE pointing to containerized REST APIs.
    """
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    def retrieve_context(self, query: str) -> Dict[str, Any]:
        # TODO: Call RAGFlow API
        return {"query": query, "context": ["mock chunk 1", "mock chunk 2"]}