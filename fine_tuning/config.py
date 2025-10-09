# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Model Configuration
TEACHER_MODEL = "gemini-2.5-flash-lite"  # Gemini teacher model
STUDENT_MODEL_BASE = "unsloth/Qwen2.5-1.5B-Instruct"  # Student base model
STUDENT_MODEL_OUTPUT = "./rental-extraction-student"  # Trained model output

CALLS_PER_MINUTE = 50  # 每分钟调用次数 (严格低于你的RPM限制，比如10或免费版的3)
MAX_CALLS_PER_RUN = 200 # 每次运行最大调用次数 (严格低于你的RPD限制，比如50)
DATASET_FILENAME = "dataset_raw.json" # 统一管理数据集文件名

# Training Configuration
TOTAL_EXAMPLES = 3500  # Total training examples to generate
BATCH_SIZE = 10  # Examples per API call
AUGMENTATION_FACTOR = 1.5  # How many variations per base example

# Budget & Distance Variations
BUDGET_FORMATS = [
    ("per month", "pcm", 1),      # £2000 per month
    ("per week", "pw", 4.33),     # £500 per week = £2165/month
    ("monthly", "monthly", 1),
    ("weekly", "weekly", 4.33),
]

DISTANCE_FORMATS = [
    ("minutes", 1),               # 30 minutes
    ("mins", 1),                  # 30 mins
    ("min", 1),                   # 30 min
    ("miles", 20),                # 5 miles ≈ 20 min (estimate)
    ("km", 12.4),                 # 5 km ≈ 20 min (estimate)
    ("kilometers", 12.4),
    ("metres", 0.0124),           # 1000 metres ≈ 12.4 min
]

# UK Cities for variation
UK_CITIES = [
    ("London", 50, ["UCL", "King's Cross", "Imperial College", "LSE", "City", "Canary Wharf"]),
    ("Manchester", 20, ["University of Manchester", "Manchester Piccadilly", "Deansgate", "Northern Quarter"]),
    ("Edinburgh", 10, ["Edinburgh University", "Waverley Station", "Princes Street", "Holyrood"]),
    ("Birmingham", 8, ["University of Birmingham", "New Street Station", "Bullring", "Digbeth"]),
    ("Bristol", 5, ["University of Bristol", "Temple Meads", "Clifton", "Harbourside"]),
    ("Leeds", 4, ["University of Leeds", "Leeds Station", "City Centre"]),
    ("Glasgow", 3, ["University of Glasgow", "Central Station", "Merchant City"]),
]

# Data Generation Settings
STYLE_VARIATIONS = [
    "casual",           # 35%
    "formal",           # 20%
    "abbreviated",      # 15%
    "verbose",          # 10%
    "with_typos",       # 10%
    "mixed",            # 10%
]

# Quality Thresholds
MIN_CONFIDENCE_SCORE = 0.85
FALLBACK_TO_GEMINI_THRESHOLD = 0.80