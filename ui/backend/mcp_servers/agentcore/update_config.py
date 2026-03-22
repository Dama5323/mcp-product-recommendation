"""
Helper script to update mcp.json with your AgentCore URL
Run this after deployment to automatically configure the remote server
"""
import json
import boto3
import sys
import os

def get_region():
    """Get AWS region from session or environment"""
    session = boto3.Session()
    region = session.region_name
    
    # If region is not set in session, try to get from environment or use default
    if not region:
        region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
        if not region:
            region = 'us-west-2'  # Default fallback
            print(f"⚠️  No region configured, using default: {region}")
    
    return region

def get_agent_arn(region):
    """Retrieve Agent ARN from Parameter Store"""
    try:
        ssm_client = boto3.client('ssm', region_name=region)
        response = ssm_client.get_parameter(Name='/workshop/text_utils_mcp/agent_arn')
        return response['Parameter']['Value']
    except Exception as e:
        print(f"❌ Error retrieving Agent ARN: {e}")
        print("Make sure you've deployed first: python3 deploy_to_agentcore.py")
        return None

def build_agentcore_url(agent_arn, region):
    """Build AgentCore invocation URL from ARN"""
    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

def update_mcp_config(url):
    """Update mcp.json with the AgentCore URL"""
    config_path = os.path.join(os.path.dirname(__file__), '../../mcp.json')
    
    try:
        # Read current config
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Update text_utils_remote
        if 'text_utils_remote' in config.get('mcpServers', {}):
            config['mcpServers']['text_utils_remote']['url'] = url
            config['mcpServers']['text_utils_remote']['enabled'] = True
            
            # Save updated config
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Configuration updated successfully!")
            print(f"\nUpdated: {config_path}")
            print(f"URL: {url}")
            print("\n📝 Next step: (Optional) Restart the workshop app if needed")
            print("   cd /workshop/ui/ && ./stop.sh && ./start.sh")
            return True
        else:
            print("❌ text_utils_remote not found in mcp.json")
            return False
            
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

def main():
    print("🔧 Configuring AgentCore Remote Server\n")
    
    # Get region first
    region = get_region()
    print(f"✓ Region: {region}")
    
    # Get Agent ARN
    agent_arn = get_agent_arn(region)
    if not agent_arn:
        sys.exit(1)
    
    print(f"✓ Found Agent ARN: {agent_arn}")
    
    # Build URL
    url = build_agentcore_url(agent_arn, region)
    print(f"✓ AgentCore URL: {url}\n")
    
    # Update config
    if update_mcp_config(url):
        print("\n🎉 Configuration complete!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
