from mcp.server import FastMCP
from strands import Agent
from strands_tools import http_request

# Create the MCP server
mcp = FastMCP("Product Recommendation MCP Server")

PRODUCT_ASSISTANT_PROMPT = """
You are a specialized product recommendation assistant.
Provide personalized product suggestions based on user preferences, budget, and needs.
Always explain your reasoning and consider multiple options.
"""

@mcp.tool(
    name="product_recommendation_assistant",
    description="Handle product recommendation queries by suggesting appropriate products"
)
def product_recommendation_assistant(query: str) -> str:
    """
    Handle product recommendation queries by suggesting appropriate products.
    """
    formatted_query = f"""
    User request: {query}

    Provide:
    - 3–5 relevant product recommendations
    - Brief explanation for each
    - Estimated price range (if possible)
    - Pros and cons of each option
    """

    try:
        product_agent = Agent(
            model="us.amazon.nova-pro-v1:0",
            system_prompt=PRODUCT_ASSISTANT_PROMPT,
            tools=[http_request]
        )
        response = product_agent(formatted_query)
        return str(response)

    except Exception as e:
        return f"Error in product recommendation: {str(e)}"


if __name__ == "__main__":
    print("Starting Product Recommendation MCP Server...")
    mcp.run(transport="stdio")