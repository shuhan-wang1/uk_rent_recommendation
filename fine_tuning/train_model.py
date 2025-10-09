# 2_train_model.py

from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import torch
from config import *

class StudentModelTrainer:
    """Fine-tune student model on generated data."""
    
    def __init__(self, 
                 base_model: str = STUDENT_MODEL_BASE,
                 max_seq_length: int = 2048):
        
        self.max_seq_length = max_seq_length
        
        print(f"{'='*60}")
        print(f"STUDENT MODEL TRAINING")
        print(f"{'='*60}")
        print(f"Base model: {base_model}")
        print(f"Max sequence length: {max_seq_length}\n")
        
        print("Loading base model...")
        self.model, self.tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=max_seq_length,
            dtype=None,
            load_in_4bit=True,
        )
        
        print("Configuring LoRA...")
        self.model = FastLanguageModel.get_peft_model(
            self.model,
            r=16,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"
            ],
            lora_alpha=16,
            lora_dropout=0.05,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=42,
        )
        
        print("✓ Model ready for training\n")
    
    def load_training_data(self, train_file: str, val_file: str):
        """Load JSONL training data."""
        
        print(f"Loading training data...")
        print(f"  Train: {train_file}")
        print(f"  Validation: {val_file}")
        
        dataset = load_dataset('json', data_files={
            'train': train_file,
            'validation': val_file
        })
        
        print(f"  ✓ Train examples: {len(dataset['train'])}")
        print(f"  ✓ Validation examples: {len(dataset['validation'])}\n")
        
        return dataset
    
    def format_prompt(self, example):
        """Format example into training prompt."""
        messages = example['messages']
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        return {"text": text}
    
    def train(self, 
              train_file: str = "train.jsonl",
              val_file: str = "val.jsonl",
              output_dir: str = STUDENT_MODEL_OUTPUT,
              num_epochs: int = 3,
              batch_size: int = 4):
        
        # Load and format data
        dataset = self.load_training_data(train_file, val_file)
        dataset = dataset.map(
            self.format_prompt,
            remove_columns=dataset['train'].column_names
        )
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=50,
            eval_steps=200,
            save_steps=200,
            warmup_steps=100,
            save_total_limit=3,
            evaluation_strategy="steps",
            load_best_model_at_end=True,
            report_to="none",
        )
        
        # Create trainer
        trainer = SFTTrainer(
            model=self.model,
            tokenizer=self.tokenizer,
            train_dataset=dataset['train'],
            eval_dataset=dataset['validation'],
            dataset_text_field="text",
            max_seq_length=self.max_seq_length,
            args=training_args,
        )
        
        # Train
        print(f"{'='*60}")
        print(f"STARTING TRAINING")
        print(f"{'='*60}\n")
        
        trainer.train()
        
        # Save
        print(f"\n{'='*60}")
        print(f"SAVING MODEL")
        print(f"{'='*60}")
        
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        print(f"✓ Model saved to {output_dir}")
        print(f"\n✓ Training complete!")
        print(f"\nNext step: Run 3_evaluate_model.py to test the model")
        
        return trainer


if __name__ == "__main__":
    trainer = StudentModelTrainer()
    trainer.train(
        train_file="train.jsonl",
        val_file="val.jsonl",
        output_dir=STUDENT_MODEL_OUTPUT,
        num_epochs=3,
        batch_size=4
    )