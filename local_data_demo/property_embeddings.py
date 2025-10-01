# property_embeddings.py
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

class PropertyEmbeddingStore:
    def __init__(self):
        print("    -> [DEBUG] Initializing PropertyEmbeddingStore...")
        # This line downloads or loads the model, which can be a point of failure
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = None
        self.properties = []
        print("    -> [DEBUG] PropertyEmbeddingStore initialized successfully.")
    
    def build_index(self, properties: list[dict]):
        """Create FAISS index from property descriptions"""
        texts = []
        for prop in properties:
            # Combine relevant fields into rich text
            text = f"""
            {prop.get('Address', '')}
            Price: {prop.get('Price', '')}
            {prop.get('Description', '')}
            Travel time: {prop.get('travel_time_minutes', '')} minutes
            Crime: {prop.get('crime_data_summary', {}).get('crime_trend', '')}
            """
            texts.append(text.strip())
        
        embeddings = self.model.encode(texts, show_progress_bar=True)
        
        # FAISS index for fast similarity search
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product (cosine)
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        self.properties = properties
    
    def search(self, query: str, top_k: int = 10):
        """Semantic search for properties"""
        query_embedding = self.model.encode([query])
        faiss.normalize_L2(query_embedding)
        
        scores, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for idx, score in zip(indices[0], scores[0]):
            prop = self.properties[idx].copy()
            prop['similarity_score'] = float(score)
            results.append(prop)
        
        return results