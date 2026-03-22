"""
Text Utilities MCP Server - Production Ready
Stateless text processing utilities for AgentCore Runtime
"""
from mcp.server.fastmcp import FastMCP
from typing import Dict
from datetime import datetime
import hashlib
import base64

# Create server with stateless HTTP (required for AgentCore)
mcp = FastMCP(host="0.0.0.0", stateless_http=True)

@mcp.tool()
def reverse_text(text: str) -> Dict:
    """
    Reverse the given text.
    
    Args:
        text: Text to reverse
    """
    try:
        reversed_text = text[::-1]
        return {
            "success": True,
            "original": text,
            "reversed": reversed_text,
            "length": len(text)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def count_words(text: str) -> Dict:
    """
    Count words, characters, and lines in text.
    
    Args:
        text: Text to analyze
    """
    try:
        lines = text.split('\n')
        words = text.split()
        
        return {
            "success": True,
            "characters": len(text),
            "characters_no_spaces": len(text.replace(' ', '')),
            "words": len(words),
            "lines": len(lines),
            "average_word_length": round(sum(len(word) for word in words) / len(words), 2) if words else 0
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def to_uppercase(text: str) -> Dict:
    """
    Convert text to uppercase.
    
    Args:
        text: Text to convert
    """
    try:
        return {
            "success": True,
            "original": text,
            "uppercase": text.upper()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def to_lowercase(text: str) -> Dict:
    """
    Convert text to lowercase.
    
    Args:
        text: Text to convert
    """
    try:
        return {
            "success": True,
            "original": text,
            "lowercase": text.lower()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def hash_text(text: str, algorithm: str = "sha256") -> Dict:
    """
    Generate hash of text.
    
    Args:
        text: Text to hash
        algorithm: Hash algorithm (md5, sha1, sha256, sha512)
    """
    try:
        algorithms = {
            "md5": hashlib.md5,
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512
        }
        
        if algorithm.lower() not in algorithms:
            return {
                "success": False,
                "error": f"Unsupported algorithm. Use: {', '.join(algorithms.keys())}"
            }
        
        hash_func = algorithms[algorithm.lower()]
        hash_value = hash_func(text.encode()).hexdigest()
        
        return {
            "success": True,
            "algorithm": algorithm.upper(),
            "hash": hash_value,
            "length": len(hash_value)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def encode_base64(text: str) -> Dict:
    """
    Encode text to base64.
    
    Args:
        text: Text to encode
    """
    try:
        encoded = base64.b64encode(text.encode()).decode()
        return {
            "success": True,
            "original": text,
            "encoded": encoded
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def decode_base64(encoded_text: str) -> Dict:
    """
    Decode base64 text.
    
    Args:
        encoded_text: Base64 encoded text to decode
    """
    try:
        decoded = base64.b64decode(encoded_text).decode()
        return {
            "success": True,
            "encoded": encoded_text,
            "decoded": decoded
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print("🚀 Starting Text Utilities MCP Server...")
    mcp.run(transport="streamable-http")
