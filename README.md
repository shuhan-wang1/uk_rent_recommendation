# UK Rent Recommendation System

An AI-powered rental housing recommendation system for international students in the UK. The system combines **RAG (Retrieval-Augmented Generation)**, a **ReAct Agent framework**, and **interactive map visualization** to help users find suitable accommodation with personalized, data-driven recommendations.

## Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Module Details](#module-details)
  - [RAG System](#rag-system)
  - [ReAct Agent](#react-agent)
  - [Tool System](#tool-system)
  - [Map Visualization](#map-visualization)
  - [Fine-Tuning](#fine-tuning)

## Features

- **Semantic Property Search** — FAISS-based similarity matching over property descriptions using SentenceTransformer embeddings
- **Three-Source RAG** — Retrieves and ranks results from property embeddings, conversation history, and area knowledge
- **Autonomous ReAct Agent** — LLM autonomously decides which tools to use, generates parameters, and iterates until the answer is ready
- **Interactive Amenity Maps** — Folium/OpenStreetMap-based maps showing nearby amenities (supermarkets, gyms, restaurants, transport) for each property
- **Smart Data Enrichment** — Only fetches safety, amenity, environment, or cost-of-living data when the user's query indicates interest
- **Multi-Source Safety Data** — Crime statistics from police.uk API with exact numbers
- **Commute Cost Calculator** — Travel time and cost estimation via Google Maps or OpenRouteService
- **Web Search Integration** — DuckDuckGo-based search with authoritative source filtering (gov.uk, Rightmove, Zoopla, BBC)
- **Conversation Memory** — ChromaDB-backed persistent chat history for context-aware follow-up responses
- **Budget-Aware Ranking** — Hybrid scoring (semantic similarity, travel time, budget match, soft preferences) with clear budget violation explanations

## System Architecture

```
User Query (Web UI)
      │
      ▼
┌─────────────────┐
│   Flask Server   │  (app.py)
│   + Unified UI   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   ReAct Agent    │  Autonomous Reasoning + Acting + Observation loop
│                  │  LLM decides tools & parameters; code only executes
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────────┐
│  Tools │ │ RAG System   │
│Registry│ │ (3-source)   │
└───┬────┘ └──────┬───────┘
    │              │
    ▼              ▼
┌──────────────────────────────┐
│  External APIs & Data        │
│  - police.uk (crime)         │
│  - Google Maps / OpenRoute   │
│  - OpenStreetMap (amenities) │
│  - DuckDuckGo (web search)  │
│  - FAISS (embeddings)        │
│  - ChromaDB (memory + area)  │
└──────────────────────────────┘
```

## Project Structure

```
uk_rent_recommendation/
│
├── local_data_demo/              # Main application
│   ├── app.py                    # Flask server entry point
│   ├── config.py                 # API key configuration
│   ├── unified-ui.html           # Web interface (Alex UI)
│   ├── requirements.txt          # Python dependencies
│   ├── data/
│   │   └── fake_property_listings.csv   # Sample property data
│   ├── core/                     # Core modules
│   │   ├── react_agent.py        # ReAct agent (LLM reasoning loop)
│   │   ├── tool_system.py        # Tool registry & execution framework
│   │   ├── llm_interface.py      # LLM interface (Ollama / Gemini)
│   │   ├── maps_service.py       # Maps, crime data, transport costs
│   │   ├── enrichment_service.py # Conditional data enrichment
│   │   ├── web_search.py         # DuckDuckGo search integration
│   │   ├── data_loader.py        # CSV data loading & parsing
│   │   ├── amenity_map_generator.py  # Interactive map generation
│   │   ├── user_session.py       # Session & favorites management
│   │   └── tools/                # Tool implementations
│   │       ├── search_properties.py       # Property search (Rightmove/Zoopla/Uhomes)
│   │       ├── calculate_commute_cost.py  # Travel cost calculation
│   │       ├── check_safety.py            # Crime statistics lookup
│   │       ├── search_nearby_pois.py      # Nearby amenities search
│   │       ├── get_property_details.py    # Full property information
│   │       └── web_search.py              # General web search
│   └── rag/                      # RAG system
│       ├── property_embeddings.py   # FAISS + SentenceTransformer
│       ├── rag_coordinator.py       # Multi-source hybrid ranking
│       ├── conversation_memory.py   # ChromaDB conversation history
│       └── area_knowledge.py        # London area knowledge base
│
├── map_visualization/            # Standalone map generator
│   ├── property_amenity_map.py   # Folium map with OSM amenities
│   ├── coordinate_verifier.py    # Geocoding accuracy verification
│   └── get_google_coordinate.py  # Google Geocoding integration
│
├── fine_tuning/                  # Model fine-tuning pipeline
│   ├── generate_data.py          # Training data generation
│   ├── train_model.py            # LoRA fine-tuning
│   ├── evaluate_model.py         # Model evaluation
│   ├── production_extractor.py   # Production inference
│   └── student_model_lora/       # Fine-tuned LoRA adapter weights
│
├── scrapped_data_demo/           # Legacy demo (web scraping version)
│   ├── app.py
│   ├── ollama_interface.py
│   └── scrapper/                 # Rightmove & Zoopla scrapers
│
└── tests/                        # Test files
```

## Tech Stack

| Category | Technologies |
|---|---|
| **Backend** | Flask, Python 3.10+ |
| **LLM** | Ollama (local, e.g. Llama 3.2), Gemini API (optional) |
| **Vector Database** | ChromaDB (persistent storage) |
| **Embeddings** | SentenceTransformer (`all-MiniLM-L6-v2`) |
| **Similarity Search** | FAISS (`IndexFlatIP` — cosine similarity) |
| **Maps & Geospatial** | Google Maps API, OpenRouteService, Folium, Leaflet, OpenStreetMap |
| **Web Search** | DuckDuckGo (DDGS) |
| **Data Processing** | Pandas, NumPy, Scikit-learn |
| **ML / NLP** | PyTorch, Transformers, Sentence-Transformers |
| **Fine-Tuning** | LoRA (PEFT), Hugging Face Transformers |
| **Frontend** | HTML5, CSS3, JavaScript |

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running (for local LLM inference)
- Git

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/<your-username>/uk_rent_recommendation.git
   cd uk_rent_recommendation
   ```

2. **Install dependencies**

   ```bash
   cd local_data_demo
   pip install -r requirements.txt
   ```

3. **Pull an Ollama model**

   ```bash
   ollama pull llama3.2
   ```

4. **Set up environment variables**

   Create a `.env` file in `local_data_demo/`:

   ```env
   GOOGLE_MAPS_API_KEY=your_google_maps_key    # Optional: for accurate travel times
   OPENROUTESERVICE_API_KEY=your_ors_key       # Optional: free alternative for travel times
   GEMINI_API_KEY=your_gemini_key              # Optional: if using Gemini instead of Ollama
   ```

5. **Run the application**

   ```bash
   python app.py
   ```

   Open your browser and navigate to `http://localhost:5000`.

## Configuration

Edit `local_data_demo/config.py` to switch between services:

```python
# Travel time service: 'google' (accurate, paid) or 'openroute' (free, approximate)
USE_TRAVEL_SERVICE = 'google'
```

## Usage

1. Open the web interface at `http://localhost:5000`
2. Describe your housing needs in natural language, e.g.:
   - *"I'm looking for a room near UCL under £1500/month with a gym"*
   - *"Find me a safe area near King's Cross with good transport links"*
   - *"What's the commute cost from Vauxhall to UCL?"*
3. The AI agent will autonomously search properties, check safety data, calculate commute times, and present ranked recommendations
4. Follow up with questions — the system remembers your conversation context

## Module Details

### RAG System

The three-source RAG architecture retrieves and ranks information from:

| Source | Storage | Purpose |
|---|---|---|
| **PropertyEmbeddingStore** | FAISS | Semantic similarity search over property descriptions |
| **ConversationMemory** | ChromaDB | Past conversation context for follow-up queries |
| **AreaKnowledgeBase** | ChromaDB | Curated London neighborhood information (safety, vibe, transport) |

**Hybrid Ranking Formula:**

```
score = 0.4 × semantic_similarity
      + 0.3 × travel_time_score
      + 0.2 × budget_match_score
      + 0.1 × soft_preference_match
```

Properties within budget are ranked first; those with soft violations are included with explanations.

### ReAct Agent

The agent follows a **Reasoning + Acting + Observation** loop:

1. **Think** — LLM analyzes the user query and decides what information is needed
2. **Act** — LLM selects a tool and generates parameters (no hard-coded rules)
3. **Observe** — The tool executes and returns results to the LLM
4. **Repeat or Respond** — LLM decides whether more information is needed or generates the final answer

The LLM persona is "Alex" — a friendly rental assistant specialized for international students.

### Tool System

Tools are registered with OpenAI Function Calling format and support:

- Automatic parameter validation (JSON Schema)
- Retry logic with exponential backoff
- Execution time tracking
- Async/sync function support

**Available Tools:**

| Tool | Description |
|---|---|
| `search_properties` | Search rentals on Rightmove, Zoopla, Uhomes |
| `calculate_commute_cost` | Calculate travel time and cost for a route |
| `check_safety` | Look up crime statistics from police.uk |
| `search_nearby_pois` | Find nearby amenities via OpenStreetMap |
| `get_property_details` | Get full details for a specific property |
| `web_search` | General DuckDuckGo search with source verification |

### Map Visualization

Interactive HTML maps generated with **Folium** and **OpenStreetMap** data:

- Property location marker with popup details
- Color-coded amenity markers (supermarkets, restaurants, gyms, parks, transport stops)
- 1.5 km radius amenity search
- Cuisine-specific restaurant filtering (Chinese, Indian, Italian, etc.)

Generated maps are saved as static HTML files in the `maps/` directory.

### Fine-Tuning

A LoRA fine-tuning pipeline for improving JSON extraction from natural language queries:

- **Data Generation** — Synthetic training data creation
- **Training** — LoRA adapter training on a base LLM
- **Evaluation** — Automated accuracy and format validation
- **Production** — Inference with the fine-tuned adapter for structured output extraction

The fine-tuned model converts free-text user queries into structured search criteria (budget, location, amenities, etc.).

## License

This project is for educational and research purposes.
