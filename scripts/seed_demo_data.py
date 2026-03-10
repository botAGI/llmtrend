"""Generate realistic demo data for a compelling first-launch dashboard.

Populates the database with models, repos, papers, signals, and reports so
that every chart, table, and metric in the Streamlit dashboard is populated
with believable data from the very first ``docker compose up``.

Usage::

    python -m scripts.seed_demo_data
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.niches import ensure_default_niches, DEFAULT_NICHES
from app.database import get_async_session, get_engine
from app.models import (
    Base,
    ArxivPaper,
    CollectionRun,
    GitHubRepo,
    HFModel,
    Niche,
    Report,
    TrendSignal,
    niche_hf_models,
    niche_github_repos,
    niche_arxiv_papers,
)
from app.utils.helpers import utc_now, days_ago

# ---------------------------------------------------------------------------
# Reproducible randomness
# ---------------------------------------------------------------------------
RNG = random.Random(42)

NOW = utc_now()


def _rand_dt(max_days_ago: int = 30) -> datetime:
    """Return a random timezone-aware UTC datetime within the last *max_days_ago* days."""
    delta = timedelta(
        days=RNG.randint(0, max_days_ago),
        hours=RNG.randint(0, 23),
        minutes=RNG.randint(0, 59),
    )
    return NOW - delta


# ---------------------------------------------------------------------------
# Realistic HuggingFace models  (500 entries)
# ---------------------------------------------------------------------------

# Curated "hero" models that will appear at the top of charts
_HERO_MODELS: list[dict] = [
    {"model_id": "meta-llama/Llama-3.2-3B", "author": "meta-llama", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "llama", "chat"], "downloads": 48_500_000, "likes": 12400},
    {"model_id": "meta-llama/Llama-3.2-1B", "author": "meta-llama", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "llama"], "downloads": 35_200_000, "likes": 8900},
    {"model_id": "meta-llama/Llama-3.1-8B-Instruct", "author": "meta-llama", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "llama", "instruction", "chat"], "downloads": 42_000_000, "likes": 15600},
    {"model_id": "meta-llama/Llama-3.1-70B-Instruct", "author": "meta-llama", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "llama", "instruction"], "downloads": 18_700_000, "likes": 9200},
    {"model_id": "mistralai/Mistral-7B-Instruct-v0.3", "author": "mistralai", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "mistral", "instruction"], "downloads": 22_100_000, "likes": 7800},
    {"model_id": "mistralai/Mixtral-8x7B-Instruct-v0.1", "author": "mistralai", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "moe", "mixtral"], "downloads": 14_300_000, "likes": 6100},
    {"model_id": "google/gemma-2-9b-it", "author": "google", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "gemma", "instruction"], "downloads": 19_500_000, "likes": 5200},
    {"model_id": "google/gemma-2-2b-it", "author": "google", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "gemma"], "downloads": 12_800_000, "likes": 3400},
    {"model_id": "Qwen/Qwen2.5-7B-Instruct", "author": "Qwen", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "qwen", "instruction"], "downloads": 16_900_000, "likes": 4900},
    {"model_id": "Qwen/Qwen2.5-72B-Instruct", "author": "Qwen", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "qwen", "instruction"], "downloads": 8_400_000, "likes": 6700},
    {"model_id": "Qwen/Qwen2.5-Coder-7B-Instruct", "author": "Qwen", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "code", "code-generation", "qwen"], "downloads": 7_200_000, "likes": 3800},
    {"model_id": "microsoft/phi-3-mini-4k-instruct", "author": "microsoft", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "phi", "instruction"], "downloads": 25_600_000, "likes": 8300},
    {"model_id": "microsoft/phi-3.5-mini-instruct", "author": "microsoft", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "phi"], "downloads": 11_400_000, "likes": 4100},
    {"model_id": "microsoft/Phi-3-medium-128k-instruct", "author": "microsoft", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "phi", "long-context"], "downloads": 6_800_000, "likes": 2900},
    {"model_id": "stabilityai/stable-diffusion-xl-base-1.0", "author": "stabilityai", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "stable-diffusion", "image-generation"], "downloads": 38_200_000, "likes": 14200},
    {"model_id": "stabilityai/sdxl-turbo", "author": "stabilityai", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "stable-diffusion", "turbo"], "downloads": 15_600_000, "likes": 5800},
    {"model_id": "stabilityai/stable-diffusion-3-medium", "author": "stabilityai", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "sd3"], "downloads": 9_300_000, "likes": 7100},
    {"model_id": "black-forest-labs/FLUX.1-dev", "author": "black-forest-labs", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "flux", "image-generation"], "downloads": 21_400_000, "likes": 11200},
    {"model_id": "black-forest-labs/FLUX.1-schnell", "author": "black-forest-labs", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "flux"], "downloads": 12_700_000, "likes": 6400},
    {"model_id": "openai/whisper-large-v3", "author": "openai", "pipeline_tag": "automatic-speech-recognition", "library_name": "transformers", "tags": ["speech", "whisper", "speech-recognition", "audio"], "downloads": 32_100_000, "likes": 9800},
    {"model_id": "openai/whisper-large-v3-turbo", "author": "openai", "pipeline_tag": "automatic-speech-recognition", "library_name": "transformers", "tags": ["speech", "whisper", "speech-recognition"], "downloads": 14_500_000, "likes": 4200},
    {"model_id": "openai/clip-vit-large-patch14", "author": "openai", "pipeline_tag": "zero-shot-image-classification", "library_name": "transformers", "tags": ["multimodal", "vision-language", "clip", "computer-vision"], "downloads": 27_800_000, "likes": 7600},
    {"model_id": "sentence-transformers/all-MiniLM-L6-v2", "author": "sentence-transformers", "pipeline_tag": "sentence-similarity", "library_name": "sentence-transformers", "tags": ["embedding", "retrieval", "rag", "search", "vector"], "downloads": 45_100_000, "likes": 11000},
    {"model_id": "BAAI/bge-large-en-v1.5", "author": "BAAI", "pipeline_tag": "sentence-similarity", "library_name": "sentence-transformers", "tags": ["embedding", "retrieval", "rag", "search"], "downloads": 18_900_000, "likes": 5300},
    {"model_id": "BAAI/bge-m3", "author": "BAAI", "pipeline_tag": "sentence-similarity", "library_name": "sentence-transformers", "tags": ["embedding", "retrieval", "multilingual", "rag"], "downloads": 11_200_000, "likes": 3700},
    {"model_id": "nvidia/NV-Embed-v2", "author": "nvidia", "pipeline_tag": "sentence-similarity", "library_name": "sentence-transformers", "tags": ["embedding", "retrieval", "rag"], "downloads": 5_600_000, "likes": 2800},
    {"model_id": "deepseek-ai/DeepSeek-Coder-V2-Instruct", "author": "deepseek-ai", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "code", "code-generation", "coding"], "downloads": 9_800_000, "likes": 5400},
    {"model_id": "deepseek-ai/DeepSeek-V2.5", "author": "deepseek-ai", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "moe"], "downloads": 7_600_000, "likes": 4100},
    {"model_id": "codellama/CodeLlama-34b-Instruct-hf", "author": "codellama", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "code", "code-generation", "coding", "copilot"], "downloads": 8_200_000, "likes": 3900},
    {"model_id": "bigcode/starcoder2-15b", "author": "bigcode", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["code", "code-generation", "programming"], "downloads": 4_700_000, "likes": 2600},
    {"model_id": "facebook/musicgen-large", "author": "facebook", "pipeline_tag": "text-to-audio", "library_name": "transformers", "tags": ["audio", "music", "text-to-audio"], "downloads": 6_400_000, "likes": 3200},
    {"model_id": "coqui/XTTS-v2", "author": "coqui", "pipeline_tag": "text-to-speech", "library_name": "transformers", "tags": ["tts", "text-to-speech", "speech", "audio"], "downloads": 8_100_000, "likes": 4500},
    {"model_id": "parler-tts/parler-tts-large-v1", "author": "parler-tts", "pipeline_tag": "text-to-speech", "library_name": "transformers", "tags": ["tts", "text-to-speech", "speech"], "downloads": 3_200_000, "likes": 1800},
    {"model_id": "CohereForAI/c4ai-command-r-plus", "author": "CohereForAI", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "rag", "tool-use", "agent"], "downloads": 5_100_000, "likes": 3100},
    {"model_id": "google/paligemma-3b-mix-448", "author": "google", "pipeline_tag": "image-text-to-text", "library_name": "transformers", "tags": ["multimodal", "vision-language", "vlm", "visual-question-answering"], "downloads": 4_300_000, "likes": 2200},
    {"model_id": "llava-hf/llava-v1.6-mistral-7b-hf", "author": "llava-hf", "pipeline_tag": "image-text-to-text", "library_name": "transformers", "tags": ["multimodal", "vision-language", "vlm", "visual-question-answering"], "downloads": 6_700_000, "likes": 3600},
    {"model_id": "microsoft/Florence-2-large", "author": "microsoft", "pipeline_tag": "image-text-to-text", "library_name": "transformers", "tags": ["multimodal", "computer-vision", "object-detection", "segmentation"], "downloads": 7_900_000, "likes": 4800},
    {"model_id": "facebook/sam2-hiera-large", "author": "facebook", "pipeline_tag": "mask-generation", "library_name": "transformers", "tags": ["computer-vision", "segmentation", "image-classification"], "downloads": 9_100_000, "likes": 5100},
    {"model_id": "ultralytics/yolov8", "author": "ultralytics", "pipeline_tag": "object-detection", "library_name": "ultralytics", "tags": ["computer-vision", "object-detection", "yolo"], "downloads": 16_500_000, "likes": 7200},
    {"model_id": "facebook/nllb-200-distilled-600M", "author": "facebook", "pipeline_tag": "translation", "library_name": "transformers", "tags": ["translation", "machine-translation", "nllb", "multilingual"], "downloads": 11_800_000, "likes": 3400},
    {"model_id": "Helsinki-NLP/opus-mt-en-de", "author": "Helsinki-NLP", "pipeline_tag": "translation", "library_name": "transformers", "tags": ["translation", "machine-translation"], "downloads": 7_200_000, "likes": 1900},
    {"model_id": "tiiuae/falcon-7b-instruct", "author": "tiiuae", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "falcon", "instruction"], "downloads": 5_400_000, "likes": 2300},
    {"model_id": "HuggingFaceH4/zephyr-7b-beta", "author": "HuggingFaceH4", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "chat", "instruction"], "downloads": 8_600_000, "likes": 4200},
    {"model_id": "NousResearch/Hermes-3-Llama-3.1-8B", "author": "NousResearch", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "chat", "tool-use", "agent"], "downloads": 3_900_000, "likes": 2800},
    {"model_id": "google/flan-t5-xxl", "author": "google", "pipeline_tag": "text2text-generation", "library_name": "transformers", "tags": ["text-generation", "summarization", "text-classification"], "downloads": 14_200_000, "likes": 4600},
    {"model_id": "facebook/bart-large-mnli", "author": "facebook", "pipeline_tag": "zero-shot-classification", "library_name": "transformers", "tags": ["text-classification", "sentiment", "nli"], "downloads": 22_300_000, "likes": 5100},
    {"model_id": "dslim/bert-base-NER", "author": "dslim", "pipeline_tag": "token-classification", "library_name": "transformers", "tags": ["ner", "token-classification", "bert"], "downloads": 13_700_000, "likes": 3800},
    {"model_id": "google/vit-base-patch16-224", "author": "google", "pipeline_tag": "image-classification", "library_name": "transformers", "tags": ["computer-vision", "image-classification", "vit"], "downloads": 15_100_000, "likes": 3200},
    {"model_id": "CompVis/stable-diffusion-v1-4", "author": "CompVis", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "stable-diffusion"], "downloads": 20_600_000, "likes": 8900},
    {"model_id": "runwayml/stable-diffusion-v1-5", "author": "runwayml", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "stable-diffusion", "image-generation"], "downloads": 31_400_000, "likes": 10500},
    {"model_id": "tencent/HunyuanVideo", "author": "tencent", "pipeline_tag": "text-to-video", "library_name": "diffusers", "tags": ["text-to-video", "video-generation", "video", "diffusion"], "downloads": 2_800_000, "likes": 4100},
    {"model_id": "stabilityai/stable-video-diffusion-img2vid-xt", "author": "stabilityai", "pipeline_tag": "image-to-video", "library_name": "diffusers", "tags": ["video-generation", "video", "diffusion"], "downloads": 4_500_000, "likes": 3600},
    {"model_id": "BioMistral/BioMistral-7B", "author": "BioMistral", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "medical", "healthcare", "biomedical"], "downloads": 1_200_000, "likes": 890},
    {"model_id": "FinGPT/fingpt-sentiment-llama-13b", "author": "FinGPT", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "finance", "financial", "sentiment", "trading"], "downloads": 780_000, "likes": 540},
    {"model_id": "facebook/esm2_t33_650M_UR50D", "author": "facebook", "pipeline_tag": "fill-mask", "library_name": "transformers", "tags": ["protein", "biology", "science", "scientific"], "downloads": 3_400_000, "likes": 1200},
    {"model_id": "microsoft/BioGPT-Large", "author": "microsoft", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["biomedical", "medical", "science", "clinical"], "downloads": 2_100_000, "likes": 980},
    {"model_id": "google/rt-2-x", "author": "google", "pipeline_tag": "robotics", "library_name": "transformers", "tags": ["robotics", "robot", "manipulation", "control"], "downloads": 890_000, "likes": 620},
    {"model_id": "nvidia/VILA-13b", "author": "nvidia", "pipeline_tag": "image-text-to-text", "library_name": "transformers", "tags": ["multimodal", "vision-language", "vlm"], "downloads": 2_600_000, "likes": 1400},
    {"model_id": "internlm/internlm2_5-7b-chat", "author": "internlm", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "chat", "agent", "tool-use"], "downloads": 4_100_000, "likes": 2100},
    {"model_id": "01-ai/Yi-1.5-9B-Chat", "author": "01-ai", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "chat"], "downloads": 3_500_000, "likes": 1700},
]

# Templates to generate additional models beyond the hero list
_MODEL_TEMPLATES: list[dict] = [
    {"prefix": "meta-llama/Llama-3.2", "suffixes": ["-1B-GGUF", "-3B-GGUF", "-11B-Vision", "-90B"], "author": "meta-llama", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "llama"]},
    {"prefix": "mistralai/Mistral", "suffixes": ["-7B-v0.1", "-7B-v0.3", "-Nemo-Instruct-2407"], "author": "mistralai", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "mistral"]},
    {"prefix": "Qwen/Qwen2.5", "suffixes": ["-0.5B", "-1.5B", "-3B", "-14B", "-32B", "-0.5B-Instruct", "-1.5B-Instruct", "-3B-Instruct", "-14B-Instruct"], "author": "Qwen", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "qwen"]},
    {"prefix": "google/gemma-2", "suffixes": ["-2b", "-9b", "-27b", "-27b-it"], "author": "google", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "gemma"]},
    {"prefix": "microsoft/phi", "suffixes": ["-2", "-3-small-8k-instruct", "-3-small-128k-instruct"], "author": "microsoft", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "phi"]},
    {"prefix": "TheBloke/Llama-2", "suffixes": ["-7B-Chat-GGUF", "-13B-Chat-GGUF", "-70B-Chat-GGUF", "-7B-GGUF", "-13B-GGUF"], "author": "TheBloke", "pipeline_tag": "text-generation", "library_name": "llama.cpp", "tags": ["llm", "text-generation", "gguf", "quantized"]},
    {"prefix": "unsloth/Llama-3.1", "suffixes": ["-8B-bnb-4bit", "-8B-Instruct-bnb-4bit", "-70B-bnb-4bit"], "author": "unsloth", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "quantized"]},
    {"prefix": "stabilityai/stable-diffusion", "suffixes": ["-2-1", "-2-1-base", "-xl-refiner-1.0"], "author": "stabilityai", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "stable-diffusion"]},
    {"prefix": "openai/whisper", "suffixes": ["-base", "-small", "-medium", "-large", "-large-v2", "-tiny"], "author": "openai", "pipeline_tag": "automatic-speech-recognition", "library_name": "transformers", "tags": ["speech", "whisper", "speech-recognition"]},
    {"prefix": "sentence-transformers", "suffixes": ["/all-mpnet-base-v2", "/paraphrase-multilingual-MiniLM-L12-v2", "/multi-qa-MiniLM-L6-cos-v1", "/all-distilroberta-v1", "/msmarco-distilbert-base-v4"], "author": "sentence-transformers", "pipeline_tag": "sentence-similarity", "library_name": "sentence-transformers", "tags": ["embedding", "retrieval", "search", "rag"]},
    {"prefix": "facebook/opt", "suffixes": ["-125m", "-350m", "-1.3b", "-2.7b", "-6.7b", "-13b"], "author": "facebook", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation"]},
    {"prefix": "THUDM/chatglm", "suffixes": ["3-6b", "3-6b-32k", "3-6b-128k"], "author": "THUDM", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "chat"]},
    {"prefix": "TencentARC/PhotoMaker", "suffixes": ["-V1", "-V2"], "author": "TencentARC", "pipeline_tag": "text-to-image", "library_name": "diffusers", "tags": ["text-to-image", "diffusion", "image-generation"]},
    {"prefix": "google/t5", "suffixes": ["-small", "-base", "-large", "-3b", "-11b"], "author": "google", "pipeline_tag": "text2text-generation", "library_name": "transformers", "tags": ["summarization", "text-classification"]},
    {"prefix": "bert-base", "suffixes": ["-uncased", "-cased", "-multilingual-uncased", "-chinese"], "author": "google", "pipeline_tag": "fill-mask", "library_name": "transformers", "tags": ["text-classification", "ner", "bert"]},
    {"prefix": "distilbert", "suffixes": ["-base-uncased", "-base-uncased-finetuned-sst-2-english", "-base-multilingual-cased"], "author": "huggingface", "pipeline_tag": "text-classification", "library_name": "transformers", "tags": ["text-classification", "sentiment"]},
    {"prefix": "Salesforce/codegen", "suffixes": ["2-1B", "2-3_7B", "2-7B", "2-16B"], "author": "Salesforce", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["code", "code-generation", "programming"]},
    {"prefix": "WizardLM/WizardCoder", "suffixes": ["-15B-V1.0", "-Python-34B-V1.0", "-33B-V1.1"], "author": "WizardLM", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["code", "code-generation", "coding"]},
    {"prefix": "allenai/OLMo", "suffixes": ["-1B", "-7B", "-7B-Instruct", "-7B-Twin-2T"], "author": "allenai", "pipeline_tag": "text-generation", "library_name": "transformers", "tags": ["llm", "text-generation", "science"]},
    {"prefix": "Alibaba-NLP/gte", "suffixes": ["-base-en-v1.5", "-large-en-v1.5", "-Qwen2-7B-instruct"], "author": "Alibaba-NLP", "pipeline_tag": "sentence-similarity", "library_name": "sentence-transformers", "tags": ["embedding", "retrieval", "rag", "search"]},
]


def _build_all_models() -> list[dict]:
    """Build the full list of 500 model dicts."""
    models: list[dict] = list(_HERO_MODELS)

    # Expand templates
    for tmpl in _MODEL_TEMPLATES:
        for suffix in tmpl["suffixes"]:
            if suffix.startswith("/"):
                model_id = tmpl["prefix"] + suffix
            else:
                model_id = f"{tmpl['prefix']}-{suffix}" if not suffix.startswith("-") else f"{tmpl['prefix']}{suffix}"
            # Skip if already in hero list
            if any(m["model_id"] == model_id for m in models):
                continue
            downloads = RNG.randint(50_000, 15_000_000)
            models.append({
                "model_id": model_id,
                "author": tmpl["author"],
                "pipeline_tag": tmpl["pipeline_tag"],
                "library_name": tmpl["library_name"],
                "tags": list(tmpl["tags"]),
                "downloads": downloads,
                "likes": max(10, downloads // RNG.randint(800, 5000)),
            })

    # Fill remaining slots to reach 500 with procedurally generated models
    _extra_authors = [
        "NousResearch", "teknium", "TheBloke", "lmsys", "Open-Orca",
        "garage-bAInd", "mosaicml", "databricks", "Writer", "togethercomputer",
        "EleutherAI", "cerebras", "TinyLlama", "upstage", "abacusai",
        "DiscoResearch", "berkeley-nest", "Undi95", "Doctor-Shotgun", "CalderaAI",
        "WizardLM", "jondurbin", "ehartford", "migtissera", "chargoddard",
        "cognitivecomputations", "Intel", "amazon", "Nexusflow", "HuggingFaceM4",
        "bigscience", "ai21labs", "databricks", "Anthropic", "cohere",
    ]
    _extra_names = [
        "falcon", "mpt", "pythia", "RedPajama", "StableBeluga", "Platypus",
        "OpenHermes", "Nous-Hermes", "WizardLM", "Orca-2", "Solar",
        "TinyLlama", "SOLAR", "Starling", "neural-chat", "Dolphin",
        "OpenChat", "Deepsek", "InternLM", "Yi-Chat", "Baichuan",
        "ChatGLM", "Aquila", "BlueLM", "Skywork", "Xwin-LM",
        "Amber", "CrystalCoder", "Poro", "Viking", "EuroLLM",
        "LeoLM", "Saiga", "GigaChat", "Saul", "Meditron",
        "BioLlama", "MedPalm", "ChemLlama", "ProtGPT", "SciGLM",
    ]
    _extra_pipelines = [
        "text-generation", "text-generation", "text-generation",
        "text-to-image", "text-classification", "token-classification",
        "sentence-similarity", "automatic-speech-recognition",
        "text-to-speech", "translation", "summarization",
        "object-detection", "image-classification",
    ]
    _extra_libraries = ["transformers", "diffusers", "sentence-transformers", "llama.cpp", "ggml"]
    _extra_tags_pool = [
        ["llm", "text-generation", "chat"],
        ["llm", "text-generation", "instruction"],
        ["code", "code-generation", "programming"],
        ["text-to-image", "diffusion", "image-generation"],
        ["embedding", "retrieval", "search"],
        ["text-classification", "sentiment"],
        ["speech", "audio", "speech-recognition"],
        ["multimodal", "vision-language"],
        ["translation", "machine-translation"],
        ["medical", "healthcare", "biomedical"],
        ["finance", "financial", "trading"],
        ["science", "scientific", "biology"],
        ["robotics", "robot", "control"],
        ["agent", "ai-agent", "tool-use"],
        ["video", "video-generation", "text-to-video"],
        ["tts", "text-to-speech", "speech"],
        ["ner", "token-classification"],
        ["summarization", "text-generation"],
        ["computer-vision", "object-detection"],
        ["computer-vision", "segmentation"],
    ]

    idx = 0
    while len(models) < 500:
        author = RNG.choice(_extra_authors)
        name = RNG.choice(_extra_names)
        size = RNG.choice(["1B", "3B", "7B", "8B", "13B", "34B", "70B", "small", "base", "large", "xl"])
        variant = RNG.choice(["", "-v1", "-v2", "-instruct", "-chat", "-GGUF", "-AWQ", "-GPTQ", ""])
        model_id = f"{author}/{name}-{size}{variant}"

        # Skip duplicates
        if any(m["model_id"] == model_id for m in models):
            idx += 1
            if idx > 2000:
                break
            continue

        pipeline = RNG.choice(_extra_pipelines)
        downloads = RNG.randint(1_000, 8_000_000)
        tags = list(RNG.choice(_extra_tags_pool))

        models.append({
            "model_id": model_id,
            "author": author,
            "pipeline_tag": pipeline,
            "library_name": RNG.choice(_extra_libraries),
            "tags": tags,
            "downloads": downloads,
            "likes": max(5, downloads // RNG.randint(800, 5000)),
        })
        idx += 1

    return models[:500]


# ---------------------------------------------------------------------------
# Realistic GitHub repos  (200 entries)
# ---------------------------------------------------------------------------

_GITHUB_REPOS: list[dict] = [
    # Top-tier repos
    {"full_name": "huggingface/transformers", "description": "State-of-the-art Machine Learning for JAX, PyTorch and TensorFlow", "language": "Python", "stars": 128000, "topics": ["deep-learning", "machine-learning", "llm", "text-generation", "transformers", "pytorch"]},
    {"full_name": "pytorch/pytorch", "description": "Tensors and Dynamic neural networks in Python with strong GPU acceleration", "language": "Python", "stars": 81000, "topics": ["deep-learning", "machine-learning", "pytorch", "tensor"]},
    {"full_name": "tensorflow/tensorflow", "description": "An Open Source Machine Learning Framework for Everyone", "language": "C++", "stars": 84000, "topics": ["deep-learning", "machine-learning", "tensorflow"]},
    {"full_name": "langchain-ai/langchain", "description": "Build context-aware reasoning applications with LangChain", "language": "Python", "stars": 92000, "topics": ["llm", "rag", "retrieval", "agent", "ai-agent", "langchain"]},
    {"full_name": "vllm-project/vllm", "description": "A high-throughput and memory-efficient inference and serving engine for LLMs", "language": "Python", "stars": 26000, "topics": ["llm", "inference", "text-generation", "serving"]},
    {"full_name": "ggerganov/llama.cpp", "description": "LLM inference in C/C++", "language": "C++", "stars": 64000, "topics": ["llm", "inference", "text-generation", "ggml", "quantization"]},
    {"full_name": "AUTOMATIC1111/stable-diffusion-webui", "description": "Stable Diffusion web UI", "language": "Python", "stars": 136000, "topics": ["stable-diffusion", "text-to-image", "diffusion", "image-generation"]},
    {"full_name": "comfyanonymous/ComfyUI", "description": "The most powerful and modular stable diffusion GUI and backend", "language": "Python", "stars": 48000, "topics": ["stable-diffusion", "text-to-image", "diffusion", "image-generation"]},
    {"full_name": "openai/whisper", "description": "Robust Speech Recognition via Large-Scale Weak Supervision", "language": "Python", "stars": 67000, "topics": ["speech", "speech-recognition", "whisper", "audio"]},
    {"full_name": "microsoft/autogen", "description": "A programming framework for agentic AI", "language": "Python", "stars": 31000, "topics": ["agent", "ai-agent", "autonomous", "llm"]},
    {"full_name": "run-llama/llama_index", "description": "LlamaIndex is a data framework for LLM-based applications", "language": "Python", "stars": 35000, "topics": ["llm", "rag", "retrieval", "search", "vector"]},
    {"full_name": "chroma-core/chroma", "description": "The AI-native open-source embedding database", "language": "Python", "stars": 14000, "topics": ["embedding", "vector", "search", "rag", "retrieval"]},
    {"full_name": "qdrant/qdrant", "description": "Qdrant - High-performance, massive-scale Vector Database", "language": "Rust", "stars": 19500, "topics": ["vector", "search", "rag", "retrieval", "embedding"]},
    {"full_name": "ollama/ollama", "description": "Get up and running with Llama 3, Mistral, and other LLMs", "language": "Go", "stars": 89000, "topics": ["llm", "text-generation", "inference", "llama"]},
    {"full_name": "meta-llama/llama", "description": "Inference code for Llama models", "language": "Python", "stars": 55000, "topics": ["llm", "text-generation", "llama", "language-model"]},
    {"full_name": "lm-sys/FastChat", "description": "An open platform for training, serving, and evaluating LLMs", "language": "Python", "stars": 36000, "topics": ["llm", "text-generation", "chat", "instruction"]},
    {"full_name": "TabbyML/tabby", "description": "Self-hosted AI coding assistant", "language": "Rust", "stars": 21000, "topics": ["code", "coding", "copilot", "code-generation"]},
    {"full_name": "continuedev/continue", "description": "The leading open-source AI code assistant", "language": "TypeScript", "stars": 17000, "topics": ["code", "coding", "copilot", "code-generation", "programming"]},
    {"full_name": "OpenDevin/OpenDevin", "description": "An autonomous AI software engineer", "language": "Python", "stars": 28000, "topics": ["agent", "ai-agent", "autonomous", "code", "programming"]},
    {"full_name": "geekan/MetaGPT", "description": "The multi-agent framework", "language": "Python", "stars": 42000, "topics": ["agent", "ai-agent", "autonomous", "multi-agent"]},
    {"full_name": "Stability-AI/generative-models", "description": "Generative Models by Stability AI", "language": "Python", "stars": 23000, "topics": ["text-to-image", "diffusion", "stable-diffusion", "image-generation"]},
    {"full_name": "invoke-ai/InvokeAI", "description": "Invoke is a leading creative engine for Stable Diffusion models", "language": "Python", "stars": 22000, "topics": ["stable-diffusion", "text-to-image", "diffusion", "image-generation"]},
    {"full_name": "microsoft/DeepSpeed", "description": "DeepSpeed is a deep learning optimization library", "language": "Python", "stars": 34000, "topics": ["deep-learning", "machine-learning", "optimization", "llm"]},
    {"full_name": "hpcaitech/ColossalAI", "description": "Making large AI models cheaper, faster, and more accessible", "language": "Python", "stars": 38000, "topics": ["deep-learning", "llm", "distributed", "training"]},
    {"full_name": "ultralytics/ultralytics", "description": "NEW - YOLOv8 in PyTorch", "language": "Python", "stars": 27000, "topics": ["computer-vision", "object-detection", "yolo", "segmentation"]},
    {"full_name": "facebookresearch/detectron2", "description": "Detectron2 is a platform for object detection, segmentation", "language": "Python", "stars": 29000, "topics": ["computer-vision", "object-detection", "segmentation", "image-classification"]},
    {"full_name": "openai/openai-python", "description": "The official Python library for the OpenAI API", "language": "Python", "stars": 22000, "topics": ["llm", "text-generation", "openai"]},
    {"full_name": "dair-ai/Prompt-Engineering-Guide", "description": "Guides and resources for prompt engineering", "language": "TypeScript", "stars": 47000, "topics": ["llm", "text-generation", "prompt-engineering"]},
    {"full_name": "mlflow/mlflow", "description": "Open source platform for the machine learning lifecycle", "language": "Python", "stars": 18000, "topics": ["machine-learning", "mlops"]},
    {"full_name": "Lightning-AI/pytorch-lightning", "description": "Pretrain, finetune and deploy AI models on multiple GPUs", "language": "Python", "stars": 28000, "topics": ["deep-learning", "pytorch", "training"]},
    {"full_name": "jax-ml/jax", "description": "Composable transformations of Python+NumPy programs", "language": "Python", "stars": 29500, "topics": ["deep-learning", "machine-learning", "jax"]},
    {"full_name": "huggingface/diffusers", "description": "Diffusers: State-of-the-art diffusion models for image and audio generation", "language": "Python", "stars": 25000, "topics": ["text-to-image", "diffusion", "image-generation", "stable-diffusion"]},
    {"full_name": "huggingface/peft", "description": "Parameter-Efficient Fine-Tuning methods", "language": "Python", "stars": 16000, "topics": ["llm", "fine-tuning", "lora", "text-generation"]},
    {"full_name": "huggingface/trl", "description": "Train transformer language models with reinforcement learning", "language": "Python", "stars": 9000, "topics": ["llm", "text-generation", "rlhf", "training"]},
    {"full_name": "BerriAI/litellm", "description": "Call 100+ LLM APIs in OpenAI format", "language": "Python", "stars": 12000, "topics": ["llm", "text-generation", "inference"]},
    {"full_name": "sgl-project/sglang", "description": "SGLang is a fast serving framework for large language models", "language": "Python", "stars": 5000, "topics": ["llm", "text-generation", "inference", "serving"]},
    {"full_name": "deepseek-ai/DeepSeek-Coder", "description": "DeepSeek Coder: Let the Code Write Itself", "language": "Python", "stars": 6200, "topics": ["code", "code-generation", "programming", "coding"]},
    {"full_name": "coqui-ai/TTS", "description": "A deep learning toolkit for Text-to-Speech", "language": "Python", "stars": 33000, "topics": ["tts", "text-to-speech", "speech", "audio"]},
    {"full_name": "suno-ai/bark", "description": "Text-Prompted Generative Audio Model", "language": "Python", "stars": 34000, "topics": ["audio", "text-to-speech", "tts", "speech"]},
    {"full_name": "fishaudio/fish-speech", "description": "Brand new TTS solution", "language": "Python", "stars": 8000, "topics": ["tts", "text-to-speech", "speech", "audio"]},
]


def _build_all_repos() -> list[dict]:
    """Build the full list of 200 repo dicts."""
    repos: list[dict] = list(_GITHUB_REPOS)

    _extra_repo_defs = [
        ("google-deepmind/alphafold", "Protein structure prediction", "Python", 12000, ["science", "biology", "protein", "scientific"]),
        ("google-deepmind/graphcast", "ML-based weather forecasting", "Python", 4500, ["science", "scientific", "weather"]),
        ("stanford-crfm/helm", "Holistic Evaluation of Language Models", "Python", 1800, ["llm", "text-generation", "evaluation"]),
        ("EleutherAI/lm-evaluation-harness", "A framework for few-shot evaluation of language models", "Python", 6000, ["llm", "text-generation", "evaluation"]),
        ("milvus-io/milvus", "A cloud-native vector database", "Go", 29000, ["vector", "search", "embedding", "rag"]),
        ("weaviate/weaviate", "Weaviate is an open source vector database", "Go", 11000, ["vector", "search", "embedding", "rag"]),
        ("facebookresearch/llama-recipes", "Scripts for fine-tuning Llama models", "Python", 11000, ["llm", "text-generation", "fine-tuning"]),
        ("unslothai/unsloth", "Finetune Llama 3, Mistral & Gemma LLMs 2-5x faster", "Python", 15000, ["llm", "text-generation", "fine-tuning", "training"]),
        ("guidance-ai/guidance", "A guidance language for controlling LLMs", "Python", 18000, ["llm", "text-generation", "structured-output"]),
        ("outlines-dev/outlines", "Structured Text Generation", "Python", 8000, ["llm", "text-generation", "structured-output"]),
        ("FlowiseAI/Flowise", "Drag & drop UI to build your customized LLM flow", "TypeScript", 29000, ["llm", "rag", "agent", "low-code"]),
        ("lobehub/lobe-chat", "Modern AI chat framework", "TypeScript", 36000, ["llm", "chat", "text-generation"]),
        ("OpenBMB/ChatDev", "Create Customized Software using Natural Language Idea", "Python", 25000, ["agent", "ai-agent", "autonomous", "code"]),
        ("assafelovic/gpt-researcher", "GPT based autonomous agent for online comprehensive research", "Python", 14000, ["agent", "ai-agent", "autonomous", "search"]),
        ("crewAIInc/crewAI", "Framework for orchestrating role-playing AI agents", "Python", 18000, ["agent", "ai-agent", "multi-agent"]),
        ("microsoft/semantic-kernel", "Integrate cutting-edge LLM technology quickly", "C#", 21000, ["llm", "agent", "ai-agent", "tool-use"]),
        ("roboflow/supervision", "Reusable computer vision tools", "Python", 18000, ["computer-vision", "object-detection", "segmentation"]),
        ("open-mmlab/mmdetection", "OpenMMLab Detection Toolbox and Benchmark", "Python", 29000, ["computer-vision", "object-detection"]),
        ("huggingface/candle", "Minimalist ML framework for Rust", "Rust", 15000, ["machine-learning", "rust", "inference"]),
        ("ggerganov/whisper.cpp", "Port of OpenAI's Whisper model in C/C++", "C++", 34000, ["speech", "speech-recognition", "whisper"]),
        ("m-bain/whisperX", "Whisper-Based Automatic Speech Recognition with word-level timestamps", "Python", 11000, ["speech", "speech-recognition", "whisper"]),
        ("myshell-ai/OpenVoice", "Instant voice cloning by MyShell", "Python", 28000, ["tts", "text-to-speech", "speech", "voice-cloning"]),
        ("SevaSk/ecoute", "A live transcription tool", "Python", 5700, ["speech", "speech-recognition", "audio"]),
        ("hiyouga/LLaMA-Factory", "Unified Efficient Fine-Tuning of 100+ LLMs", "Python", 29000, ["llm", "text-generation", "fine-tuning"]),
        ("axolotl-ai-cloud/axolotl", "Go ahead and axolotl questions about fine-tuning", "Python", 7500, ["llm", "text-generation", "fine-tuning"]),
        ("haotian-liu/LLaVA", "Visual Instruction Tuning: LLaVA", "Python", 19000, ["multimodal", "vision-language", "vlm"]),
        ("THUDM/CogVideo", "Text-to-Video Generation", "Python", 7200, ["text-to-video", "video-generation", "video"]),
        ("hpcaitech/Open-Sora", "Open-source implementation of Sora", "Python", 21000, ["text-to-video", "video-generation", "video"]),
        ("openbmb/MiniCPM-V", "MiniCPM-V: A GPT-4V Level MLLM on Your Phone", "Python", 9000, ["multimodal", "vision-language", "vlm"]),
        ("microsoft/Phi-3CookBook", "Resources for Phi-3", "TypeScript", 3200, ["llm", "text-generation", "phi"]),
    ]
    for name, desc, lang, stars, topics in _extra_repo_defs:
        if any(r["full_name"] == name for r in repos):
            continue
        repos.append({
            "full_name": name,
            "description": desc,
            "language": lang,
            "stars": stars,
            "topics": topics,
        })

    # Fill to 200 with procedurally-generated repos
    _owners = [
        "ml-explore", "ai-research-lab", "neural-bits", "modelscope", "deeplearning-ai",
        "fast-ai-dev", "openllm-project", "agi-labs", "ai-toolkit", "mlsys-team",
        "pytorch-labs", "triton-inference", "onnx-community", "tvm-project", "xformers-dev",
        "neuralmagic", "mosaic-ml", "eleutherai-dev", "bigscience-workshop", "bloom-dev",
    ]
    _rnames = [
        "llm-bench", "model-eval", "ai-tools", "ml-pipeline", "data-prep",
        "train-loop", "infer-engine", "prompt-lib", "embedding-server", "rag-toolkit",
        "agent-runtime", "code-assist", "speech-kit", "vision-bench", "cv-pipeline",
        "nlp-utils", "text-gen", "fine-tune-kit", "quant-engine", "deploy-kit",
        "serving-framework", "model-registry", "feature-store", "experiment-tracker",
        "auto-label", "synthetic-data", "distill-engine", "pruning-tools",
        "tokenizer-suite", "checkpoint-manager", "gpu-scheduler", "batch-inference",
    ]
    _langs = ["Python", "Python", "Python", "Rust", "C++", "TypeScript", "Go", "Julia"]
    _topic_sets = [
        ["llm", "text-generation"], ["code", "code-generation"], ["speech", "audio"],
        ["computer-vision", "image-classification"], ["rag", "retrieval", "vector"],
        ["agent", "ai-agent"], ["machine-learning"], ["deep-learning"],
        ["text-to-image", "diffusion"], ["multimodal", "vision-language"],
        ["science", "scientific"], ["medical", "healthcare"],
        ["finance", "trading"], ["robotics", "robot"],
    ]

    idx = 0
    while len(repos) < 200:
        owner = RNG.choice(_owners)
        rname = RNG.choice(_rnames)
        full_name = f"{owner}/{rname}"
        if any(r["full_name"] == full_name for r in repos):
            idx += 1
            if idx > 1000:
                break
            continue
        repos.append({
            "full_name": full_name,
            "description": f"AI/ML toolkit: {rname.replace('-', ' ')}",
            "language": RNG.choice(_langs),
            "stars": RNG.randint(100, 25000),
            "topics": list(RNG.choice(_topic_sets)),
        })
        idx += 1

    return repos[:200]


# ---------------------------------------------------------------------------
# Realistic arXiv papers  (100 entries)
# ---------------------------------------------------------------------------

_ARXIV_PAPERS: list[dict] = [
    {"title": "Scaling Laws for Neural Language Models: Revisited", "category": "cs.CL", "authors": ["A. Chen", "B. Wang", "C. Li"]},
    {"title": "Attention Is All You Need: Extensions to Multi-Modal Reasoning", "category": "cs.CL", "authors": ["D. Kim", "E. Park", "F. Zhang"]},
    {"title": "Efficient Fine-Tuning of Large Language Models via Adaptive LoRA", "category": "cs.LG", "authors": ["G. Brown", "H. Davis"]},
    {"title": "Mixture-of-Experts with Dynamic Routing for Trillion-Parameter Models", "category": "cs.LG", "authors": ["I. Johnson", "J. Wilson", "K. Taylor"]},
    {"title": "Constitutional AI: Harmlessness from AI Feedback at Scale", "category": "cs.AI", "authors": ["L. Anderson", "M. Thomas"]},
    {"title": "Chain-of-Thought Prompting Elicits Reasoning in Multimodal Models", "category": "cs.AI", "authors": ["N. Martinez", "O. Garcia", "P. Lopez"]},
    {"title": "DPO: Direct Preference Optimization for Language Model Alignment", "category": "cs.CL", "authors": ["Q. Robinson", "R. Clark"]},
    {"title": "FlashAttention-3: Fast and Memory-Efficient Exact Attention with IO-Awareness", "category": "cs.LG", "authors": ["S. Lewis", "T. Walker"]},
    {"title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks: A Survey", "category": "cs.CL", "authors": ["U. Hall", "V. Allen", "W. Young"]},
    {"title": "State Space Models vs. Transformers for Long-Range Sequence Modeling", "category": "cs.LG", "authors": ["X. King", "Y. Wright"]},
    {"title": "Vision Transformers at Scale: Training ViT-22B", "category": "cs.CV", "authors": ["Z. Scott", "A. Green", "B. Baker"]},
    {"title": "Segment Anything Model 2: Towards Universal Image Segmentation", "category": "cs.CV", "authors": ["C. Adams", "D. Nelson"]},
    {"title": "Diffusion Models Beat GANs on Conditional Image Synthesis", "category": "cs.CV", "authors": ["E. Carter", "F. Mitchell", "G. Perez"]},
    {"title": "Stable Diffusion 3: Scaling Rectified Flow Transformers for Image Generation", "category": "cs.CV", "authors": ["H. Roberts", "I. Turner"]},
    {"title": "Sora: Creating Video from Text with Diffusion Transformers", "category": "cs.CV", "authors": ["J. Phillips", "K. Campbell"]},
    {"title": "Whisper v4: Approaching Human-Level Speech Recognition Across 99 Languages", "category": "cs.CL", "authors": ["L. Parker", "M. Evans"]},
    {"title": "XTTS: Cross-Lingual Text-to-Speech with Zero-Shot Voice Cloning", "category": "cs.CL", "authors": ["N. Edwards", "O. Collins"]},
    {"title": "Neural Machine Translation with Sparse Mixture-of-Experts", "category": "cs.CL", "authors": ["P. Stewart", "Q. Sanchez"]},
    {"title": "Graph Neural Networks for Drug Discovery: A Comprehensive Survey", "category": "cs.AI", "authors": ["R. Morris", "S. Rogers", "T. Reed"]},
    {"title": "AlphaFold 3: Accurate Structure Prediction for All Biomolecular Interactions", "category": "cs.AI", "authors": ["U. Cook", "V. Morgan"]},
    {"title": "Reinforcement Learning from Human Feedback: Theory and Practice", "category": "cs.LG", "authors": ["W. Bell", "X. Murphy"]},
    {"title": "LoRA Meets Quantization: 4-bit Fine-Tuning of 70B Parameter Models", "category": "cs.LG", "authors": ["Y. Bailey", "Z. Rivera"]},
    {"title": "Agent-Bench: Evaluating LLMs as Autonomous Agents", "category": "cs.AI", "authors": ["A. Cooper", "B. Richardson"]},
    {"title": "Self-Play Fine-Tuning for Language Models Without Human Annotation", "category": "cs.CL", "authors": ["C. Cox", "D. Howard"]},
    {"title": "Mamba 2: Linear-Time Sequence Modeling with Selective State Spaces", "category": "cs.LG", "authors": ["E. Ward", "F. Torres"]},
    {"title": "Contrastive Learning for Visual Representations: Beyond SimCLR", "category": "cs.CV", "authors": ["G. Peterson", "H. Gray"]},
    {"title": "YOLO-World: Real-Time Open-Vocabulary Object Detection", "category": "cs.CV", "authors": ["I. Ramirez", "J. James"]},
    {"title": "Multimodal Instruction Tuning with Visual Encoders at Scale", "category": "cs.CV", "authors": ["K. Watson", "L. Brooks"]},
    {"title": "Matryoshka Representation Learning for Adaptive Embedding Dimensions", "category": "cs.LG", "authors": ["M. Kelly", "N. Sanders"]},
    {"title": "Code Generation with Planning: Outperforming GPT-4 on HumanEval", "category": "cs.AI", "authors": ["O. Price", "P. Bennett"]},
    {"title": "Sparse Autoencoders Find Interpretable Features in Language Models", "category": "cs.LG", "authors": ["Q. Wood", "R. Barnes"]},
    {"title": "Towards Artificial General Intelligence: A Survey of Recent Progress", "category": "cs.AI", "authors": ["S. Ross", "T. Henderson"]},
    {"title": "Speculative Decoding for Faster LLM Inference Without Quality Loss", "category": "cs.CL", "authors": ["U. Coleman", "V. Jenkins"]},
    {"title": "GAN-Based Data Augmentation for Low-Resource NLP Tasks", "category": "cs.CL", "authors": ["W. Perry", "X. Powell"]},
    {"title": "Evolutionary Architecture Search for Vision-Language Models", "category": "cs.NE", "authors": ["Y. Long", "Z. Patterson"]},
    {"title": "Neural Architecture Search with Differentiable Reinforcement Learning", "category": "cs.NE", "authors": ["A. Hughes", "B. Flores"]},
    {"title": "Neuro-Symbolic AI: Bridging Logic and Deep Learning", "category": "cs.AI", "authors": ["C. Washington", "D. Butler"]},
    {"title": "Multi-Agent Debate Improves Factuality of Large Language Models", "category": "cs.AI", "authors": ["E. Simmons", "F. Foster"]},
    {"title": "Watermarking Large Language Models: Detection and Robustness", "category": "cs.CL", "authors": ["G. Gonzales", "H. Bryant"]},
    {"title": "Tokenization-Free Language Models with Byte-Level Processing", "category": "cs.CL", "authors": ["I. Alexander", "J. Russell"]},
    {"title": "Deep Reinforcement Learning for Robotic Manipulation: A Survey", "category": "cs.AI", "authors": ["K. Griffin", "L. Diaz"]},
    {"title": "Federated Learning Meets LLMs: Privacy-Preserving Fine-Tuning", "category": "cs.LG", "authors": ["M. Hayes", "N. Myers"]},
    {"title": "Prompt Compression for Efficient LLM Inference in Production", "category": "cs.CL", "authors": ["O. Ford", "P. Hamilton"]},
    {"title": "Self-Supervised Pre-Training for 3D Point Cloud Understanding", "category": "cs.CV", "authors": ["Q. Graham", "R. Sullivan"]},
    {"title": "Time Series Forecasting with Foundation Models: Challenges and Opportunities", "category": "cs.LG", "authors": ["S. Wallace", "T. Woods"]},
    {"title": "Training Compute-Optimal Large Language Models: An Updated Analysis", "category": "cs.LG", "authors": ["U. West", "V. Jordan"]},
    {"title": "RLHF Without Reward Models: Learning from Pairwise Comparisons", "category": "cs.LG", "authors": ["W. Owens", "X. Dixon"]},
    {"title": "Physics-Informed Neural Operators for Partial Differential Equations", "category": "cs.NE", "authors": ["Y. Love", "Z. Fisher"]},
    {"title": "Text-to-3D Generation with Score Distillation Sampling", "category": "cs.CV", "authors": ["A. Mendez", "B. Hunt"]},
    {"title": "Multilingual LLMs: Bridging the Performance Gap Across Languages", "category": "cs.CL", "authors": ["C. Dunn", "D. Schmidt"]},
]


def _build_all_papers() -> list[dict]:
    """Build the full list of 100 paper dicts."""
    papers = list(_ARXIV_PAPERS)

    _extra_titles = [
        "Zero-Shot Cross-Lingual Transfer with Instruction-Tuned Models",
        "Adaptive Computation in Transformer Networks",
        "Efficient Transformers: A Survey of Recent Advances",
        "Knowledge Distillation for Edge Deployment of LLMs",
        "Emergent Abilities of Large Language Models: A Critical Review",
        "On the Convergence of Adam and Beyond for Non-Convex Optimization",
        "Data Quality is All You Need: Curating Pre-Training Corpora",
        "Safety Alignment of Foundation Models: Methods and Challenges",
        "Position Interpolation for Extending Context Window of LLMs",
        "Group Relative Policy Optimization for Language Models",
        "Visual Grounding with Large Language Models",
        "Point Cloud Transformers for Autonomous Driving",
        "Preference Optimization with Reference-Free Rewards",
        "Continual Learning in Large Language Models",
        "Geometric Deep Learning on Molecular Structures",
        "Grokking: Generalization Beyond Overfitting on Small Datasets",
        "Causal Representation Learning with Variational Autoencoders",
        "In-Context Learning as Implicit Bayesian Inference",
        "Scaling Vision Transformers to 10 Billion Parameters",
        "Diffusion Models for Text Generation: A New Paradigm",
        "Instruction Following Without Instruction Tuning",
        "Human Motion Generation with Denoising Diffusion Models",
        "Reward Hacking in RLHF: Causes and Mitigations",
        "Mixture of Depths: Dynamic Token Routing in Transformers",
        "Quantizing Diffusion Models to 4 Bits Without Quality Loss",
        "Test-Time Training Improves Robustness of Vision Transformers",
        "Branch-Train-Merge: Embarrassingly Parallel Training of Expert LLMs",
        "Gecko: Versatile Text Embeddings Distilled from LLMs",
        "Mechanistic Interpretability of In-Context Learning",
        "Ring Attention for Near-Infinite Context Transformers",
        "Gated Linear Attention as a Recurrent Alternative to Transformers",
        "Jamba: A Hybrid Transformer-Mamba Language Model",
        "Video Understanding with Long-Context Vision Models",
        "Multi-Token Prediction for Faster Language Model Training",
        "Layout-Aware Document Understanding with Vision-Language Models",
        "Parameter-Efficient Transfer Learning with Adapters",
        "On the Role of Depth in Transformer Language Models",
        "Self-Rewarding Language Models for Iterative Alignment",
        "Selective Attention Improves Reasoning in Transformers",
        "Training LLMs Over Heterogeneous Data with Data Mixing Laws",
        "Protein Language Models for Structure-Function Prediction",
        "Real-Time Neural Radiance Fields for Dynamic Scenes",
        "Sample-Efficient Reinforcement Learning with World Models",
        "Scalable Extraction of Training Data from Language Models",
        "Compositional Visual Reasoning with Large Language Models",
        "KV Cache Compression for Efficient Long-Context Inference",
        "Binary and Ternary Quantization of Large Language Models",
        "How Do Transformers Learn Algorithms? A Mechanistic View",
        "Sequence Parallelism for Long-Context Training at Scale",
        "Medical Image Segmentation with Foundation Models",
    ]
    _cats = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE"]
    _names_pool = [
        "A. Smith", "B. Jones", "C. Lee", "D. Patel", "E. Nakamura",
        "F. Mueller", "G. Dubois", "H. Ivanova", "I. Santos", "J. Svensson",
        "K. Okonkwo", "L. Yamamoto", "M. Rossi", "N. Sharma", "O. Petrov",
    ]

    for title in _extra_titles:
        if any(p["title"] == title for p in papers):
            continue
        num_authors = RNG.randint(2, 5)
        papers.append({
            "title": title,
            "category": RNG.choice(_cats),
            "authors": RNG.sample(_names_pool, num_authors),
        })
        if len(papers) >= 100:
            break

    return papers[:100]


# ---------------------------------------------------------------------------
# Trend signals  (20 entries)
# ---------------------------------------------------------------------------

_SIGNAL_DEFS: list[dict] = [
    {"signal_type": "download_spike", "severity": "critical", "source_type": "huggingface", "source_identifier": "meta-llama/Llama-3.2-3B", "value": 48500000, "delta": 12000000, "delta_percent": 32.8, "description": "Llama 3.2-3B downloads surged 32.8% (+12M) in the past week, driven by widespread adoption in production systems."},
    {"signal_type": "download_spike", "severity": "high", "source_type": "huggingface", "source_identifier": "black-forest-labs/FLUX.1-dev", "value": 21400000, "delta": 5200000, "delta_percent": 32.1, "description": "FLUX.1-dev downloads jumped 32.1% as the community embraces the new architecture over SDXL."},
    {"signal_type": "star_spike", "severity": "critical", "source_type": "github", "source_identifier": "ollama/ollama", "value": 89000, "delta": 8500, "delta_percent": 10.6, "description": "Ollama gained 8.5K stars this week (+10.6%), reflecting surging interest in local LLM deployment."},
    {"signal_type": "star_spike", "severity": "high", "source_type": "github", "source_identifier": "langchain-ai/langchain", "value": 92000, "delta": 3200, "delta_percent": 3.6, "description": "LangChain continues strong growth with 3.2K new stars, bolstered by the LangGraph agent framework release."},
    {"signal_type": "new_entry", "severity": "high", "source_type": "huggingface", "source_identifier": "Qwen/Qwen2.5-72B-Instruct", "value": 8400000, "delta": 8400000, "delta_percent": 100.0, "description": "Qwen 2.5-72B-Instruct is a new top-tier model, reaching 8.4M downloads within its first week of release."},
    {"signal_type": "new_entry", "severity": "medium", "source_type": "huggingface", "source_identifier": "deepseek-ai/DeepSeek-V2.5", "value": 7600000, "delta": 7600000, "delta_percent": 100.0, "description": "DeepSeek V2.5 entered tracking with 7.6M downloads, showing strong adoption for the MoE architecture."},
    {"signal_type": "trend_acceleration", "severity": "high", "source_type": "huggingface", "source_identifier": "microsoft/phi-3-mini-4k-instruct", "value": 25600000, "delta": 6400000, "delta_percent": 33.3, "description": "Phi-3-mini growth is accelerating: downloads grew 33% this period vs. 12% in the previous period."},
    {"signal_type": "trend_acceleration", "severity": "medium", "source_type": "github", "source_identifier": "vllm-project/vllm", "value": 26000, "delta": 2100, "delta_percent": 8.8, "description": "vLLM star growth rate increased from 5.2% to 8.8%, reflecting growing adoption for production inference."},
    {"signal_type": "niche_growth", "severity": "critical", "source_type": "niche", "source_identifier": "AI Agents", "value": 42.5, "delta": 15.2, "delta_percent": 55.7, "description": "The AI Agents niche shows explosive 55.7% growth in combined download/star metrics across all tracked resources."},
    {"signal_type": "niche_growth", "severity": "high", "source_type": "niche", "source_identifier": "RAG & Search", "value": 38.1, "delta": 9.8, "delta_percent": 34.6, "description": "RAG & Search niche downloads grew 34.6%, led by new embedding models and vector database adoption."},
    {"signal_type": "download_spike", "severity": "medium", "source_type": "huggingface", "source_identifier": "sentence-transformers/all-MiniLM-L6-v2", "value": 45100000, "delta": 4200000, "delta_percent": 10.3, "description": "all-MiniLM-L6-v2 saw a 10.3% download increase as RAG architectures continue mainstreaming."},
    {"signal_type": "download_spike", "severity": "medium", "source_type": "huggingface", "source_identifier": "stabilityai/stable-diffusion-xl-base-1.0", "value": 38200000, "delta": 3100000, "delta_percent": 8.8, "description": "SDXL base maintains momentum with 8.8% download growth despite competition from FLUX models."},
    {"signal_type": "star_spike", "severity": "medium", "source_type": "github", "source_identifier": "comfyanonymous/ComfyUI", "value": 48000, "delta": 4200, "delta_percent": 9.6, "description": "ComfyUI gained 4.2K stars as the node-based workflow becomes the preferred SD interface."},
    {"signal_type": "new_entry", "severity": "low", "source_type": "github", "source_identifier": "sgl-project/sglang", "value": 5000, "delta": 5000, "delta_percent": 100.0, "description": "SGLang is a newly tracked fast serving framework gaining traction in the inference space."},
    {"signal_type": "trend_acceleration", "severity": "low", "source_type": "huggingface", "source_identifier": "openai/whisper-large-v3-turbo", "value": 14500000, "delta": 2800000, "delta_percent": 23.9, "description": "Whisper large-v3-turbo growth accelerated to 23.9% as speech-to-text use cases expand."},
    {"signal_type": "niche_growth", "severity": "medium", "source_type": "niche", "source_identifier": "Code Generation", "value": 28.3, "delta": 6.7, "delta_percent": 31.0, "description": "Code Generation niche saw 31% combined growth, driven by DeepSeek Coder V2 and Qwen2.5-Coder releases."},
    {"signal_type": "download_spike", "severity": "low", "source_type": "huggingface", "source_identifier": "google/gemma-2-9b-it", "value": 19500000, "delta": 1800000, "delta_percent": 10.2, "description": "Gemma 2-9B instruction-tuned model shows steady 10.2% growth as a strong open-weight option."},
    {"signal_type": "niche_growth", "severity": "low", "source_type": "niche", "source_identifier": "Video Generation", "value": 12.4, "delta": 4.1, "delta_percent": 49.4, "description": "Video Generation niche is surging at 49.4% growth, though from a smaller base than text/image niches."},
    {"signal_type": "star_spike", "severity": "high", "source_type": "github", "source_identifier": "OpenDevin/OpenDevin", "value": 28000, "delta": 5600, "delta_percent": 25.0, "description": "OpenDevin gained 5.6K stars (+25%) as autonomous AI developer agents capture developer imagination."},
    {"signal_type": "trend_acceleration", "severity": "medium", "source_type": "huggingface", "source_identifier": "BAAI/bge-m3", "value": 11200000, "delta": 2400000, "delta_percent": 27.3, "description": "BGE-M3 multilingual embedding model growth accelerated to 27.3% as global RAG deployments expand."},
]


# ---------------------------------------------------------------------------
# Sample reports (3 entries)
# ---------------------------------------------------------------------------

_DAILY_REPORT_MD = """# AI Trend Monitor - Daily Report

**Period:** Last 24 hours | **Generated:** {date}

## Key Highlights

- **Llama 3.2-3B** continues its dominance with 48.5M total downloads (+32.8% week-over-week)
- **FLUX.1-dev** surpassed SDXL in daily download velocity for the first time
- **AI Agents** niche showed the highest growth rate across all tracked niches (+55.7%)
- 3 new critical signals detected; 7 high-severity signals active

## Top Models by Downloads (24h)

| Rank | Model | Downloads | Growth |
|------|-------|-----------|--------|
| 1 | meta-llama/Llama-3.2-3B | 48.5M | +32.8% |
| 2 | sentence-transformers/all-MiniLM-L6-v2 | 45.1M | +10.3% |
| 3 | meta-llama/Llama-3.1-8B-Instruct | 42.0M | +8.4% |
| 4 | stabilityai/stable-diffusion-xl-base-1.0 | 38.2M | +8.8% |
| 5 | meta-llama/Llama-3.2-1B | 35.2M | +15.1% |

## Active Signals

- **CRITICAL:** Llama 3.2-3B download spike (+12M in one week)
- **CRITICAL:** AI Agents niche explosive growth (+55.7%)
- **CRITICAL:** Ollama GitHub stars surge (+8.5K stars)
- **HIGH:** FLUX.1-dev overtaking SDXL in daily downloads
- **HIGH:** Qwen 2.5-72B rapid adoption (8.4M downloads in first week)

## Niche Performance

| Niche | Models | Growth | Top Model |
|-------|--------|--------|-----------|
| Text Generation / LLMs | 142 | +18.3% | Llama-3.2-3B |
| Image Generation | 48 | +12.7% | SDXL-base-1.0 |
| RAG & Search | 35 | +34.6% | all-MiniLM-L6-v2 |
| Code Generation | 28 | +31.0% | DeepSeek-Coder-V2 |
| AI Agents | 15 | +55.7% | Hermes-3-Llama |
"""

_WEEKLY_REPORT_MD = """# AI Trend Monitor - Weekly Report

**Period:** Last 7 days | **Generated:** {date}

## Executive Summary

This week saw significant momentum in the LLM ecosystem, with Meta's Llama 3.2
family continuing to dominate downloads. The most notable trend is the explosive
growth of the **AI Agents** niche (+55.7%), driven by frameworks like AutoGen,
CrewAI, and OpenDevin. Image generation saw a notable shift as **FLUX.1** models
began overtaking Stable Diffusion XL in daily download velocity.

## Key Metrics

- **Total models tracked:** 500
- **Total GitHub repos tracked:** 200
- **New papers indexed:** 34
- **Signals generated:** 20 (3 critical, 5 high, 7 medium, 5 low)
- **Overall ecosystem growth:** +14.2% (downloads-weighted)

## Emerging Trends

1. **Local LLM deployment** is accelerating. Ollama crossed 89K GitHub stars,
   and quantized model variants (GGUF, AWQ, GPTQ) represent 23% of all
   tracked model downloads.

2. **Multimodal models** are converging. Vision-language models like LLaVA,
   PaliGemma, and Florence-2 are seeing faster growth than text-only counterparts.

3. **Embedding model competition** is intensifying. BAAI's BGE-M3 and Nvidia's
   NV-Embed-v2 are challenging the long-standing dominance of all-MiniLM-L6-v2.

4. **Small language models** (< 3B parameters) grew 40% faster than large models,
   suggesting a market shift toward efficient, deployable alternatives.

## Top 10 Fastest Growing Models

| Rank | Model | Growth % | Downloads |
|------|-------|----------|-----------|
| 1 | Qwen/Qwen2.5-72B-Instruct | +100% | 8.4M |
| 2 | deepseek-ai/DeepSeek-V2.5 | +100% | 7.6M |
| 3 | meta-llama/Llama-3.2-3B | +32.8% | 48.5M |
| 4 | black-forest-labs/FLUX.1-dev | +32.1% | 21.4M |
| 5 | microsoft/phi-3-mini-4k-instruct | +33.3% | 25.6M |
| 6 | BAAI/bge-m3 | +27.3% | 11.2M |
| 7 | openai/whisper-large-v3-turbo | +23.9% | 14.5M |
| 8 | meta-llama/Llama-3.2-1B | +15.1% | 35.2M |
| 9 | sentence-transformers/all-MiniLM-L6-v2 | +10.3% | 45.1M |
| 10 | google/gemma-2-9b-it | +10.2% | 19.5M |
"""

_NICHE_REPORT_MD = """# AI Agents - Niche Deep Dive

**Period:** Last 30 days | **Generated:** {date}

## Niche Overview

The AI Agents niche encompasses autonomous and semi-autonomous AI systems
capable of planning, tool use, and multi-step task execution. This niche has
shown the highest growth rate (+55.7%) among all tracked niches this period.

## Key Models

| Model | Downloads | Growth |
|-------|-----------|--------|
| CohereForAI/c4ai-command-r-plus | 5.1M | +22.4% |
| NousResearch/Hermes-3-Llama-3.1-8B | 3.9M | +18.7% |
| internlm/internlm2_5-7b-chat | 4.1M | +15.3% |

## Key Repositories

| Repository | Stars | Growth |
|------------|-------|--------|
| microsoft/autogen | 31K | +12.3% |
| geekan/MetaGPT | 42K | +8.1% |
| OpenDevin/OpenDevin | 28K | +25.0% |
| crewAIInc/crewAI | 18K | +14.7% |
| assafelovic/gpt-researcher | 14K | +11.2% |

## Recent Research Papers

1. "Agent-Bench: Evaluating LLMs as Autonomous Agents" (cs.AI)
2. "Multi-Agent Debate Improves Factuality of Large Language Models" (cs.AI)
3. "Chain-of-Thought Prompting Elicits Reasoning in Multimodal Models" (cs.AI)

## Analysis

The AI Agents space is rapidly evolving from simple chatbot wrappers to
sophisticated multi-agent orchestration systems. Key developments include:

- **Tool use standardization** via function-calling APIs is enabling more
  reliable agent behavior across model providers.
- **Multi-agent architectures** (MetaGPT, CrewAI) are gaining traction for
  complex workflows that single agents cannot handle effectively.
- **Code-generation agents** (OpenDevin, SWE-Agent) represent the most
  commercially advanced use case for autonomous AI.

The niche is expected to continue its rapid growth trajectory as more
enterprises adopt agent-based workflows for automation tasks.
"""


# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------


async def _seed_data(session: AsyncSession) -> None:  # noqa: C901 (complexity)
    """Insert all demo data inside a single session."""

    # ── 1. Ensure niches exist ──────────────────────────────────────────
    await ensure_default_niches(session)
    await session.flush()

    niche_result = await session.execute(select(Niche))
    niches: list[Niche] = list(niche_result.scalars().all())
    niche_by_name: dict[str, Niche] = {n.name: n for n in niches}
    print(f"  Niches ready: {len(niches)}")

    # ── 2. HuggingFace models ──────────────────────────────────────────
    all_model_dicts = _build_all_models()
    hf_objs: list[HFModel] = []
    for md in all_model_dicts:
        growth_factor = 1.0 + RNG.uniform(0.03, 0.35)
        downloads_prev = int(md["downloads"] / growth_factor)
        likes_prev = max(0, md["likes"] - RNG.randint(5, max(6, md["likes"] // 10)))
        dt = _rand_dt(30)
        model_name = md["model_id"].split("/")[-1] if "/" in md["model_id"] else md["model_id"]
        hf = HFModel(
            model_id=md["model_id"],
            name=model_name,
            author=md.get("author"),
            pipeline_tag=md.get("pipeline_tag"),
            library_name=md.get("library_name"),
            tags=md.get("tags", []),
            downloads=md["downloads"],
            downloads_previous=downloads_prev,
            likes=md.get("likes", 0),
            likes_previous=likes_prev,
            trending_score=round(RNG.uniform(0.0, 100.0), 2),
            last_modified=dt,
            first_seen_at=dt - timedelta(days=RNG.randint(1, 90)),
            last_seen_at=NOW,
        )
        session.add(hf)
        hf_objs.append(hf)

    await session.flush()
    print(f"  HF models created: {len(hf_objs)}")

    # ── 3. GitHub repos ────────────────────────────────────────────────
    all_repo_dicts = _build_all_repos()
    gh_objs: list[GitHubRepo] = []
    for idx, rd in enumerate(all_repo_dicts):
        stars = rd["stars"]
        growth_factor = 1.0 + RNG.uniform(0.02, 0.25)
        stars_prev = int(stars / growth_factor)
        dt = _rand_dt(30)
        owner = rd["full_name"].split("/")[0]
        name = rd["full_name"].split("/")[1] if "/" in rd["full_name"] else rd["full_name"]
        repo = GitHubRepo(
            github_id=1000000 + idx,
            full_name=rd["full_name"],
            name=name,
            owner_login=owner,
            description=rd.get("description", ""),
            html_url=f"https://github.com/{rd['full_name']}",
            language=rd.get("language", "Python"),
            topics=rd.get("topics", []),
            stars=stars,
            stars_previous=stars_prev,
            forks=max(10, stars // RNG.randint(4, 15)),
            open_issues=RNG.randint(10, 800),
            license_spdx=RNG.choice(["Apache-2.0", "MIT", "BSD-3-Clause", "GPL-3.0", None]),
            repo_created_at=dt - timedelta(days=RNG.randint(30, 1500)),
            repo_pushed_at=dt,
            first_seen_at=dt - timedelta(days=RNG.randint(1, 60)),
            last_seen_at=NOW,
        )
        session.add(repo)
        gh_objs.append(repo)

    await session.flush()
    print(f"  GitHub repos created: {len(gh_objs)}")

    # ── 4. arXiv papers ────────────────────────────────────────────────
    all_paper_dicts = _build_all_papers()
    paper_objs: list[ArxivPaper] = []
    for idx, pd_item in enumerate(all_paper_dicts):
        pub_date = _rand_dt(30)
        arxiv_id = f"2503.{10000 + idx:05d}"
        category = pd_item["category"]
        paper = ArxivPaper(
            arxiv_id=arxiv_id,
            title=pd_item["title"],
            abstract=f"We present a study on {pd_item['title'].lower()}. "
                     f"Our approach demonstrates significant improvements over prior work "
                     f"across multiple benchmarks and evaluation criteria. Experiments show "
                     f"consistent gains in both efficiency and quality metrics.",
            authors=pd_item.get("authors", ["Unknown Author"]),
            categories=[category] + RNG.sample(
                [c for c in ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE"] if c != category],
                k=RNG.randint(0, 2),
            ),
            primary_category=category,
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            abstract_url=f"https://arxiv.org/abs/{arxiv_id}",
            published_at=pub_date,
            first_seen_at=pub_date,
        )
        session.add(paper)
        paper_objs.append(paper)

    await session.flush()
    print(f"  arXiv papers created: {len(paper_objs)}")

    # ── 5. Niche assignments (many-to-many) ────────────────────────────
    assignment_count = 0

    # Build keyword lookup for niche matching
    for niche in niches:
        kw_set = {kw.lower() for kw in (niche.keywords or [])}

        # Assign HF models
        for hf in hf_objs:
            tags_lower = {t.lower() for t in (hf.tags or [])}
            pipeline_lower = (hf.pipeline_tag or "").lower()
            name_lower = (hf.name or "").lower()
            searchable = tags_lower | {pipeline_lower, name_lower}
            if kw_set & searchable:
                stmt = niche_hf_models.insert().values(
                    niche_id=niche.id, hf_model_id=hf.id, confidence=1.0
                )
                await session.execute(stmt)
                assignment_count += 1

        # Assign GitHub repos
        for repo in gh_objs:
            topics_lower = {t.lower() for t in (repo.topics or [])}
            desc_lower = (repo.description or "").lower()
            name_lower = (repo.name or "").lower()
            searchable = topics_lower | {name_lower}
            # Also check substring match in description
            match = bool(kw_set & searchable)
            if not match:
                for kw in kw_set:
                    if kw in desc_lower or kw in name_lower:
                        match = True
                        break
            if match:
                stmt = niche_github_repos.insert().values(
                    niche_id=niche.id, github_repo_id=repo.id, confidence=1.0
                )
                await session.execute(stmt)
                assignment_count += 1

        # Assign arXiv papers (match by category keywords)
        _niche_cat_map = {
            "Text Generation / LLMs": ["cs.CL", "cs.AI"],
            "Code Generation": ["cs.AI"],
            "Image Generation": ["cs.CV"],
            "Computer Vision": ["cs.CV"],
            "Speech & Audio": ["cs.CL"],
            "Video Generation": ["cs.CV"],
            "NLP / Text Analysis": ["cs.CL"],
            "Translation": ["cs.CL"],
            "RAG & Search": ["cs.CL", "cs.AI"],
            "AI Agents": ["cs.AI"],
            "Multimodal": ["cs.CV", "cs.CL"],
            "Robotics": ["cs.AI"],
            "Healthcare AI": ["cs.AI"],
            "Finance AI": ["cs.AI", "cs.LG"],
            "Scientific Research": ["cs.AI", "cs.LG"],
        }
        cat_matches = _niche_cat_map.get(niche.name, [])
        for paper in paper_objs:
            title_lower = paper.title.lower()
            if paper.primary_category in cat_matches:
                # Also require at least a weak keyword match in title
                if any(kw in title_lower for kw in kw_set):
                    stmt = niche_arxiv_papers.insert().values(
                        niche_id=niche.id, arxiv_paper_id=paper.id, confidence=0.8
                    )
                    await session.execute(stmt)
                    assignment_count += 1

    await session.flush()
    print(f"  Niche assignments created: {assignment_count}")

    # ── 6. Trend signals ───────────────────────────────────────────────
    for idx, sd in enumerate(_SIGNAL_DEFS):
        # Try to link to a niche
        linked_niche_id = None
        if sd["source_type"] == "niche":
            niche_obj = niche_by_name.get(sd["source_identifier"])
            if niche_obj:
                linked_niche_id = niche_obj.id
        else:
            # Try to find a matching niche for the source identifier
            for n in niches:
                kw_set = {kw.lower() for kw in (n.keywords or [])}
                src_lower = sd["source_identifier"].lower()
                if any(kw in src_lower for kw in kw_set):
                    linked_niche_id = n.id
                    break

        # Determine source_id: try to map to actual model/repo id
        source_id = idx + 1

        signal = TrendSignal(
            source_type=sd["source_type"],
            source_id=source_id,
            source_identifier=sd["source_identifier"],
            signal_type=sd["signal_type"],
            severity=sd["severity"],
            value=sd["value"],
            delta=sd.get("delta"),
            delta_percent=sd.get("delta_percent"),
            description=sd["description"],
            metadata_json={"demo": True, "index": idx},
            niche_id=linked_niche_id,
            detected_at=_rand_dt(7),
            is_read=RNG.choice([True, False, False]),
        )
        session.add(signal)

    await session.flush()
    print(f"  Trend signals created: {len(_SIGNAL_DEFS)}")

    # ── 7. Sample reports ──────────────────────────────────────────────
    date_str = NOW.strftime("%Y-%m-%d %H:%M UTC")

    agents_niche = niche_by_name.get("AI Agents")

    reports_data = [
        {
            "title": f"Daily Report - {NOW.strftime('%Y-%m-%d')}",
            "report_type": "daily",
            "content_markdown": _DAILY_REPORT_MD.format(date=date_str),
            "niche_id": None,
            "signals_count": 12,
            "period_start": NOW - timedelta(days=1),
            "period_end": NOW,
            "generation_time_seconds": 4.2,
            "llm_model_used": "llama3.1:8b",
        },
        {
            "title": f"Weekly Report - Week {NOW.strftime('%W')}, {NOW.strftime('%Y')}",
            "report_type": "weekly",
            "content_markdown": _WEEKLY_REPORT_MD.format(date=date_str),
            "niche_id": None,
            "signals_count": 20,
            "period_start": NOW - timedelta(days=7),
            "period_end": NOW,
            "generation_time_seconds": 8.7,
            "llm_model_used": "llama3.1:8b",
        },
        {
            "title": "AI Agents - Niche Deep Dive",
            "report_type": "niche",
            "content_markdown": _NICHE_REPORT_MD.format(date=date_str),
            "niche_id": agents_niche.id if agents_niche else None,
            "signals_count": 5,
            "period_start": NOW - timedelta(days=30),
            "period_end": NOW,
            "generation_time_seconds": 12.3,
            "llm_model_used": "llama3.1:8b",
        },
    ]

    for rd in reports_data:
        report = Report(
            title=rd["title"],
            report_type=rd["report_type"],
            content_markdown=rd["content_markdown"],
            niche_id=rd["niche_id"],
            signals_count=rd["signals_count"],
            period_start=rd["period_start"],
            period_end=rd["period_end"],
            generated_at=NOW - timedelta(hours=RNG.randint(1, 6)),
            generation_time_seconds=rd["generation_time_seconds"],
            llm_model_used=rd["llm_model_used"],
        )
        session.add(report)

    await session.flush()
    print(f"  Reports created: {len(reports_data)}")

    # ── 8. Collection run records ──────────────────────────────────────
    for source in ["huggingface", "github", "arxiv"]:
        run = CollectionRun(
            source_type=source,
            status="success",
            items_fetched=RNG.randint(50, 500),
            items_created=RNG.randint(5, 50),
            items_updated=RNG.randint(20, 200),
            started_at=NOW - timedelta(hours=RNG.randint(1, 6)),
            completed_at=NOW - timedelta(minutes=RNG.randint(1, 30)),
            duration_seconds=round(RNG.uniform(5.0, 120.0), 2),
        )
        session.add(run)

    await session.flush()
    print("  Collection runs created: 3")


async def seed_demo_data() -> None:
    """Main entry point: check for existing data and seed if empty."""
    # Ensure tables exist
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Check if data already exists
    async for session in get_async_session():
        result = await session.execute(
            select(func.count(HFModel.id))
        )
        count = result.scalar_one()
        if count > 10:
            print(f"Database already has {count} models. Skipping seed.")
            return

    print("Seeding demo data...")
    async for session in get_async_session():
        await _seed_data(session)

    print("Demo data seeded successfully!")
    print("  - 500 HuggingFace models")
    print("  - 200 GitHub repositories")
    print("  - 100 arXiv papers")
    print("  - 20 trend signals")
    print("  - 3 sample reports")
    print("  - 3 collection run records")
    print("  - 15 niches with assignments")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
