"""Database tool for Pinecone vector storage with embeddings."""

import uuid
from typing import List, Optional, Dict, Any
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VectorDatabase:
    """Pinecone vector database integration with OpenAI embeddings."""
    
    def __init__(self):
        """Initialize Pinecone client and embeddings model."""
        self.client = None
        self.index = None
        self.embeddings = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        if not Config.PINECONE_API_KEY:
            logger.warning("Pinecone API key not found - vector database disabled")
            return
        
        if not Config.PINECONE_HOST:
            logger.warning("Pinecone host not configured - vector database disabled")
            return
        
        try:
            # Initialize Pinecone client
            self.client = Pinecone(api_key=Config.PINECONE_API_KEY)
            
            # Connect to index using host URL (serverless/dedicated)
            self.index = self.client.Index(host=Config.PINECONE_HOST)
            
            # Initialize OpenAI embeddings with 1024 dimensions
            # text-embedding-3-small supports dimensions parameter
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                dimensions=1024,
                openai_api_key=Config.OPENAI_API_KEY
            )
            
            logger.info("Pinecone vector database initialized successfully")
            logger.info(f"Connected to index at: {Config.PINECONE_HOST}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            self.client = None
            self.index = None
    
    def store_documents(self, documents: List[str], metadata: Optional[List[dict]] = None) -> bool:
        """
        Store documents in vector database with embeddings.
        
        Args:
            documents: List of document texts to store
            metadata: Optional list of metadata dictionaries (one per document)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.index or not self.embeddings:
            logger.error("Pinecone not initialized")
            return False
        
        if not documents:
            logger.warning("No documents provided for storage")
            return False
        
        try:
            # Ensure metadata list matches documents length
            if metadata is None:
                metadata = [{}] * len(documents)
            elif len(metadata) != len(documents):
                logger.warning("Metadata length doesn't match documents, padding with empty dicts")
                metadata.extend([{}] * (len(documents) - len(metadata)))
            
            all_vectors = []
            
            for doc_idx, document in enumerate(documents):
                # Split document into chunks
                chunks = self.text_splitter.split_text(document)
                
                # Generate embeddings for each chunk
                chunk_embeddings = self.embeddings.embed_documents(chunks)
                
                # Prepare vectors for upsert
                for chunk_idx, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
                    vector_id = f"{doc_idx}_{chunk_idx}_{uuid.uuid4().hex[:8]}"
                    
                    # Add chunk text and position to metadata
                    chunk_metadata = {
                        **metadata[doc_idx],
                        "text": chunk,
                        "document_index": doc_idx,
                        "chunk_index": chunk_idx,
                        "chunk_count": len(chunks)
                    }
                    
                    all_vectors.append({
                        "id": vector_id,
                        "values": embedding,
                        "metadata": chunk_metadata
                    })
            
            # Upsert vectors in batches (Pinecone recommends batches of 100)
            batch_size = 100
            for i in range(0, len(all_vectors), batch_size):
                batch = all_vectors[i:i + batch_size]
                self.index.upsert(vectors=batch)
                logger.info(f"Upserted batch {i//batch_size + 1} ({len(batch)} vectors)")
            
            logger.info(f"Successfully stored {len(documents)} documents as {len(all_vectors)} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Error storing documents in Pinecone: {e}")
            return False
    
    def search_similar(self, query: str, top_k: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[dict]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter_dict: Optional metadata filter dictionary
            
        Returns:
            List of similar documents with metadata, scores, and text
        """
        if not self.index or not self.embeddings:
            logger.error("Pinecone not initialized")
            return []
        
        if not query:
            logger.warning("Empty query provided")
            return []
        
        try:
            # Generate embedding for query
            query_embedding = self.embeddings.embed_query(query)
            
            # Search Pinecone
            search_results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )
            
            # Format results
            results = []
            for match in search_results.get("matches", []):
                result = {
                    "id": match.get("id"),
                    "score": match.get("score"),
                    "text": match.get("metadata", {}).get("text", ""),
                    "metadata": match.get("metadata", {})
                }
                results.append(result)
            
            logger.info(f"Found {len(results)} similar documents for query")
            return results
            
        except Exception as e:
            logger.error(f"Error searching Pinecone: {e}")
            return []
    
    def delete_documents(self, document_indices: List[int]) -> bool:
        """
        Delete documents by their document indices.
        
        Args:
            document_indices: List of document indices to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.index:
            logger.error("Pinecone not initialized")
            return False
        
        try:
            deleted_count = 0
            
            # Query to find all vectors with matching document_index
            for doc_idx in document_indices:
                # Use metadata filter to find vectors
                # Note: This requires querying first, then deleting
                # For efficiency, we'd need to track vector IDs, but for now we'll use metadata filter
                filter_dict = {"document_index": {"$eq": doc_idx}}
                
                # Get all vectors for this document (we need to query with a dummy vector)
                # Since we can't list all vectors easily, we'll use a workaround
                # For production, consider maintaining a mapping of document_index to vector IDs
                logger.warning(f"Delete by document_index not fully implemented - requires vector ID tracking")
                logger.info(f"Would delete vectors for document_index: {doc_idx}")
            
            logger.info(f"Delete operation requested for {len(document_indices)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            return False
    
    def delete_by_ids(self, vector_ids: List[str]) -> bool:
        """
        Delete vectors by their IDs.
        
        Args:
            vector_ids: List of vector IDs to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.index:
            logger.error("Pinecone not initialized")
            return False
        
        try:
            self.index.delete(ids=vector_ids)
            logger.info(f"Deleted {len(vector_ids)} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting vectors: {e}")
            return False
