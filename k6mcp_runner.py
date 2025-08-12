import asyncio
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

# Set the system prompt for the K6 Agent
SYSTEM_PROMPT = f"""
You are a specialized K6 Load Testing Agent that helps users run and analyze performance tests.

Your primary capabilities:
1. Execute K6 test scripts on specified JavaScript files
2. Analyze test results and provide performance insights
3. Help modify test parameters like VUs (Virtual Users) and duration
4. Suggest improvements to test scripts

When a user mentions a JavaScript file, you should:
1. Examine the file content if possible
2. Identify the test scenarios defined in the file
3. Use the export const options (e.g., vus, iterations, duration, etc.) specified in the JavaScript file for test execution, unless the user provides different parameters
4. Execute the test using the K6 MCP server tools
5. Present the results in a clear, structured format with:
   - Response times (min, max, average, p90, p95)
   - Success rates
   - Error analysis
   - Throughput metrics

Available commands:
- Run a test file: Execute a K6 test script (e.g., "Run k6code1.js")
- Run with options: Execute with custom VUs and duration (e.g., "Run k6code1.js with 50 users for 30 seconds")
- Analyze: Provide detailed analysis of a previously run test

Always use the K6 MCP server tools for executing tests rather than terminal commands.

Current working directory: {os.getcwd()}
"""

# Global variables for caching agent and client
_agent = None
_client = None

def get_openai_api_key():
    load_dotenv()
    return os.getenv("OPENROUTER_API_KEY")

async def initialize_k6_agent():
    global _agent, _client
    if _agent and _client:
        return _agent, _client

    api_key = get_openai_api_key()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment or .env file.")

    config_file = "mcpk6.json"
    _client = MCPClient.from_config_file(config_file)

    llm = ChatOpenAI(
        model="z-ai/glm-4.5",
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=api_key,
        temperature=0.3,
        timeout=180
    )

    _agent = MCPAgent(
        llm=llm,
        client=_client,
        max_steps=50,
        memory_enabled=True,
        system_prompt=SYSTEM_PROMPT
    )

    return _agent, _client

async def run_k6_agent_query() -> str:
    """
    Runs the K6 agent with the provided user input and returns the structured response.
    """
    agent, client = await initialize_k6_agent()

    try:
        response = await agent.run("K6 run D:\\API\\MiddlewareMinApi\\merged_k6_test.js for 1 vu and 3 seconds")
        return response
    except Exception as e:
        return f"❌ Error: {e}"