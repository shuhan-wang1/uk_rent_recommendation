# rag_coordinator.py
from property_embeddings import PropertyEmbeddingStore
from conversation_memory import ConversationMemory
from area_knowledge import AreaKnowledgeBase

class RAGCoordinator:
    def __init__(self):
        self.property_store = PropertyEmbeddingStore()
        self.conversation_memory = ConversationMemory()
        self.area_knowledge = AreaKnowledgeBase()  # New component
    
    def enhanced_search(self, user_query: str, criteria: dict):
        """Multi-source retrieval with reranking"""
        
        # 1. Semantic property search
        semantic_results = self.property_store.search(user_query, top_k=20)
        
        # 2. Get relevant past conversations
        past_context = self.conversation_memory.retrieve_relevant_history(
            user_query, n_results=3
        )
        
        # 3. Retrieve area-specific knowledge
        location = criteria.get('destination')
        area_info = self.area_knowledge.get_context(location)
        
        # 4. Hybrid scoring (semantic + rules)
        scored_results = self._hybrid_rank(
            semantic_results, criteria, area_info
        )
        
        return scored_results, past_context, area_info
    
    def _hybrid_rank(self, properties, criteria, area_info):
        """Combine semantic similarity with hard constraints"""
        final_scores = []
        
        for prop in properties:
            score = prop.get('similarity_score', 0) * 0.4  # Semantic weight
            
            # Rule-based boosting from criteria
            if 'max_travel_time' in criteria and prop.get('travel_time_minutes', 999) <= criteria['max_travel_time']:
                score += 0.3
            
            if 'max_budget' in criteria and prop.get('parsed_price', 9999) <= criteria['max_budget']:
                score += 0.2
            
            # Safety concerns boost from soft preferences
            crime_trend = prop.get('crime_data_summary', {}).get('crime_trend')
            if 'soft_preferences' in criteria and 'safe' in criteria['soft_preferences'].lower():
                if crime_trend == 'decreasing':
                    score += 0.1
            
            prop['final_score'] = score
            final_scores.append(prop)
        
        return sorted(final_scores, key=lambda x: x['final_score'], reverse=True)