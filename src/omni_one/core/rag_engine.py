"""RAG engine (optional, paid deps). NEVER imported by Seller OS path — lazy only.

Kept for enterprise labs. All heavy imports are lazy so `pip install -r requirements-seller.txt`
works offline without torch/weaviate/langchain.
"""
import os


class RAGEngine:
    """Lazy RAG. Raises helpful error if optional deps missing (seller path never calls this)."""

    def __init__(self):
        self.client = None
        self.embedder = None
        self.text_splitter = None
        self.collection_name = "EnterpriseKnowledge"
        self.connected = False
        self._error: str | None = None

        try:
            import weaviate  # type: ignore
            from weaviate.classes.config import Configure  # type: ignore
            from langchain_community.embeddings import SentenceTransformerEmbeddings  # type: ignore
            from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
            # Try to connect to Weaviate
            self.client = weaviate.connect_to_local()
            self.connected = True

            # Initialize embedding model
            self.embedder = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

            # Text splitter for chunking
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )

            # Create collection if not exists
            if not self.client.collections.exists(self.collection_name):
                self.client.collections.create(
                    self.collection_name,
                    vectorizer_config=Configure.Vectorizer.text2vec_transformers(),
                    generative_config=Configure.Generative.openai()  # or other
                )

        except Exception as e:
            self._error = str(e)
            self.connected = False

    def add_documents(self, documents, metadata=None):
        """Add documents to the vector store."""
        if not self.connected:
            raise RuntimeError(
                "RAG not available offline (needs weaviate + sentence-transformers). "
                f"Install enterprise extras or use free Jaccard cache. Cause: {self._error}"
            )

        try:
            texts = []
            metadatas = []

            for doc in documents:
                chunks = self.text_splitter.split_text(doc['content'])
                for chunk in chunks:
                    texts.append(chunk)
                    metadatas.append({
                        'source': doc.get('source', 'unknown'),
                        'type': doc.get('type', 'document'),
                        'timestamp': doc.get('timestamp', None),
                        **(metadata or {})
                    })

            # Add to Weaviate
            vectorstore = Weaviate(
                client=self.client,
                index_name=self.collection_name,
                text_key="content",
                embedding=self.embedder
            )
            vectorstore.add_texts(texts, metadatas)
        except Exception as e:
            print(f"Failed to add documents: {e}")

    def retrieve(self, query, k=5):
        """Retrieve relevant documents for a query."""
        if not self.connected:
            return []  # Return empty list if not connected (offline-safe)

        try:
            from langchain_community.vectorstores import Weaviate  # type: ignore
            vectorstore = Weaviate(
                client=self.client,
                index_name=self.collection_name,
                text_key="content",
                embedding=self.embedder
            )
            docs = vectorstore.similarity_search(query, k=k)
            return docs
        except Exception as e:
            print(f"RAG retrieval failed: {e}")
            return []

    def generate_with_rag(self, query, model="gemini-2.5-flash"):
        """Generate response using RAG (requires GOOGLE_API_KEY + enterprise extras)."""
        # Retrieve relevant docs
        docs = self.retrieve(query)
        context = "\n\n".join([doc.page_content for doc in docs])

        # Use litellm for multi-model support
        try:
            import litellm  # type: ignore
        except ImportError as e:
            raise RuntimeError(f"litellm not installed (enterprise extra): {e}")
        litellm.api_key = os.getenv('GOOGLE_API_KEY')  # or set appropriately

        prompt = f"Context:\n{context}\n\nQuery: {query}\n\nAnswer based on the context:"

        response = litellm.completion(
            model=f"gemini/{model}",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    def close(self):
        try:
            if self.client is not None:
                self.client.close()
        except Exception:
            pass