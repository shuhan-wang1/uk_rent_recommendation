# 3_evaluate_model.py

import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import List, Dict
import re
from config import *

class ModelEvaluator:
    """Comprehensive evaluation of trained model."""
    
    def __init__(self, model_path: str = STUDENT_MODEL_OUTPUT):
        print(f"{'='*60}")
        print(f"MODEL EVALUATION")
        print(f"{'='*60}\n")
        
        print(f"Loading model from {model_path}...")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        
        print("✓ Model loaded\n")
        
        self.test_data = self._load_test_data("test.jsonl")
        print(f"✓ Loaded {len(self.test_data)} test examples\n")
    
    def _load_test_data(self, filename: str) -> List[Dict]:
        data = []
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                data.append(json.loads(line))
        return data
    
    def _extract_json(self, text: str) -> dict:
        """Extract JSON from model output."""
        try:
            return json.loads(text)
        except:
            # Try to find JSON
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
        return None
    
    def predict(self, user_query: str) -> dict:
        """Get model prediction."""
        
        messages = [
            {
                "role": "system",
                "content": "You are a JSON extraction specialist for UK rental searches."
            },
            {
                "role": "user",
                "content": user_query
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
        
        return self._extract_json(response)
    
    def evaluate(self):
        """Run comprehensive evaluation."""
        
        metrics = {
            'json_valid': 0,
            'status_correct': 0,
            'destination_exact': 0,
            'budget_within_5_percent': 0,
            'budget_within_10_percent': 0,
            'travel_time_exact': 0,
            'city_correct': 0,
            'all_critical_correct': 0,
            'total': len(self.test_data)
        }
        
        errors = []
        
        print(f"{'='*60}")
        print(f"RUNNING EVALUATION")
        print(f"{'='*60}\n")
        
        for i, example in enumerate(self.test_data):
            user_query = example['messages'][1]['content']
            expected_json = json.loads(example['messages'][2]['content'])
            
            try:
                predicted_json = self.predict(user_query)
                
                if predicted_json:
                    metrics['json_valid'] += 1
                    
                    # Status
                    if predicted_json.get('status') == expected_json.get('status'):
                        metrics['status_correct'] += 1
                    
                    # Destination
                    if predicted_json.get('destination') == expected_json.get('destination'):
                        metrics['destination_exact'] += 1
                    
                    # Budget (within tolerance)
                    pred_budget = predicted_json.get('max_budget', 0)
                    exp_budget = expected_json.get('max_budget', 0)
                    
                    if exp_budget > 0:
                        error_pct = abs(pred_budget - exp_budget) / exp_budget
                        if error_pct <= 0.05:
                            metrics['budget_within_5_percent'] += 1
                        if error_pct <= 0.10:
                            metrics['budget_within_10_percent'] += 1
                    
                    # Travel time
                    if predicted_json.get('max_travel_time') == expected_json.get('max_travel_time'):
                        metrics['travel_time_exact'] += 1
                    
                    # City
                    if predicted_json.get('city_context') == expected_json.get('city_context'):
                        metrics['city_correct'] += 1
                    
                    # All critical fields correct
                    if (predicted_json.get('destination') == expected_json.get('destination') and
                        abs(pred_budget - exp_budget) / max(exp_budget, 1) <= 0.10 and
                        predicted_json.get('max_travel_time') == expected_json.get('max_travel_time')):
                        metrics['all_critical_correct'] += 1
                
                else:
                    errors.append({
                        'index': i,
                        'query': user_query[:50],
                        'error': 'Invalid JSON output'
                    })
                
            except Exception as e:
                errors.append({
                    'index': i,
                    'query': user_query[:50],
                    'error': str(e)
                })
            
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(self.test_data)}")
        
        # Print results
        print(f"\n{'='*60}")
        print(f"EVALUATION RESULTS")
        print(f"{'='*60}\n")
        
        for key, value in metrics.items():
            if key != 'total':
                percentage = (value / metrics['total']) * 100
                print(f"{key:30s}: {value:4d}/{metrics['total']} ({percentage:6.2f}%)")
        
        # Print errors
        if errors:
            print(f"\n{'='*60}")
            print(f"ERRORS (showing first 10)")
            print(f"{'='*60}")
            for error in errors[:10]:
                print(f"  #{error['index']}: {error['query']}... → {error['error']}")
        
        return metrics


if __name__ == "__main__":
    evaluator = ModelEvaluator()
    metrics = evaluator.evaluate()
    
    # Save metrics
    with open("evaluation_results.json", 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\n✓ Evaluation complete!")
    print(f"✓ Results saved to evaluation_results.json")
    print(f"\nNext step: Use 4_production_extractor.py in your application")