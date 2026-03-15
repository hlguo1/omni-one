import os
import weaviate
from weaviate.classes.config import Configure
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Weaviate
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI  # or use litellm

class RAGEngine:
    def __init__(self):
        self.client = None
        self.embedder = None
        self.text_splitter = None
        self.collection_name = "EnterpriseKnowledge"
        self.connected = False

        try:
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
            print(f"Weaviate connection failed: {e}. RAG features will be limited.")
            self.connected = False

    def add_documents(self, documents, metadata=None):
        """Add documents to the vector store."""
        if not self.connected:
            print("Weaviate not connected, skipping document addition")
            return

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
            return []  # Return empty list if not connected

        try:
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
        """Generate response using RAG."""
        # Retrieve relevant docs
        docs = self.retrieve(query)
        context = "\n\n".join([doc.page_content for doc in docs])

        # Use litellm for multi-model support
        import litellm
        litellm.api_key = os.getenv('GOOGLE_API_KEY')  # or set appropriately

        prompt = f"Context:\n{context}\n\nQuery: {query}\n\nAnswer based on the context:"

        response = litellm.completion(
            model=f"gemini/{model}",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    def close(self):
        self.client.close()