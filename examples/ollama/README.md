# Ollama adapter note

No Ollama adapter is implemented in v0.1.

The intended future path is:

1. wrap an Ollama or OpenAI-compatible conversation loop
2. emit the same `GenericEventEnvelope`
3. persist via the same core store
4. retrieve via the same MCP surface
