# Ollama-backed workflow note

No native Ollama adapter is implemented in the public v1.0.x line.

Current validation uses MCP-compatible CLI workflows that can run Ollama-backed models, including Qwen Code with local Qwen models and cloud-backed Ollama model routes listed in the main README.

The intended future path is:

1. wrap an Ollama or OpenAI-compatible conversation loop
2. emit the same `GenericEventEnvelope`
3. persist via the same core store
4. retrieve via the same MCP surface
