import google.generativeai as genai
import json
import time
import random
import os
from typing import List, Dict, Tuple
from config import *
import re
from datetime import datetime

class AdvancedDistillationDataGenerator:
    """
    Advanced data generator with:
    - Style variations (casual, formal, typos)
    - Metric conversions (weekly/monthly budgets, miles/km/minutes)
    - City diversity
    - Natural language variations
    - Robust JSON parsing with individual example rescue
    """
    
    def __init__(self):
        self.model = genai.GenerativeModel(TEACHER_MODEL)
        self.generated_count = 0
        
        # Dynamic batch size management
        self.current_batch_size = BATCH_SIZE
        self.initial_batch_size = BATCH_SIZE
        self.max_batch_size = BATCH_SIZE * 2  # Can grow up to 2x initial size
        self.min_batch_size = max(5, BATCH_SIZE // 3)  # Minimum viable batch size
        
        # Performance tracking for adaptive sizing
        self.consecutive_successes = 0
        self.consecutive_token_limit_hits = 0
        self.total_batches = 0
        
        self.statistics = {
            'by_city': {},
            'by_style': {},
            'by_budget_format': {},
            'by_distance_format': {},
            'rescued_examples': 0,
            'failed_batches': 0,
            'token_limit_hits': 0,
            'safety_blocks': 0,
            'batch_size_increases': 0,
            'batch_size_decreases': 0,
        }
    
    def _select_city_weighted(self) -> Tuple[str, List[str]]:
        """Select city based on weighted probability."""
        rand = random.random() * 100
        cumulative = 0
        
        for city, weight, destinations in UK_CITIES:
            cumulative += weight
            if rand <= cumulative:
                return city, destinations
        
        return UK_CITIES[0][0], UK_CITIES[0][2]
    
    def _increase_batch_size(self):
        """Gradually increase batch size after sustained success."""
        old_size = self.current_batch_size
        
        # Increase by 25% or add 2, whichever is larger
        increase = max(2, int(self.current_batch_size * 0.25))
        new_size = min(self.current_batch_size + increase, self.max_batch_size)
        
        if new_size > old_size:
            self.current_batch_size = new_size
            self.statistics['batch_size_increases'] += 1
            print(f"📈 Performance good! Increasing batch size: {old_size} → {new_size}")
            return True
        return False
    
    def _decrease_batch_size(self):
        """Reduce batch size when hitting token limits."""
        old_size = self.current_batch_size
        
        # Decrease by 40% or subtract 3, whichever is larger (aggressive reduction)
        decrease = max(3, int(self.current_batch_size * 0.4))
        new_size = max(self.current_batch_size - decrease, self.min_batch_size)
        
        if new_size < old_size:
            self.current_batch_size = new_size
            self.statistics['batch_size_decreases'] += 1
            print(f"📉 Token limits detected! Decreasing batch size: {old_size} → {new_size}")
            return True
        else:
            print(f"⚠️  Already at minimum batch size ({self.min_batch_size})")
            return False
    
    def _check_and_adjust_batch_size(self, success: bool):
        """
        Adaptively adjust batch size based on performance.
        
        Strategy:
        - After 5 consecutive successes → increase by 25%
        - After 2 consecutive token limits → decrease by 40%
        - Success resets token limit counter
        - Failure resets success counter
        """
        if success:
            self.consecutive_successes += 1
            self.consecutive_token_limit_hits = 0
            
            # Increase after 5 consecutive successes
            if self.consecutive_successes >= 5:
                if self._increase_batch_size():
                    self.consecutive_successes = 0  # Reset counter
        else:
            self.consecutive_successes = 0
    
    def _convert_budget_format(self, base_budget: int) -> Tuple[int, str, str]:
        """Convert budget to different formats."""
        format_type, suffix, multiplier = random.choice(BUDGET_FORMATS)
        
        if "week" in format_type:
            display_budget = int(base_budget / 4.33)
            return display_budget, suffix, format_type
        else:
            return base_budget, suffix, format_type
    
    def _convert_distance_format(self, base_minutes: int) -> Tuple[float, str]:
        """Convert travel time to different metrics."""
        format_type, conversion_factor = random.choice(DISTANCE_FORMATS)
        
        if "minute" in format_type or "min" in format_type:
            return base_minutes, format_type
        else:
            # Convert minutes to distance
            distance = base_minutes / conversion_factor
            return round(distance, 1), format_type
    
    def _apply_style_variation(self, query: str, style: str) -> str:
        """Apply style variations to make data more realistic."""
        
        if style == "casual":
            query = query.replace("apartment", "flat")
            query = query.replace("one bedroom", "1 bed")
            query = query.replace("two bedroom", "2 bed")
            query = query.replace("University", "Uni")
            query = query.replace("maximum", "max")
            query = query.replace("minutes", "mins")
            
        elif style == "abbreviated":
            query = query.replace("bedroom", "br")
            query = query.replace("apartment", "apt")
            query = query.replace("near", "nr")
            query = query.replace("station", "stn")
            query = query.replace("minutes", "m")
            query = re.sub(r'one\s+bedroom', '1BR', query, flags=re.IGNORECASE)
            query = re.sub(r'two\s+bedroom', '2BR', query, flags=re.IGNORECASE)
            
        elif style == "verbose":
            fillers = ["please", "I would like", "if possible", "ideally", "preferably"]
            if random.random() > 0.5:
                query = random.choice(fillers) + ", " + query
                
        elif style == "with_typos":
            typo_map = {
                "apartment": ["apartmnet", "appartment", "apartement"],
                "bedroom": ["bedrom", "bedrrom"],
                "minutes": ["minuts", "miutes"],
                "commute": ["commut", "comute"],
                "budget": ["budjet", "buget"],
                "near": ["neer", "ner"],
                "flat": ["falt"],
                "quiet": ["queit", "quite"],
                "modern": ["morden"],
            }
            
            for correct, typos in typo_map.items():
                if correct in query.lower() and random.random() < 0.3:
                    query = re.sub(
                        correct, 
                        random.choice(typos), 
                        query, 
                        count=1, 
                        flags=re.IGNORECASE
                    )
        
        elif style == "mixed":
            if random.random() > 0.5:
                query = self._apply_style_variation(query, "casual")
            if random.random() > 0.7:
                query = self._apply_style_variation(query, "abbreviated")
        
        return query
    
    def _validate_single_example(self, example: Dict) -> Tuple[bool, str]:
        """Validate a single example. Returns (is_valid, error_message)."""
        try:
            if 'user_query' not in example or 'expected_json' not in example:
                return False, "Missing required fields"
            
            if not isinstance(example['user_query'], str) or not example['user_query'].strip():
                return False, "Invalid user_query"
            
            json_output = example['expected_json']
            if not isinstance(json_output, dict):
                return False, "expected_json must be a dict"
            
            # Validate budget if present
            budget = json_output.get('max_budget')
            if budget:
                if not isinstance(budget, (int, float)):
                    return False, f"Invalid budget type: {type(budget)}"
                if budget < 300 or budget > 10000:
                    return False, f"Unrealistic budget: {budget}"
            
            # Validate travel time if present
            travel_time = json_output.get('max_travel_time')
            if travel_time:
                if not isinstance(travel_time, (int, float)):
                    return False, f"Invalid travel_time type: {type(travel_time)}"
                if travel_time < 5 or travel_time > 180:
                    return False, f"Unrealistic travel_time: {travel_time}"
            
            # Validate status
            status = json_output.get('status')
            if status and status not in ['success', 'clarification_needed']:
                return False, f"Invalid status: {status}"
            
            return True, ""
            
        except Exception as e:
            return False, str(e)
    
    def _extract_json_array(self, text: str) -> List[Dict]:
        """Extract JSON array from Gemini response with robust error handling."""
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        # Try parsing the full array first
        try:
            examples = json.loads(text)
            # Validate each example
            valid_examples = []
            for i, ex in enumerate(examples):
                is_valid, error = self._validate_single_example(ex)
                if is_valid:
                    valid_examples.append(ex)
                else:
                    print(f"⚠️  Example {i} invalid: {error}")
            return valid_examples
        except json.JSONDecodeError as e:
            print(f"⚠️  Full JSON parse failed at position {e.pos}: {e.msg}")
            
            # Try to find and fix common JSON errors
            text = self._fix_common_json_errors(text)
            
            # Try again after fixes
            try:
                examples = json.loads(text)
                valid_examples = []
                for i, ex in enumerate(examples):
                    is_valid, error = self._validate_single_example(ex)
                    if is_valid:
                        valid_examples.append(ex)
                return valid_examples
            except json.JSONDecodeError:
                print("⚠️  JSON fixes didn't work, attempting individual object rescue...")
            
            # Last resort: try to extract individual valid JSON objects
            return self._rescue_individual_objects(text)
    
    def _fix_common_json_errors(self, text: str) -> str:
        """Fix common JSON formatting errors."""
        # Fix trailing commas before ] or }
        text = re.sub(r',(\s*[\]}])', r'\1', text)
        
        # Fix single quotes to double quotes (be careful with apostrophes in content)
        # Only fix quotes around keys
        text = re.sub(r"'(\w+)':", r'"\1":', text)
        
        # Fix unescaped quotes in strings (basic attempt)
        # This is tricky and might not catch all cases
        
        return text
    
    def _rescue_individual_objects(self, text: str) -> List[Dict]:
        """Try to extract individual valid JSON objects from malformed response."""
        rescued = []
        
        # Strategy 1: Try to split by },{ pattern and reconstruct
        # Find all occurrences of complete objects
        depth = 0
        start_pos = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if depth == 0:
                    start_pos = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start_pos != -1:
                    obj_str = text[start_pos:i+1]
                    try:
                        obj = json.loads(obj_str)
                        is_valid, error = self._validate_single_example(obj)
                        if is_valid:
                            rescued.append(obj)
                            print(f"✓ Rescued valid object {len(rescued)}")
                        else:
                            print(f"✗ Object invalid: {error}")
                    except json.JSONDecodeError as e:
                        print(f"✗ Object parse failed: {e}")
                    start_pos = -1
        
        if rescued:
            print(f"✓ Rescued {len(rescued)} objects from malformed JSON")
            self.statistics['rescued_examples'] += len(rescued)
        else:
            print("✗ Could not rescue any valid objects")
        
        return rescued
    
    def generate_batch(self, batch_size: int = 15) -> List[Dict]:
        """Generate a batch of diverse examples with improved error handling."""
        
        # Select styles for this batch
        styles = random.choices(
            STYLE_VARIATIONS,
            weights=[35, 20, 15, 10, 10, 10],
            k=batch_size
        )
        
        # Improved prompt with stricter JSON formatting requirements
        prompt = f"""Generate {batch_size} apartment search queries with structured JSON outputs. 

CRITICAL JSON FORMATTING:
- Return ONLY a valid JSON array
- NO trailing commas before ] or }}
- Use DOUBLE quotes only (never single quotes)
- Ensure all strings are properly escaped
- Each object must have exactly these fields: "user_query", "query_metadata", "expected_json"

Example of ONE valid object:
{{
  "user_query": "2 bed flat near Manchester Uni, max £1200pm, 25 mins commute",
  "query_metadata": {{
    "style": "casual",
    "original_budget_monthly": 1200,
    "original_time_minutes": 25,
    "city": "Manchester"
  }},
  "expected_json": {{
    "status": "success",
    "destination": "University of Manchester, Oxford Road, Manchester M13 9PL",
    "max_budget": 1200,
    "max_travel_time": 25,
    "soft_preferences": "safe area for students",
    "property_tags": ["2-bedroom", "student-friendly"],
    "amenities_of_interest": ["university", "libraries"],
    "area_vibe": "student neighborhood with cafes and study spaces",
    "suggested_search_locations": ["Fallowfield", "Rusholme", "Victoria Park"],
    "city_context": "Manchester"
  }}
}}

REQUIREMENTS:
1. City Distribution: London 50%, Manchester 20%, Edinburgh 10%, Birmingham 8%, Bristol 5%, Leeds 4%, Glasgow 3%

2. Budget Formats (convert to monthly in max_budget):
   - "£2000 per month" → max_budget: 2000
   - "£500 per week" → max_budget: 2165 (500 × 4.33)
   - "£450 weekly" → max_budget: 1949

3. Distance/Time Formats (convert to minutes in max_travel_time):
   - "30 minutes" → max_travel_time: 30
   - "5 miles" → max_travel_time: 25 (estimate for public transit)
   - "3 km" → max_travel_time: 18

4. Styles for this batch: {', '.join(styles[:5])}
   - casual: "flat", "uni", "1 bed"
   - formal: "apartment", "university", "one bedroom"
   - abbreviated: "1BR apt nr KX"
   - with_typos: "apartmnet", "commut"

5. Query Completeness:
   - 70%: Complete (has destination, budget, time)
   - 20%: Incomplete → status="clarification_needed"
   - 10%: Edge cases

Return ONLY a JSON array of {batch_size} objects. No markdown, no explanation."""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.85,  # Slightly lower for better formatting
                    top_p=0.95,
                    max_output_tokens=8000,
                )
            )
            
            # Check if response is valid before accessing text
            if not response.candidates:
                print("❌ No candidates in response")
                self.statistics['failed_batches'] += 1
                return []
            
            candidate = response.candidates[0]
            
            # Check finish_reason
            # 0=UNSPECIFIED, 1=STOP(success), 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION, 5=OTHER
            finish_reason = candidate.finish_reason
            
            if finish_reason == 2:  # MAX_TOKENS
                self.statistics['token_limit_hits'] += 1
                self.consecutive_token_limit_hits += 1
                
                # Automatically reduce batch size after 2 consecutive hits
                if self.consecutive_token_limit_hits >= 2:
                    self._decrease_batch_size()
                    self.consecutive_token_limit_hits = 0  # Reset after adjustment
                else:
                    print(f"⚠️  Response hit token limit! ({self.consecutive_token_limit_hits}/2)")
                    print(f"   Current batch_size: {batch_size}")
                
                self.statistics['failed_batches'] += 1
                self._check_and_adjust_batch_size(success=False)
                return []
            elif finish_reason == 3:  # SAFETY
                self.statistics['safety_blocks'] += 1
                print("⚠️  Response blocked by safety filters")
                self.statistics['failed_batches'] += 1
                return []
            elif finish_reason == 4:  # RECITATION
                print("⚠️  Response blocked due to recitation concerns")
                self.statistics['failed_batches'] += 1
                return []
            elif finish_reason not in [0, 1]:  # Not SUCCESS
                print(f"⚠️  Unexpected finish_reason: {finish_reason}")
                self.statistics['failed_batches'] += 1
                return []
            
            # Now safe to access text
            if not candidate.content or not candidate.content.parts:
                print("❌ No content parts in response")
                self.statistics['failed_batches'] += 1
                return []
                
            response_text = candidate.content.parts[0].text
            
            # Save raw response for debugging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = f"debug_response_{timestamp}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response_text)
            print(f"📝 Raw response saved to {debug_file}")
            
            examples = self._extract_json_array(response_text)
            
            if not examples:
                print("❌ No valid examples extracted from this batch")
                self.statistics['failed_batches'] += 1
                return []
            
            # Update statistics
            for example in examples:
                metadata = example.get('query_metadata', {})
                city = metadata.get('city', 'Unknown')
                style = metadata.get('style', 'Unknown')
                
                self.statistics['by_city'][city] = self.statistics['by_city'].get(city, 0) + 1
                self.statistics['by_style'][style] = self.statistics['by_style'].get(style, 0) + 1
            
            self.generated_count += len(examples)
            self.total_batches += 1
            
            # Check if we should increase batch size
            self._check_and_adjust_batch_size(success=True)
            
            print(f"✓ Successfully generated {len(examples)}/{batch_size} examples")
            
            return examples
            
        except Exception as e:
            print(f"❌ Error generating batch: {e}")
            self.statistics['failed_batches'] += 1
            return []
    
    def generate_edge_cases(self, count: int = 100) -> List[Dict]:
        """Generate challenging edge cases with improved formatting."""
        
        edge_prompt = f"""Generate {count} edge case rental queries. Return ONLY valid JSON array.

FORMAT EXAMPLE (follow exactly):
[
  {{
    "user_query": "find me a flat, any budget",
    "query_metadata": {{"style": "vague", "city": "London"}},
    "expected_json": {{
      "status": "clarification_needed",
      "question": "What is your maximum monthly budget?",
      "destination": null,
      "max_budget": null,
      "max_travel_time": null
    }}
  }}
]

Edge Case Types:
1. Vague: "any budget", "flexible", "don't care"
2. Contradictions: "cheap luxury", "spacious studio"
3. Multiple destinations: "near UCL or Imperial"
4. Missing info: "flat in London" (no budget/time)
5. Ambiguous: "quick commute", "not too far"
6. Negative: "not expensive", "avoid noise"
7. Complex: many preferences at once
8. Typos + abbreviations: "1BR nr KX"

Return ONLY JSON array of {count} objects."""

        try:
            response = self.model.generate_content(
                edge_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.8,
                    max_output_tokens=8000,
                )
            )
            
            # Check if response is valid
            if not response.candidates:
                print("❌ No candidates in response")
                self.statistics['failed_batches'] += 1
                return []
            
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason
            
            if finish_reason == 2:  # MAX_TOKENS
                print(f"⚠️  Edge case response hit token limit! Reducing count to {count // 2}")
                self.statistics['failed_batches'] += 1
                return []
            elif finish_reason == 3:  # SAFETY
                print("⚠️  Response blocked by safety filters")
                self.statistics['failed_batches'] += 1
                return []
            elif finish_reason not in [0, 1]:
                print(f"⚠️  Unexpected finish_reason: {finish_reason}")
                self.statistics['failed_batches'] += 1
                return []
            
            if not candidate.content or not candidate.content.parts:
                print("❌ No content parts in response")
                self.statistics['failed_batches'] += 1
                return []
            
            response_text = candidate.content.parts[0].text
            
            examples = self._extract_json_array(response_text)
            print(f"✓ Generated {len(examples)}/{count} edge cases")
            return examples
            
        except Exception as e:
            print(f"❌ Error generating edge cases: {e}")
            self.statistics['failed_batches'] += 1
            return []

    def validate_and_clean(self, dataset: List[Dict]) -> List[Dict]:
        """Validate data quality and consistency."""
        
        validated = []
        issues = []
        
        for i, example in enumerate(dataset):
            is_valid, error = self._validate_single_example(example)
            if is_valid:
                validated.append(example)
            else:
                issues.append(f"Example {i}: {error}")
        
        print(f"\n{'='*60}")
        print(f"VALIDATION RESULTS")
        print(f"{'='*60}")
        print(f"Total examples: {len(dataset)}")
        print(f"Valid examples: {len(validated)}")
        print(f"Invalid examples: {len(issues)}")
        print(f"\nPerformance Metrics:")
        print(f"  Rescued examples: {self.statistics['rescued_examples']}")
        print(f"  Failed batches: {self.statistics['failed_batches']}")
        print(f"  Token limit hits: {self.statistics.get('token_limit_hits', 0)}")
        print(f"  Safety blocks: {self.statistics.get('safety_blocks', 0)}")
        print(f"\nBatch Size Dynamics:")
        print(f"  Initial batch size: {self.initial_batch_size}")
        print(f"  Current batch size: {self.current_batch_size}")
        print(f"  Size increases: {self.statistics.get('batch_size_increases', 0)}")
        print(f"  Size decreases: {self.statistics.get('batch_size_decreases', 0)}")
        print(f"  Total batches: {self.total_batches}")
        if self.total_batches > 0:
            print(f"  Avg examples/batch: {len(validated) / self.total_batches:.1f}")
        print(f"Rescued examples: {self.statistics['rescued_examples']}")
        print(f"Failed batches: {self.statistics['failed_batches']}")
        
        if issues:
            print(f"\n⚠️  First 10 issues:")
            for issue in issues[:10]:
                print(f"  - {issue}")
        
        # Print statistics
        print(f"\n{'='*60}")
        print(f"GENERATION STATISTICS")
        print(f"{'='*60}")
        print("\nBy City:")
        for city, count in sorted(self.statistics['by_city'].items(), key=lambda x: -x[1]):
            print(f"  {city}: {count}")
        
        print("\nBy Style:")
        for style, count in sorted(self.statistics['by_style'].items(), key=lambda x: -x[1]):
            print(f"  {style}: {count}")
        
        return validated
    
    def save_dataset(self, dataset: List[Dict], filename: str):
        """Save in training format (JSONL)."""
        
        with open(filename, 'w', encoding='utf-8') as f:
            for example in dataset:
                training_example = {
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a JSON extraction specialist for UK rental searches. Extract criteria into structured JSON. Always convert budgets to monthly and travel times to minutes."
                        },
                        {
                            "role": "user",
                            "content": example['user_query']
                        },
                        {
                            "role": "assistant",
                            "content": json.dumps(example['expected_json'], ensure_ascii=False)
                        }
                    ]
                }
                f.write(json.dumps(training_example, ensure_ascii=False) + '\n')
        
        print(f"✓ Saved {len(dataset)} examples to {filename}")


# Main execution
if __name__ == "__main__":
    
    if not GEMINI_API_KEY:
        print("❌ ERROR: GEMINI_API_KEY not found. Please create a .env file and add your key.")
        exit(1)
    
    genai.configure(api_key=GEMINI_API_KEY)
    generator = AdvancedDistillationDataGenerator()
    
    # Progress management
    dataset = []
    if os.path.exists(DATASET_FILENAME):
        with open(DATASET_FILENAME, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
        print(f"📂 Resuming. Found {len(dataset)} examples in {DATASET_FILENAME}")

    examples_to_generate = TOTAL_EXAMPLES - len(dataset)
    if examples_to_generate <= 0:
        print("✅ Dataset already complete!")
        print(f"Current size: {len(dataset)}")
        print(f"To generate more, increase TOTAL_EXAMPLES in config.py")
    else:
        print(f"🎯 Target: {TOTAL_EXAMPLES} examples")
        print(f"📊 Current: {len(dataset)} examples")
        print(f"🔄 Need: {examples_to_generate} more examples")
        print(f"⏱️  Max API calls this run: {MAX_CALLS_PER_RUN}")
        
        calls_this_run = 0
        sleep_duration = 60 / CALLS_PER_MINUTE
        
        while len(dataset) < TOTAL_EXAMPLES and calls_this_run < MAX_CALLS_PER_RUN:
            print(f"\n{'='*60}")
            print(f"Batch {calls_this_run + 1} / {MAX_CALLS_PER_RUN}")
            print(f"Current batch size: {generator.current_batch_size}")
            print(f"{'='*60}")
            
            # Generate main examples or edge cases
            # Use dynamic batch size (may have been auto-adjusted)
            effective_batch_size = generator.current_batch_size
            
            if len(dataset) < TOTAL_EXAMPLES * 0.85:
                print(f"📝 Generating {effective_batch_size} main examples...")
                new_examples = generator.generate_batch(effective_batch_size)
            else:
                print(f"⚠️  Generating {effective_batch_size} edge case examples...")
                new_examples = generator.generate_edge_cases(effective_batch_size)
            
            if new_examples:
                dataset.extend(new_examples)
                print(f"✅ Added {len(new_examples)} examples. Total: {len(dataset)}/{TOTAL_EXAMPLES}")
                
                # Save progress immediately
                with open(DATASET_FILENAME, 'w', encoding='utf-8') as f:
                    json.dump(dataset, f, indent=2, ensure_ascii=False)
                print(f"💾 Progress saved to {DATASET_FILENAME}")
            else:
                print("⚠️  No valid examples in this batch")

            calls_this_run += 1
            
            # Rate limiting
            if len(dataset) < TOTAL_EXAMPLES and calls_this_run < MAX_CALLS_PER_RUN:
                print(f"⏸️  Pausing {sleep_duration:.1f}s for rate limit...")
                time.sleep(sleep_duration)

        print("\n" + "="*60)
        print("SESSION COMPLETE")
        print("="*60)
        if calls_this_run >= MAX_CALLS_PER_RUN:
            print(f"⏰ Reached API call limit ({MAX_CALLS_PER_RUN} calls)")
        if len(dataset) >= TOTAL_EXAMPLES:
            print("🎉 Target achieved!")
        print(f"📊 Dataset: {len(dataset)} / {TOTAL_EXAMPLES} examples")
        print(f"\n🔄 Batch Size Performance:")
        print(f"   Started with: {generator.initial_batch_size}")
        print(f"   Ended with: {generator.current_batch_size}")
        print(f"   Increases: {generator.statistics.get('batch_size_increases', 0)}")
        print(f"   Decreases: {generator.statistics.get('batch_size_decreases', 0)}")
        if generator.current_batch_size > generator.initial_batch_size:
            improvement = ((generator.current_batch_size - generator.initial_batch_size) / generator.initial_batch_size) * 100
            print(f"   📈 Throughput improved by {improvement:.0f}%!")
        elif generator.current_batch_size < generator.initial_batch_size:
            print(f"   📉 Reduced due to token limits (stability mode)")
        print(f"🔄 Run again to continue generation")
        print("="*60)

    # Final dataset processing
    if len(dataset) >= TOTAL_EXAMPLES:
        print("\n" + "="*60)
        print("FINALIZING DATASET")
        print("="*60)
        
        validated_dataset = generator.validate_and_clean(dataset)
        random.shuffle(validated_dataset)
        
        total = len(validated_dataset)
        train_size = int(total * 0.70)
        val_size = int(total * 0.15)
        
        train_data = validated_dataset[:train_size]
        val_data = validated_dataset[train_size:train_size + val_size]
        test_data = validated_dataset[train_size + val_size:]
        
        generator.save_dataset(train_data, "train.jsonl")
        generator.save_dataset(val_data, "val.jsonl")
        generator.save_dataset(test_data, "test.jsonl")
        
        print(f"\n{'='*60}")
        print(f"✅ DATASET COMPLETE")
        print(f"{'='*60}")
        print(f"📚 Training:   {len(train_data):4d} examples (70%)")
        print(f"📊 Validation: {len(val_data):4d} examples (15%)")
        print(f"🧪 Test:       {len(test_data):4d} examples (15%)")
        print(f"💾 Files: train.jsonl, val.jsonl, test.jsonl")
        print("="*60)