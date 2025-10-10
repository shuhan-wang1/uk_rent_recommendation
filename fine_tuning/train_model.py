# train_model.py - FULLY OPTIMIZED FOR RTX 3090
from __future__ import annotations
import os
import json
from typing import Dict, List, Any, Optional

import torch
from datasets import load_dataset
from transformers import TrainingArguments, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

from config import *

# ======== LoRA Config - OPTIMIZED FOR FULL PRECISION ========
LORA_R = globals().get("LORA_R", 64)  # Increased for more capacity
LORA_ALPHA = globals().get("LORA_ALPHA", 128)  # Increased proportionally
LORA_DROPOUT = globals().get("LORA_DROPOUT", 0.05)
TARGET_MODULES = globals().get("TARGET_MODULES", [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
])

# ======== TRL 导入 & 兼容处理 ========
from trl import SFTTrainer

# 尝试不同位置导入官方的 Completion-Only collator；若失败则使用自定义实现
_TRL_COMPLETION_COLLATOR = None
try:
    from trl import DataCollatorForCompletionOnlyLM as _TRL_COMPLETION_COLLATOR
except Exception:
    try:
        from trl.trainer.utils import DataCollatorForCompletionOnlyLM as _TRL_COMPLETION_COLLATOR
    except Exception:
        _TRL_COMPLETION_COLLATOR = None


class SimpleCompletionOnlyCollator:
    """
    自定义的"只在 assistant 回复上算 loss"的 collator。
    原理：通过匹配 tokenizer.apply_chat_template 产生的 assistant 前缀（response_template），
    将其之前（含前缀）的位置全部 mask 为 -100，仅保留前缀之后的 token 参与 loss。
    """
    def __init__(self, tokenizer, response_template: str):
        self.tokenizer = tokenizer
        # 不加 special tokens，确保与样本里实际 token 对齐
        self.response_toks = tokenizer.encode(
            response_template, add_special_tokens=False
        )
        print(f"Response tokens to match: {self.response_toks}")

    @staticmethod
    def _find_subsequence(sequence: List[int], pattern: List[int]) -> int:
        """返回 pattern 在 sequence 中第一次出现的起始下标；若不存在返回 -1。"""
        if not pattern or not sequence or len(pattern) > len(sequence):
            return -1
        plen = len(pattern)
        for i in range(len(sequence) - plen + 1):
            if sequence[i:i + plen] == pattern:
                return i
        return -1

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        batch = self.tokenizer.pad(
            features,
            padding=True,
            return_tensors="pt",
        )
        input_ids = batch["input_ids"]
        attention_mask = batch["attention_mask"]
        labels = input_ids.clone()

        resp = self.response_toks
        plen = len(resp)
        for i in range(input_ids.size(0)):
            seq = input_ids[i].tolist()
            start = self._find_subsequence(seq, resp)
            if start == -1:
                labels[i, :] = -100
            else:
                end = start + plen
                labels[i, :end] = -100

        batch["labels"] = labels
        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


class StudentModelTrainer:
    """
    Fine-tune student model on jsonl data:
    每条样本是 {"messages": [{"role": "...", "content": "..."}, ...]}
    仅在 assistant 回复上计算 loss（关键）。
    """
    def __init__(
        self,
        base_model: Optional[str] = None,
        max_seq_length: int = 2048,  # ← Back to 2048 for full GPU
        load_in_4bit: bool = False,
        load_in_8bit: bool = False,  # ← No quantization for RTX 3090
        cache_dir: Optional[str] = None,
    ) -> None:
        self.base_model = base_model if base_model is not None else STUDENT_MODEL_BASE
        self.max_seq_length = max_seq_length
        self.load_in_4bit = load_in_4bit
        self.load_in_8bit = load_in_8bit
        self.cache_dir = cache_dir

        print("\n=== Init model & tokenizer ===")
        print(f"Base model: {self.base_model}")
        print(f"Max seq len: {self.max_seq_length}")
        print(f"Quantization: {'4-bit' if load_in_4bit else '8-bit' if load_in_8bit else 'Full Precision (BF16/FP16)'}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.base_model,
            trust_remote_code=True,
            cache_dir=self.cache_dir,
        )
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        try:
            self.tokenizer.padding_side = "right"
        except Exception:
            pass

        # Load model with optimal settings for RTX 3090
        if self.load_in_4bit:
            print("⚠️  Using 4-bit quantization")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=self.cache_dir,
            )
        elif self.load_in_8bit:
            print("⚠️  Using 8-bit quantization")
            bnb_config = BitsAndBytesConfig(
                load_in_8bit=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=self.cache_dir,
            )
        else:
            print("✓ Using full precision training (optimal for RTX 3090)")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=self.cache_dir,
                torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
            )

        # Only prepare for kbit training if using quantization
        if self.load_in_4bit or self.load_in_8bit:
            self.model = prepare_model_for_kbit_training(self.model)
        else:
            # For full precision, enable gradient checkpointing
            self.model.gradient_checkpointing_enable()

        print("\n=== Apply LoRA ===")
        print(f"LORA_R={LORA_R}, LORA_ALPHA={LORA_ALPHA}, LORA_DROPOUT={LORA_DROPOUT}")
        print(f"TARGET_MODULES={TARGET_MODULES}")
        
        peft_config = LoraConfig(
            r=LORA_R,
            lora_alpha=LORA_ALPHA,
            lora_dropout=LORA_DROPOUT,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=TARGET_MODULES,
        )
        
        self.model = get_peft_model(self.model, peft_config)
        self.model.print_trainable_parameters()

        # 构造"assistant 开始处"的模板前缀
        self.response_template = self._get_response_template()
        print(f"Response template: {repr(self.response_template)}")

        if _TRL_COMPLETION_COLLATOR is not None:
            print("\n=== Use TRL DataCollatorForCompletionOnlyLM ===")
            self.collator = _TRL_COMPLETION_COLLATOR(
                response_template=self.response_template,
                tokenizer=self.tokenizer,
            )
        else:
            print("\n=== Use SimpleCompletionOnlyCollator (fallback) ===")
            self.collator = SimpleCompletionOnlyCollator(
                tokenizer=self.tokenizer,
                response_template=self.response_template,
            )

        print("\n=== Device & Memory ===")
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"Device count: {torch.cuda.device_count()}")
            print(f"Current device: {torch.cuda.current_device()}")
            print(f"Device name: {torch.cuda.get_device_name(0)}")
            print(f"Total memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
            try:
                print(f"bf16 supported: {torch.cuda.is_bf16_supported()}")
            except Exception:
                pass

    def _get_response_template(self) -> str:
        """获取正确的 assistant 响应模板"""
        try:
            full_template = self.tokenizer.apply_chat_template(
                [{"role": "user", "content": "test"}, {"role": "assistant", "content": ""}],
                tokenize=False,
                add_generation_prompt=False,
            )
            
            if "<|im_start|>assistant" in full_template:
                return "<|im_start|>assistant\n"
            elif "### Response:" in full_template:
                return "### Response:\n"
            elif "<|assistant|>" in full_template:
                return "<|assistant|>\n"
            elif "[/INST]" in full_template:
                return "[/INST]"
            else:
                lines = full_template.split("\n")
                for i, line in enumerate(lines):
                    if "assistant" in line.lower():
                        return line + "\n" if i < len(lines) - 1 else line
                return "<|im_start|>assistant\n"
        except Exception as e:
            print(f"Warning: Could not extract response template: {e}")
            return "<|im_start|>assistant\n"

    @staticmethod
    def _ensure_paths(train_file: str, val_file: str) -> None:
        if not os.path.exists(train_file):
            raise FileNotFoundError(f"Train file not found: {train_file}")
        if not os.path.exists(val_file):
            raise FileNotFoundError(f"Val file not found: {val_file}")

    def _load_dataset(self, train_file: str, val_file: str):
        print("\n=== Load dataset ===")
        print(f"Train file: {train_file}")
        print(f"Val   file: {val_file}")
        dataset = load_dataset(
            "json",
            data_files={"train": train_file, "validation": val_file},
        )
        print(f"Train examples: {len(dataset['train'])}")
        print(f"Val examples  : {len(dataset['validation'])}")
        return dataset

    def _preprocess_dataset(self, dataset):
        """将 messages 格式转换为 tokenized input_ids with improved JSON formatting"""
        def tokenize_function(examples):
            texts = []
            msgs_batch = examples["messages"]
            for msgs in msgs_batch:
                try:
                    # First, try to improve JSON formatting in assistant response
                    formatted_msgs = []
                    for msg in msgs:
                        if msg["role"] == "assistant":
                            content = msg['content']
                            try:
                                json_obj = json.loads(content)
                                content = json.dumps(json_obj, indent=2, ensure_ascii=False)
                            except:
                                pass
                            formatted_msgs.append({"role": "assistant", "content": content})
                        else:
                            formatted_msgs.append(msg)
                    
                    text = self.tokenizer.apply_chat_template(
                        formatted_msgs,
                        tokenize=False,
                        add_generation_prompt=False,
                    )
                except Exception:
                    text = ""
                    for msg in msgs:
                        content = msg['content']
                        if msg["role"] == "system":
                            text += f"<|im_start|>system\n{content}<|im_end|>\n"
                        elif msg["role"] == "user":
                            text += f"<|im_start|>user\n{content}<|im_end|>\n"
                        elif msg["role"] == "assistant":
                            try:
                                json_obj = json.loads(content)
                                content = json.dumps(json_obj, indent=2, ensure_ascii=False)
                            except:
                                pass
                            text += f"<|im_start|>assistant\n{content}<|im_end|>\n"
                texts.append(text)
            
            tokenized = self.tokenizer(
                texts,
                truncation=True,
                max_length=self.max_seq_length,
                padding=False,
                return_tensors=None,
            )
            return tokenized
        
        return dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset["train"].column_names,
            desc="Tokenizing dataset",
        )

    def evaluate_json_accuracy(self, test_file: str = "test.jsonl", num_samples: int = 50):
        """Test if model can generate valid JSON"""
        print(f"\n{'='*60}")
        print("EVALUATING JSON GENERATION ACCURACY")
        print(f"{'='*60}")
        
        if not os.path.exists(test_file):
            print(f"⚠️  Test file not found: {test_file}")
            return 0.0
        
        with open(test_file, 'r') as f:
            test_cases = [json.loads(line) for line in f]
        
        num_samples = min(num_samples, len(test_cases))
        print(f"Testing on {num_samples} examples...")
        
        self.model.eval()
        valid_json_count = 0
        exact_match_count = 0
        
        for idx, case in enumerate(test_cases[:num_samples]):
            messages = case['messages'][:2]
            expected_json = case['messages'][2]['content']
            
            try:
                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_tensors="pt"
                ).to(self.model.device)
                
                with torch.no_grad():
                    outputs = self.model.generate(
                        text,
                        max_new_tokens=512,
                        temperature=0.1,
                        do_sample=False,
                        pad_token_id=self.tokenizer.pad_token_id,
                    )
                
                response = self.tokenizer.decode(outputs[0][text.shape[1]:], skip_special_tokens=True)
                
                try:
                    parsed_response = json.loads(response)
                    valid_json_count += 1
                    
                    try:
                        expected_parsed = json.loads(expected_json)
                        if parsed_response == expected_parsed:
                            exact_match_count += 1
                    except:
                        pass
                        
                except json.JSONDecodeError as e:
                    if idx < 5:
                        print(f"\n❌ Example {idx+1} - Invalid JSON:")
                        print(f"   Query: {messages[1]['content'][:100]}...")
                        print(f"   Error: {str(e)[:100]}")
                        print(f"   Generated: {response[:200]}...")
                
            except Exception as e:
                print(f"❌ Example {idx+1} - Generation error: {e}")
        
        json_accuracy = valid_json_count / num_samples
        exact_accuracy = exact_match_count / num_samples
        
        print(f"\n{'='*60}")
        print(f"RESULTS:")
        print(f"  Valid JSON Rate:  {json_accuracy:.1%} ({valid_json_count}/{num_samples})")
        print(f"  Exact Match Rate: {exact_accuracy:.1%} ({exact_match_count}/{num_samples})")
        print(f"{'='*60}\n")
        
        return json_accuracy

    def train(
        self,
        train_file: str = "train.jsonl",
        val_file: str = "val.jsonl",
        output_dir: str = STUDENT_MODEL_OUTPUT,
        num_epochs: int = 10,
        batch_size: int = 8,  # ← Increased for RTX 3090
        grad_accum_steps: int = 2,  # ← Reduced (effective batch = 16)
        learning_rate: float = 5e-6,
        eval_steps: int = 100,
        save_steps: int = 100,
        logging_steps: int = 2,  # ← Match accumulation
        warmup_steps: int = 200,
        seed: int = 42,
        weight_decay: float = 0.01,
        max_grad_norm: float = 0.3,
    ):
        self._ensure_paths(train_file, val_file)
        dataset = self._load_dataset(train_file, val_file)
        
        print("\n=== Preprocessing dataset ===")
        tokenized_dataset = self._preprocess_dataset(dataset)

        # Determine if using quantization
        use_quantization = self.load_in_4bit or self.load_in_8bit
        
        args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=grad_accum_steps,
            learning_rate=learning_rate,
            weight_decay=weight_decay,
            max_grad_norm=max_grad_norm,
            logging_steps=logging_steps,
            eval_steps=eval_steps,
            save_steps=save_steps,
            warmup_steps=warmup_steps,
            warmup_ratio=0.1,
            eval_strategy="steps",
            save_strategy="steps",
            save_total_limit=3,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            fp16=not torch.cuda.is_bf16_supported() and not use_quantization,  # Use FP16 if no BF16
            bf16=torch.cuda.is_bf16_supported() and not use_quantization,  # Use BF16 if supported
            report_to="none",
            seed=seed,
            gradient_checkpointing=True,
            optim="paged_adamw_8bit" if use_quantization else "adamw_torch",
            lr_scheduler_type="cosine",
            logging_first_step=True,
            logging_nan_inf_filter=False,
            logging_strategy="steps",
            dataloader_num_workers=4,  # ← Use multiple workers for faster data loading
            dataloader_pin_memory=True,  # ← Pin memory for faster GPU transfer
        )

        print("\n=== Build SFTTrainer ===")
        print(f"Effective batch size: {batch_size * grad_accum_steps}")
        print(f"Total training steps: ~{len(tokenized_dataset['train']) * num_epochs // (batch_size * grad_accum_steps)}")
        print(f"GPU Memory optimization: {'Quantized' if use_quantization else 'Full Precision'}")
        
        trainer = SFTTrainer(
            model=self.model,
            train_dataset=tokenized_dataset["train"],
            eval_dataset=tokenized_dataset["validation"],
            data_collator=self.collator,
            args=args,
        )

        print("\n=== Start training ===")
        print("💡 Optimized for RTX 3090:")
        print("   - Larger batch size (8) for better GPU utilization")
        print("   - Full precision training for best quality")
        print("   - Multiple dataloader workers")
        print("   - Watch loss < 2.0, accuracy > 60%")
        
        trainer.train()

        print("\n=== Save final adapter & tokenizer ===")
        os.makedirs(output_dir, exist_ok=True)
        trainer.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)

        print("\n✓ Training complete!")
        
        print("\n=== Evaluating model on test set ===")
        json_accuracy = self.evaluate_json_accuracy("test.jsonl", num_samples=50)
        
        if json_accuracy < 0.5:
            print("\n⚠️  WARNING: Low JSON accuracy!")
            print("   Suggestions:")
            print("   1. Train for more epochs (try 15-20)")
            print("   2. Check data quality")
        elif json_accuracy > 0.8:
            print("\n🎉 Excellent! Model generates valid JSON reliably")
        
        print("\n推理提示：用 tokenizer.apply_chat_template(..., add_generation_prompt=True) 构造输入。")
        return trainer


if __name__ == "__main__":
    print("="*60)
    print("TRAINING CONFIGURATION - OPTIMIZED FOR RTX 3090")
    print("="*60)
    print("Optimizations for maximum GPU utilization:")
    print("  ✓ Full precision (BF16/FP16) - no quantization")
    print("  ✓ Batch size: 8 (increased from 1)")
    print("  ✓ Gradient accumulation: 2 (effective batch = 16)")
    print("  ✓ Sequence length: 2048 (full context)")
    print("  ✓ LoRA rank: 64 (increased capacity)")
    print("  ✓ Multi-worker data loading")
    print("  ✓ Learning rate: 5e-6")
    print("  ✓ Training for 10 epochs")
    print("="*60)
    
    trainer = StudentModelTrainer(
        load_in_4bit=False,
        load_in_8bit=False,  # ← No quantization for RTX 3090
        max_seq_length=2048,  # ← Full sequences
    )
    
    trainer.train(
        train_file="train.jsonl",
        val_file="val.jsonl",
        output_dir=STUDENT_MODEL_OUTPUT,
        num_epochs=10,
        batch_size=8,  # ← Start with 8, can increase if OOM doesn't occur
        grad_accum_steps=2,
        learning_rate=5e-6,
        warmup_steps=200,
        eval_steps=100,
        save_steps=100,
        logging_steps=2,
    )