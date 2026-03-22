"""
Deploy Note Manager to AgentCore Runtime
Run this script to deploy your MCP server to production
"""
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session
import os

# Initialize AWS session and get region
boto_session = Session()
region = boto_session.region_name

# If region is not set in session, try to get from environment or use default
if not region:
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if not region:
        # Try to get from EC2 instance metadata
        try:
            import boto3
            region = boto3.DEFAULT_SESSION.region_name if boto3.DEFAULT_SESSION else None
        except:
            pass
    if not region:
        region = 'us-west-2'  # Default fallback
        print(f"⚠️  No region configured, using default: {region}")

print(f"🌍 Deploying to region: {region}")

# Initialize AgentCore Runtime
agentcore_runtime = Runtime()

# Configure deployment
print("\n⚙️  Configuring AgentCore Runtime...")
response = agentcore_runtime.configure(
    entrypoint="text_utils_server.py",
    auto_create_execution_role=True,
    auto_create_ecr=True,
    requirements_file="requirements.txt",
    region=region,
    protocol="MCP",
    agent_name="text_utils_mcp",
)
print("✓ Configuration completed")

# Launch to AgentCore
print("\n🚀 Launching to AgentCore Runtime...")
print("This may take 3-5 minutes...")
launch_result = agentcore_runtime.launch()

print("\n✅ Deployment Complete!")
print(f"Agent ARN: {launch_result.agent_arn}")
print(f"Agent ID: {launch_result.agent_id}")

# Store ARN for later use
ssm_client = boto_session.client('ssm', region_name=region)
ssm_client.put_parameter(
    Name='/workshop/text_utils_mcp/agent_arn',
    Value=launch_result.agent_arn,
    Type='String',
    Description='Text Utilities MCP Server Agent ARN',
    Overwrite=True
)
print("✓ Agent ARN stored in Parameter Store")

# Print instructions for mcp.json
print("\n" + "="*60)
print("📝 Next Steps:")
print("="*60)
print("\n1. Run the auto-config script:")
print("   python3 update_config.py")
print("\n   OR manually update /workshop/ui/backend/mcp.json:")
print(f"   Replace URL with your AgentCore endpoint")
print('   Set "enabled": true')
print("\n2. (Optional) Restart the workshop app if needed:")
print("   cd /workshop/ui/ && ./stop.sh && ./start.sh")
print("\n🎉 Your MCP server will be live on AgentCore!")
print("="*60)
