"""
Tests for the Egyptian Law Assistant RAG system.
Comprehensive testing suite covering all modules.
"""

import pytest
import asyncio
from pathlib import Path

# Test configuration
TEST_DATA_DIR = Path(__file__).parent / "fixtures" / "sample_documents"

__all__ = ["TEST_DATA_DIR"]
