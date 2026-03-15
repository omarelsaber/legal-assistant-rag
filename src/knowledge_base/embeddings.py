"""

Embedding model factory for the Egyptian Law Assistant.



Responsibilities:

  - Return the correct LlamaIndex embedding model for the active LLM provider.

  - Fail fast with a ``ConfigurationError`` for unsupported providers so the

    error surfaces at startup, not mid-ingestion.



Architectural note:

  This module is the single place in the codebase that imports LlamaIndex

  embedding classes. If you ever swap the embedding library (e.g., from

  OllamaEmbedding to HuggingFaceEmbedding), this is the only file to change.



Supported providers (Architecture Decision #3  provider factory pattern):

  - "ollama"   OllamaEmbedding  (local, free, requires Ollama running)

  - "claude"   OllamaEmbedding  (Anthropic has no native embedding API;

                                   Ollama is still used for embeddings even

                                   when Claude is the generation provider.

                                   This is a deliberate design choice: keep

                                   the embedding model independent of the

                                   generation provider.)



Future providers to add here:

  - "openai"         OpenAIEmbedding

  - "huggingface"    HuggingFaceEmbedding (fully local, no Ollama required)

"""



from __future__ import annotations



import logging



from llama_index.core.base.embeddings.base import BaseEmbedding

from llama_index.embeddings.ollama import OllamaEmbedding



from src.core.config import Settings

from src.core.exceptions import ConfigurationError



logger = logging.getLogger(__name__)





def get_embedding_model(settings: Settings) -> BaseEmbedding:

    """

    Return a LlamaIndex embedding model configured for the active provider.



    The returned object satisfies LlamaIndex's ``BaseEmbedding`` protocol,

    so it can be passed directly to ``VectorStoreIndex`` and ``IngestionPipeline``

    without any adapter layer.



    Provider mapping:

      - ``"ollama"``   ``OllamaEmbedding`` pointing at ``settings.ollama_base_url``

      - ``"claude"``   Same as ``"ollama"``  see module docstring for rationale.

      - anything else  raises ``ConfigurationError`` immediately.



    Args:

        settings: The active Settings singleton.



    Returns:

        A configured ``BaseEmbedding`` instance ready for use.



    Raises:

        ConfigurationError: If ``settings.llm_provider`` has no registered

            embedding implementation. This fires at startup, not mid-request.



    Example::



        embed_model = get_embedding_model(settings)

        vectors = embed_model.get_text_embedding_batch(["sample text"])

    """

    provider = settings.llm_provider

    model_name = settings.embedding_model

    base_url = settings.ollama_base_url



    if provider in ("ollama", "claude"):

        # For "claude": generation uses Anthropic's API, but embeddings are

        # served locally via Ollama. This keeps embedding costs zero and

        # avoids vendor lock-in for the vector representation layer.

        logger.info(

            "Loading embedding model %r via Ollama at %s  (generation provider: %r)",

            model_name,

            base_url,

            provider,

        )

        return OllamaEmbedding(

            model_name=model_name,

            base_url=base_url,

            # request_timeout controls how long to wait for the first token

            # from the embedding server. Default (30s) is too short for a

            # cold-start with a large model; 120s is safe for local hardware.

            request_timeout=120.0,

        )



    #  Unsupported provider  fail fast 

    #

    # We raise ConfigurationError (not ValueError) so the FastAPI

    # exception_handlers.py can map it to a 500 with a structured body,

    # and so tests can catch it by type rather than by message string.

    raise ConfigurationError(

        setting="llm_provider",

        reason=(

            f"No embedding implementation registered for provider {provider!r}. "

            f"Supported values: 'ollama', 'claude'. "

            f"To add a new provider, extend get_embedding_model() in "

            f"src/knowledge_base/embeddings.py."

        ),

    )
