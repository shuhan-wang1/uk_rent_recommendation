"""
Centralized LLM Configuration for LangGraph Agent

Provides ChatOllama instances with appropriate settings for different tasks:
- react_llm: Low temperature for deterministic response generation
- classification_llm: High temperature for diverse tool voting
"""

from langchain_ollama import ChatOllama

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "gemma3:27b-cloud"


def get_react_llm() -> ChatOllama:
    """LLM for agent reasoning and response generation (low temperature)."""
    return ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        temperature=0.1,
        top_p=0.9,
        num_predict=4000,
        num_ctx=8192,
    )


def get_classification_llm() -> ChatOllama:
    """LLM for tool classification voting (high temperature for diversity)."""
    return ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        temperature=0.7,
        top_p=0.95,
        top_k=40,
        num_predict=50,
        num_ctx=4096,
    )


def get_planning_llm() -> ChatOllama:
    """LLM for search planning (high temperature for creative query generation)."""
    return ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        temperature=0.8,
        top_p=0.9,
        num_predict=2000,
        num_ctx=8192,
    )
