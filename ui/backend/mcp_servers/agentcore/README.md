# AgentCore Deployment

This directory contains the Text Utilities MCP server ready for deployment to Amazon Bedrock AgentCore Runtime.

## Files

- `text_utils_server.py` - Production-ready stateless MCP server
- `deploy_to_agentcore.py` - Deployment script
- `update_config.py` - Auto-config helper
- `requirements.txt` - Python dependencies

## Quick Deploy

```bash
cd /workshop/ui/backend/mcp_servers/agentcore
python3 deploy_to_agentcore.py
python3 update_config.py
```

Follow the on-screen instructions to restart the workshop app.

## Tools

The text utilities server provides 7 stateless tools:
- reverse_text - Reverse any text
- count_words - Count words, characters, lines
- to_uppercase - Convert to uppercase
- to_lowercase - Convert to lowercase
- hash_text - Generate hashes (MD5, SHA1, SHA256, SHA512)
- encode_base64 - Encode to base64
- decode_base64 - Decode from base64
