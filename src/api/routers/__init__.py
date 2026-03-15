"""
API routers for different endpoints.
"""

from . import health, query

__all__ = ["health", "query"]
from .query import router as query_router

__all__ = ["ingestion_router", "query_router"]
