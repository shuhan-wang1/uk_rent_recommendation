# 4_production_extractor.py

import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import re
from typing import Optional
from config import *

# Optional: Import Outlines for constrained decoding
try:
    import outlines
    from pydantic import BaseModel, Field
    OUTLINES_AVAILABLE = True
except ImportError:
    OUTLINES_AVAILABLE = False
    print("⚠️  Outlines not available. Install with: pip install outlines")


# Define schema for constrained decoding
if OUTLINES_AVAILABLE:
    class RentalCriteria(BaseModel):
        status: str
        destination: Optional[str] = None
        max_budget: Optional[int] = None
        max_travel_time: Optional[int] = None
        soft_preferences: Optional[str] = None
        property_tags: Optional[list[str]] = []
        amenities_of_interest: Optional[list[str]] = []
        area_vibe: Optional[str] = None
        suggested_search_locations: Optional[list[str]] = []
        city_context: Optional[str] = "London"
        question: Optional[str] = None


class ProductionExtractor:
    """
    Production-ready extractor combining:
    - Fine-tuned model (Option 2)
    - Optional constrained decoding (Option 3)
    - Gemini fallback for difficult cases
    """
    
    def __init__(self, 
                 model_path: str = STUDENT_MODEL_OUTPUT,
                 use_constraints: bool = False):
        
        print(f"{'='*60}")
        print(f"PRODUCTION EXTRACTOR")
        print(f"{'='*60}")
        print(f"Model: {model_path}")
        print(f"Constrained decoding: {'enabled' if use_constraints and OUTLINES_AVAILABLE else 'disabled'}")
        
        self.use_constraints = use_constraints and OUTLINES_AVAILABLE
        
        # Load fine-tuned model
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        
        # Setup constrained generator if enabled
        if self.use_constraints:
            print("Setting up constrained generator...")
            self.constrained_model = outlines.models.Transformers(self.model, self.tokenizer)
            self.constrained_generator = outlines.generate.json(
                self.constrained_model,
                RentalCriteria
            )
            print("✓ Constrained generator ready")
        
        # Gemini for fallback
        if GEMINI_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            self.gemini = genai.GenerativeModel('gemini-2.0-flash-exp')
            print("✓ Gemini fallback available")
        else:
            self.gemini = None
            print("⚠️  Gemini fallback not available (no API key)")
        
        print(f"✓ Production extractor ready\n")
    
    def extract(self, user_query: str, use_fallback: bool = True) -> dict:
        """
        Main extraction method with smart fallback.
        
        Flow:
        1. Try fine-tuned model (fast, free)
        2. Check confidence
        3. If low confidence and use_fallback=True, use Gemini
        """
        
        # Try fine-tuned model first
        try:
            if self.use_constraints:
                result = self._extract_constrained(user_query)
            else:
                result = self._extract_standard(user_query)
            
            # Calculate confidence
            confidence = self._calculate_confidence(result)
            
            if confidence >= MIN_CONFIDENCE_SCORE:
                return {
                    'result': result,
                    'method': 'fine-tuned',
                    'confidence': confidence
                }
            
            elif use_fallback and confidence < FALLBACK_TO_GEMINI_THRESHOLD and self.gemini:
                print(f"⚠️  Low confidence ({confidence:.2f}), using Gemini fallback")
                result = self._extract_gemini_fallback(user_query)
                return {
                    'result': result,
                    'method': 'gemini_fallback',
                    'confidence': 1.0
                }
            
            else:
                return {
                    'result': result,
                    'method': 'fine-tuned',
                    'confidence': confidence
                }
                
        except Exception as e:
            print(f"❌ Extraction error: {e}")
            
            if use_fallback and self.gemini:
                print("→ Using Gemini fallback due to error")
                result = self._extract_gemini_fallback(user_query)
                return {
                    'result': result,
                    'method': 'gemini_fallback',
                    'confidence': 1.0
                }
            else:
                return {
                    'result': {'status': 'error', 'message': str(e)},
                    'method': 'error',
                    'confidence': 0.0
                }
    
    def _extract_standard(self, user_query: str) -> dict:
        """Standard extraction without constraints."""
        
        messages = [
            {
                "role": "system",
                "content": "You are a JSON extraction specialist for UK rental searches. Always convert budgets to monthly and travel times to minutes."
            },
            {
                "role": "user",
                "content": f"Extract rental criteria from: {user_query}"
            }
        ]
        
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.1,
            do_sample=False,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        response = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        )
        
        # Extract JSON
        return self._extract_json(response)
    
    def _extract_constrained(self, user_query: str) -> dict:
        """Extraction with constrained decoding (guaranteed valid JSON)."""
        
        prompt = f"""Extract UK rental criteria from: {user_query}

Return structured JSON with all available information."""

        result = self.constrained_generator(prompt)
        return result.model_dump(exclude_none=True)
    
    def _extract_gemini_fallback(self, user_query: str) -> dict:
        """Fallback to Gemini for difficult cases."""
        
        prompt = f"""Extract UK rental search criteria from this query and return ONLY valid JSON:

User query: "{user_query}"

Return JSON with this structure:
{{
  "status": "success" or "clarification_needed",
  "destination": "specific UK address",
  "max_budget": monthly_budget_in_gbp,
  "max_travel_time": time_in_minutes,
  "soft_preferences": "extracted preferences",
  "city_context": "London/Manchester/etc",
  "suggested_search_locations": ["area1", "area2"],
  "question": "clarification question if needed"
}}

CONVERSION RULES:
- Convert weekly budgets to monthly (multiply by 4.33)
- Convert distances to minutes (5 miles ≈ 25 min, 3 km ≈ 18 min)
- Return ONLY the JSON, no explanation."""

        response = self.gemini.generate_content(
            prompt,
            generation_config={
                'temperature': 0.1,
                'max_output_tokens': 1000,
            }
        )
        
        return self._extract_json(response.text)
    
    def _extract_json(self, text: str) -> dict:
        """Extract JSON from text."""
        try:
            return json.loads(text)
        except:
            # Remove markdown
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            # Try again
            try:
                return json.loads(text.strip())
            except:
                # Find JSON in text
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except:
                        pass
        
        return {'status': 'error', 'message': 'Could not parse JSON'}
    
    def _calculate_confidence(self, result: dict) -> float:
        """Calculate confidence score for result."""
        
        if not isinstance(result, dict):
            return 0.0
        
        score = 0.0
        
        # Check required fields
        if result.get('status') in ['success', 'clarification_needed']:
            score += 0.2
        
        # Destination
        dest = result.get('destination', '')
        if dest and len(dest) > 5:
            score += 0.3
        
        # Budget
        budget = result.get('max_budget', 0)
        if 500 <= budget <= 5000:  # Reasonable range
            score += 0.2
        
        # Travel time
        time = result.get('max_travel_time', 0)
        if 5 <= time <= 120:  # Reasonable range
            score += 0.2
        
        # City context
        valid_cities = ['London', 'Manchester', 'Edinburgh', 'Birmingham', 'Bristol', 'Leeds', 'Glasgow']
        if result.get('city_context') in valid_cities:
            score += 0.1
        
        return min(score, 1.0)


# Integration with your existing code
def clarify_and_extract_criteria_production(user_query: str) -> dict:
    """
    Drop-in replacement for your existing function.
    Use this in app.py
    """
    
    # Initialize extractor (do this once at startup in production)
    extractor = ProductionExtractor(
        model_path=STUDENT_MODEL_OUTPUT,
        use_constraints=False  # Set to True if you want guaranteed JSON structure
    )
    
    # Extract
    response = extractor.extract(user_query, use_fallback=True)
    
    # Return just the result (compatible with your existing code)
    return response['result']


# Example usage and testing
if __name__ == "__main__":
    
    extractor = ProductionExtractor(use_constraints=False)
    
    # Test cases
    test_queries = [
        "Find 1 bed flat near Manchester University, £1200 per month, 25 mins max",
        "2BR apt nr KX <£550pw 30m UCL",
        "apartmnet near manchster univercity budjet 1500 30 minuts",
        "Flat in Edinburgh near the university, around £1000 monthly, don't care about commute",
        "Find me a flat in London",  # Should trigger clarification
    ]
    
    print(f"{'='*60}")
    print(f"TESTING PRODUCTION EXTRACTOR")
    print(f"{'='*60}\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\nTest {i}: {query}")
        print("-" * 60)
        
        response = extractor.extract(query)
        
        print(f"Method: {response['method']}")
        print(f"Confidence: {response['confidence']:.2f}")
        print(f"Result: {json.dumps(response['result'], indent=2)}")