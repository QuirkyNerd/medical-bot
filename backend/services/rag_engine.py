#!/usr/bin/env python3
"""
backend/services/rag_engine.py
==============================
RAG Engine Test Script

Tests the RAG pipeline components:
- Qdrant connection
- Collection status
- RAG agent functionality
"""

from core.vectorstore import get_vectorstore, close_vectorstore
from agents.rag_agent import RagAgent
from agents.router_agent import QueryIntent


class RAGEngine:
    def __init__(self):
        from core.vectorstore import get_vectorstore
        self.vs = get_vectorstore()

    def collection_counts(self):
        return self.vs.status()


def test_qdrant_connection():
    """Test Qdrant connection and collection status."""
    print("🔍 Testing Qdrant connection...")

    try:
        vs = get_vectorstore()
        print("✅ Qdrant connection established")

        status = vs.status()
        print("📊 Collection counts:")
        for collection, count in status.items():
            print(f"   {collection}: {count} vectors")

        return True
    except Exception as e:
        print(f"❌ Qdrant connection failed: {e}")
        return False

def test_rag_agent():
    """Test RAG agent with a sample query."""
    print("\n🤖 Testing RAG Agent...")

    try:
        # RagAgent handles vs internally or accepts it
        vs = get_vectorstore()
        rag_agent = RagAgent(vectorstore=vs, top_k=5)

        # Sample query
        query = "What are the symptoms of diabetes?"
        intent = QueryIntent.GENERAL_KNOWLEDGE

        result = rag_agent.retrieve(query, intent)

        print(f"✅ RAG retrieval successful")
        print(f"   Query: {query}")
        print(f"   Chunks retrieved: {len(result.chunks)}")
        print(f"   Confidence: {result.confidence:.3f}")
        print(f"   Collections searched: {result.collections_searched}")

        # Basic validation
        if len(result.chunks) == 0 and vs.count("global_knowledge") > 0:
            print("   ⚠️ Warning: No chunks retrieved but collection is not empty.")

        return True
    except Exception as e:
        print(f"❌ RAG agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🚀 Starting RAG Engine Test")
    print("=" * 50)

    # Test Qdrant
    qdrant_ok = test_qdrant_connection()

    # Test RAG if Qdrant is OK
    if qdrant_ok:
        rag_ok = test_rag_agent()
    else:
        rag_ok = False

    print("\n" + "=" * 50)
    if qdrant_ok and rag_ok:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above.")

    # 5. Cleanup
    close_vectorstore()

if __name__ == "__main__":
    main()