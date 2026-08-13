---
name: nvidia-ai-suite
description: Access, query, and integrate NVIDIA's free AI models, NIM microservices (TensorRT-LLM), Riva TTS/ASR speech engine, NV-Embed-v2, Cosmos 34B physical AI, and NeMo Guardrails.
---

# NVIDIA AI Suite & NIM Microservices Skill

Use this skill when you want to access, query, or deploy NVIDIA's catalog of free AI Foundation models, NIMs, speech engines, or safety guardrails.

## Capabilities & Model Catalog

### 1. High-Performance LLMs & Reasoners
- **`nvidia/llama-3.3-70b-instruct`**: Premier 70B parameter instruction-tuned model.
- **`meta/llama-3.1-405b-instruct`**: Frontier 405B model hosted with TensorRT-LLM acceleration.
- **`nvidia/llama-3.1-nemotron-70b-instruct`**: High-alignment Nemotron reward/instruct model.
- **`nvidia/nemotron-4-340b-instruct`**: Heavy enterprise reasoning and synthetic data generation.
- **`deepseek-ai/deepseek-r1`**: Low-latency DeepSeek R1 reasoning chain NIM.

### 2. Multimodal Vision & Physical AI
- **`nvidia/cosmos-nemotron-34b`**: Physical AI and 3D spatial world model.
- **`microsoft/kosmos-2`**: Precise visual grounding and bounding box detection.
- **`nvidia/neva-22b`**: High-fidelity visual QA and vision-language model.

### 3. Embeddings, Reranking & Retrieval (RAG)
- **`nvidia/nv-embedqa-e5-v5`**: Benchmark-leading retrieval embeddings.
- **`nvidia/nv-embed-v2`**: 4096-dimensional multilingual embedding engine.
- **`nvidia/rerank-qa-mistral-4b`**: High-precision RAG context reranker.

### 4. Speech, Voice AI & Animation Perks (Riva)
- **`nvidia/riva-tts-multilingual`**: Ultra-fast neural Text-to-Speech microservice.
- **`nvidia/riva-asr-parakeet`**: Streaming sub-100ms Automatic Speech Recognition.
- **`nvidia/audio2face-v2`**: 3D facial animation generator from raw audio.

### 5. Safety & Guardrails
- **`nvidia/nemo-guardrails`**: Programmable conversational safety & PII protection.

## Usage & Execution Command

```bash
# List all installed NVIDIA models and status
python MBM/LeadEngine/nvidia_model_registry.py --list

# Test query dispatch
python MBM/LeadEngine/nvidia_model_registry.py --test
```
