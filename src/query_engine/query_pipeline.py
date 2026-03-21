"""
Async query pipeline for the Egyptian Law Assistant.

Pipeline stages (in execution order):
  QueryRequest (domain)
      ↓  load_index()                   ← knowledge_base boundary
  VectorStoreIndex (LlamaIndex)
      ↓  get_retriever(top_k=20)        ← broad initial retrieval
  NodeWithScore × 20
      ↓  CrossEncoderReranker(top_n=5)  ← semantic reranking (runs first on clean text)
  NodeWithScore × 5
      ↓  MetadataMappingPostprocessor   ← [المصدر:] citation formatting (runs second)
  Formatted context nodes
      ↓  RetrieverQueryEngine (simple_summarize + Arabic prompt)
  Response (LlamaIndex)
      ↓  map_response()                 ← response_synthesizer.py (domain boundary exit)
  QueryResponse (domain)               ← only this leaves the module

CRITICAL FIX — English leakage root cause and solution:

  OLD CODE: response_mode="compact"
    LlamaIndex "compact" uses TWO templates:
    1. text_qa_template  → our Arabic prompt (correct)
    2. refine_template   → LlamaIndex's DEFAULT English template (the leaker)

    When 20 retrieved nodes exceed the context window after compaction,
    LlamaIndex invokes the English REFINE_PROMPT:
    "The original query is: ... We have the opportunity to refine..."
    Receiving this English context causes llama3 to switch to English.

  NEW CODE: response_mode="simple_summarize"
    - Concatenates all node texts, truncates to fit ONE context window
    - Calls text_qa_template exactly ONCE — no refine_template ever
    - 5 reranked articles (~3k tokens) + prompt (~900 chars) fits llama3's 8k window
"""

from __future__ import annotations

import asyncio
import functools
import logging
import sys
from pathlib import Path
from typing import Any, List, Optional

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.prompts import PromptTemplate
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.schema import NodeWithScore, QueryBundle

from src.core.config import Settings, get_settings
from src.core.exceptions import EmptyRetrievalError, LLMProviderError, RetrievalError
from src.core.schemas import QueryRequest, QueryResponse
from src.knowledge_base.indexer import load_index
from src.llm_providers.llm_factory import get_llm
from src.query_engine.response_synthesizer import map_response
from src.query_engine.retriever import get_retriever

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ── Arabic QA Prompt ───────────────────────────────────────────────────────────
#
# Engineering rationale for each design choice:
#
# [1] Persona first — Llama 3 responds to role identity more strongly than
#     rule lists. "أنت مستشار قانوني مصري متخصص" establishes the character
#     before any rules are stated. The character then "speaks Arabic" as a
#     natural extension of who it is.
#
# [2] Character-level prohibition — "حرف لاتيني" (Latin character) is more
#     concrete than "don't use English." The model understands the Arabic/Latin
#     script distinction at the byte level.
#
# [3] Arabic-Indic ordinals (١٢٣٤) for the rule list — keeps the entire
#     non-template body of the prompt in Arabic script. The model treats
#     the prompt's dominant script as a signal for the response's script.
#
# [4] No bracket placeholders [like this] in the format guide — brackets
#     signal "fill in any language here." The format guide uses explicit
#     Arabic descriptive text so the model understands "Arabic goes here."
#
# [5] Forced completion prefix — the prompt ends with the required opening
#     phrase "وفقاً للتشريعات المصرية،". For Ollama's /api/generate
#     (completion) endpoint, the model continues directly from this token.
#     For /api/chat, it acts as a final instruction and a strong first-token
#     cue. Either way, the model has zero ambiguity about where to start.
#
_ARABIC_QA_PROMPT = (
    "أنت مستشار قانوني مصري متخصص. مهمتك الوحيدة هي الإجابة عن الأسئلة القانونية "
    "بالعربية الفصحى الرسمية استناداً إلى النصوص التشريعية المقدمة.\n\n"

    "استثناء التحيات (Greetings Exception):\n"
    "إذا كان إدخال المستخدم مجرد تحية أو دردشة بسيطة (مثل: أهلاً، كيف حالك، اخبارك)، "
    "فقم برد التحية بحفاوة بصفتك مساعد قانوني ذكي واطلب منه بتهذيب طرح استفساره القانوني. "
    "يُمنع منعاً باتاً استخدام التنسيق الهيكلي (الحكم، السند، التفاصيل) للتحيات البسيطة. "
    "احتفظ بهذا التنسيق الصارم للأسئلة القانونية الفعلية فقط.\n\n"

    "تحذير صارم لا استثناء فيه: يُحظر تماماً استخدام أي حرف لاتيني في إجابتك. "
    "كل كلمة وكل حرف يجب أن يكون عربياً. المخالفة تُبطل الإجابة كاملاً.\n\n"

    "النصوص القانونية المرجعية:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"

    "السؤال: {query_str}\n\n"

    "القواعد الإلزامية للإجابة (في حال كان السؤال قانونياً وليس تحية):\n"
    "١. ابدأ إجابتك بعبارة \"وفقاً للتشريعات المصرية،\" كتمهيد.\n"
    "٢. اعتمد فقط على النصوص الواردة في السياق أعلاه. لا تستحضر معلومات من خارجها.\n"
    "٣. إن لم تتضمن النصوص المتاحة إجابةً كافية، فاكتب حرفياً: "
    "\"عذراً، لا يوجد نص صريح في المواد المتاحة بشأن هذه المسألة.\"\n"
    "٤. قدّم إجابتك بالتنسيق الآتي بالضبط:\n\n"
    "**الحكم القانوني:** اكتب الحكم الرئيسي في جملة واحدة مباشرة\n"
    "**السند القانوني:** اكتب اسم القانون ورقم المادة\n"
    "**التفاصيل:** اكتب الشرح المفصل المستند إلى النص\n"
)

# Rewrite prompt: colloquial Arabic → formal legal Arabic.
# Must be concise — this is an extra LLM call on the critical path.
_REWRITE_PROMPT = (
    "أعد صياغة السؤال التالي بالعربية القانونية الفصحى الدقيقة لتسهيل البحث "
    "في النصوص التشريعية. اكتب السؤال المعاد صياغته فقط بدون أي شرح:\n"
    "السؤال: {query}"
)


def _is_arabic_clean(text: str) -> bool:
    """
    Returns True if text contains ONLY Arabic script, digits, spaces,
    and punctuation. Rejects any Latin/Cyrillic/foreign alphabet characters.
    Used to validate query rewrites before using them.
    """
    if not text or not text.strip():
        return False
    for char in text:
        if char.isspace() or char.isdigit():
            continue
        cp = ord(char)
        if 0x0600 <= cp <= 0x06FF:   # Arabic core
            continue
        if 0x0750 <= cp <= 0x077F:   # Arabic Supplement
            continue
        if 0x08A0 <= cp <= 0x08FF:   # Arabic Extended-A
            continue
        if 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:  # Presentation Forms
            continue
        if char in '،؟!.()؛:»«,?!;:-–—…"\'':
            continue
        if char.isalpha():
            return False  # Any foreign alphabetic character → reject
    return True


# ── Post-processors ────────────────────────────────────────────────────────────

class CrossEncoderReranker(BaseNodePostprocessor):
    """
    Reranks nodes using a HuggingFace cross-encoder model.

    Pipeline position: FIRST — must run on clean node text before
    MetadataMappingPostprocessor reformats the node content.

    Graceful degradation: if sentence-transformers is not installed,
    returns first top_n nodes unchanged with a warning.
    Install with: pip install sentence-transformers
    """

    model_name: str = "BAAI/bge-reranker-v2-m3"
    top_n: int = 5
    _model: Any = PrivateAttr()

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        top_n: int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, top_n=top_n, **kwargs)
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name, max_length=512)
            logger.info("CrossEncoderReranker loaded: %s", self.model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed — reranking disabled. "
                "pip install sentence-transformers"
            )
            self._model = None

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        if self._model is None or not nodes:
            return nodes[: self.top_n]

        if query_bundle is None:
            logger.warning("CrossEncoderReranker: no query_bundle — skipping rerank.")
            return nodes[: self.top_n]

        pairs = [[query_bundle.query_str, n.node.text] for n in nodes]
        scores = self._model.predict(pairs)

        for node, score in zip(nodes, scores):
            node.score = float(score)

        reranked = sorted(nodes, key=lambda x: x.score or 0.0, reverse=True)
        logger.debug(
            "Reranked %d → %d nodes. Top score: %.4f",
            len(nodes), self.top_n,
            reranked[0].score if reranked else 0.0,
        )
        return reranked[: self.top_n]

    @classmethod
    def class_name(cls) -> str:
        return "CrossEncoderReranker"


class MetadataMappingPostprocessor(BaseNodePostprocessor):
    """
    Formats each node into the Arabic citation block required by the QA prompt.

    Pipeline position: SECOND — must run after CrossEncoderReranker so
    the cross-encoder scores clean article text, not citation-wrapped text.

    Output format per node:
        [المصدر: اسم القانون - المادة N]
        نص المادة: ...the original article text...

    Idempotency: stores original text in _original_text metadata before
    first rewrite so a second run rewrites from original, not from the
    already-formatted citation block.
    """

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        for n in nodes:
            meta = n.node.metadata or {}
            
            # Try explicit law_name first, then derive from source filename,
            # then fall back to generic Arabic label (never English "Unknown Law")
            law_name = meta.get("law_name") or ""
            if not law_name:
                source_file = meta.get("source_file", "")
                if "corporate" in source_file.lower() or "شركات" in source_file:
                    law_name = "قانون الشركات 159 لسنة 1981"
                elif "civil" in source_file.lower() or "مدني" in source_file:
                    law_name = "القانون المدني المصري"
                elif source_file:
                    law_name = source_file.replace(".txt", "").replace("_", " ")
                else:
                    law_name = "التشريع المصري"

            article_raw = meta.get("article_number", "")

            if str(article_raw).startswith("المادة"):
                article_str = str(article_raw)
            elif article_raw:
                article_str = f"المادة {article_raw}"
            else:
                article_str = f"المادة {n.node.id_[:8]}"

            section = meta.get("section", "")
            section_part = f" - {section}" if section else ""

            # Idempotency guard: preserve original text on first pass
            original_text = meta.get("_original_text")
            if not original_text:
                original_text = n.node.text
                n.node.metadata["_original_text"] = original_text

            # Set text_template BEFORE set_content so LlamaIndex's
            # get_content() uses our template, not its default metadata format.
            n.node.text_template = "{content}"
            n.node.metadata_template = ""
            n.node.set_content(
                f"[المصدر: {law_name} - {article_str}{section_part}]\n"
                f"نص المادة: {original_text}"
            )

        return nodes

    @classmethod
    def class_name(cls) -> str:
        return "MetadataMappingPostprocessor"


# ── Core Pipeline ──────────────────────────────────────────────────────────────

async def execute_query(
    request: QueryRequest,
    settings: Settings | None = None,
) -> QueryResponse:
    """
    Execute a full RAG query and return a domain ``QueryResponse``.
    """
    active_settings = settings or get_settings()
    provider = active_settings.llm_provider

    logger.info(
        "Executing query: top_k=%d  provider=%r  query=%r",
        request.top_k, provider, request.query[:80],
    )

    # ── Step 1: Load index ─────────────────────────────────────────────────────
    try:
        index = load_index(settings=active_settings)
    except Exception as exc:
        raise RetrievalError(
            f"Failed to load index from Pinecone: {exc}. "
            "Run `make ingest` to populate the index before querying."
        ) from exc

    # ── Step 2: Broad retrieval (top-20 candidates for the reranker) ───────────
    retriever = get_retriever(index, top_k=20)

    # ── Step 3: Load LLM ───────────────────────────────────────────────────────
    try:
        llm = get_llm(active_settings)
    except Exception as exc:
        raise LLMProviderError(
            provider=provider,
            reason=f"Failed to initialise LLM provider: {exc}",
            retryable=False,
        ) from exc

    # ── Step 4: Query rewriting (colloquial → formal legal Arabic) ─────────────
    # Best-effort: on any failure, fall back to the original query silently.
    # Guard: reject rewrites that are empty or suspiciously long (>500 chars
    # signals the model started answering instead of rewriting).
    rewritten_query = request.query
    try:
        logger.info(">>>> TRACKER: Step 4 - Sending query to Groq for REWRITING...")
        # Wrap the rewrite call in a 10-second timeout to prevent the API from hanging
        rewrite_result = await asyncio.wait_for(
            llm.acomplete(_REWRITE_PROMPT.format(query=request.query)),
            timeout=10.0
        )
        logger.info(">>>> TRACKER: Step 4 - Query rewriting DONE!")
        candidate = rewrite_result.text.strip()
        if candidate and len(candidate) < 500 and _is_arabic_clean(candidate):
            rewritten_query = candidate
            logger.info(
                "Query rewritten:\n  Original : %r\n  Rewritten: %r",
                request.query, rewritten_query,
            )
        elif candidate and not _is_arabic_clean(candidate):
            logger.warning(
                "Query rewrite rejected — contains non-Arabic characters: %r. "
                "Using original query.",
                candidate,
            )
        else:
            logger.warning("Query rewrite empty/oversized — using original.")
    except Exception as exc:
        logger.warning("Query rewriting failed/timed out (%s) — using original query.", exc)

    # ── Step 5: Assemble query engine ──────────────────────────────────────────
    #
    # response_mode="simple_summarize" ← THE FIX FOR ENGLISH LEAKAGE
    #
    # See module docstring for full explanation.
    # In short: simple_summarize calls our Arabic template ONCE.
    # compact would call the English refine_template on overflow → leaks English.
    #
    # Post-processor ORDER IS MANDATORY:
    #   [0] CrossEncoderReranker   — scores clean text, must run FIRST
    #   [1] MetadataMappingPostprocessor — formats text, must run SECOND
    top_n = request.top_k if request.top_k else 5
    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        llm=llm,
        response_mode="simple_summarize",       # ← THE FIX
        text_qa_template=PromptTemplate(_ARABIC_QA_PROMPT),
        node_postprocessors=[
            CrossEncoderReranker(top_n=top_n),  # 1st: score on clean text
            MetadataMappingPostprocessor(),      # 2nd: format citation headers
        ],
    )

    # ── Step 6: Execute query (async, non-blocking) ────────────────────────────
    raw_response = await _run_query(query_engine, rewritten_query)

    # ── Step 7: Domain boundary exit ──────────────────────────────────────────
    return map_response(raw_response, provider=provider)


async def _run_query(query_engine: RetrieverQueryEngine, query_str: str) -> object:
    from llama_index.core.schema import QueryBundle
    from llama_index.core.settings import Settings as LlamaSettings
    
    try:
        bundle = QueryBundle(query_str)
        
        embed_model = getattr(query_engine.retriever, "_embed_model", LlamaSettings.embed_model)
        
        logger.info(">>>> TRACKER: Starting to generate embedding for query (Calling Cohere)...")
        if bundle.embedding is None and embed_model is not None:
            bundle.embedding = await embed_model.aget_text_embedding(query_str)
            
        logger.info(">>>> TRACKER: Embedding generated! Now querying ChromaDB...")
        nodes = await query_engine.aretrieve(bundle)
        
        logger.info(">>>> TRACKER: ChromaDB query done! Now sending prompt to Groq (LLM)...")
        res = await query_engine.asynthesize(bundle, nodes=nodes)
        
        logger.info(">>>> TRACKER: Groq responded! Returning answer to frontend.")
        return res

    except Exception as exc:
        exc_type = type(exc).__name__
        retryable = any(
            kw in exc_type.lower()
            for kw in ("timeout", "ratelimit", "connection", "unavailable")
        )
        raise LLMProviderError(
            provider="unknown",
            reason=f"Query execution failed ({exc_type}): {exc}",
            retryable=retryable,
        ) from exc


# ── CLI / Inspection Entry Point ───────────────────────────────────────────────

async def main() -> None:
    """
    Development entry point.
    Prerequisites: make ingest && ollama serve && ollama pull llama3
    Run with: python -m src.query_engine.query_pipeline
    """
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    test_query = "ما هي شروط تأسيس شركة المساهمة؟"
    print(f"\n{'=' * 60}")
    print("  Egyptian Law Assistant — Query Pipeline Test")
    print(f"{'=' * 60}")
    print(f"  Query   : {test_query}")
    print(f"  Provider: {get_settings().llm_provider}")
    print(f"  Model   : {get_settings().ollama_model}\n")

    request = QueryRequest(query=test_query, top_k=5)
    try:
        response = await execute_query(request)
    except (EmptyRetrievalError, LLMProviderError, RetrievalError) as exc:
        print(f"\n[ERROR] {getattr(exc, 'message', str(exc))}")
        return

    print(f"{'─' * 60}\n{response.answer}\n{'─' * 60}")
    for i, chunk in enumerate(response.source_chunks, 1):
        print(f"  [{i}] {chunk.article_number or 'Unknown'}  "
              f"score={chunk.metadata.get('similarity_score', 'N/A')}")
    print(f"\n  Provider: {response.llm_provider_used}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())