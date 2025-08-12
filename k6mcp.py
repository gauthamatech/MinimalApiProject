import asyncio
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI 
from mcp_use import MCPAgent,MCPClient

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
3. Execute the test using the K6 MCP server tools
4. Present the results in a clear, structured format with:
   - Response times (min, max, average, p90, p95)
   - Success rates
   - Error analysis
   - Throughput metrics

Available commands:
- Run a test file: Execute a K6 test script (e.g., "Run k6code1.js")
- Run with options: Execute with custom VUs and duration (e.g., "Run k6code1.js with 50 users for 30 seconds")
- Analyze: Provide detailed analysis of a previously run test

Always use the K6 MCP server tools for executing tests rather than terminal commands.

"""

def get_openai_api_key():
    # Try to get from environment or .env
    load_dotenv()
    return os.getenv("OPENAI_API_KEY")

async def run_openai_chat():
    """Run a chat using OpenAI only."""
    api_key = get_openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment or .env file.")
    os.environ["OPENAI_API_KEY"] = api_key

    config_file = "mcpk6.json"

    print("Initializing chat...")

    client = MCPClient.from_config_file(config_file)

    llm = ChatOpenAI(
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        model="z-ai/glm-4.5",
        temperature=0.3,
        timeout=60
    )

    agent = MCPAgent(
        llm=llm, 
        client=client, 
        max_steps=50,  # Increased steps for thorough analysis
        memory_enabled=True,
        system_prompt=SYSTEM_PROMPT
    )

    try:
        while True:
            # Get user input
            user_input = input("K6 Test Agent: ")
            
            
            try:
                print("\n🔄 Analyzing... (this may take a moment for thorough code review)")
                response = await agent.run(user_input)
                print(f"\n📄 k6 Test Result:\n{response}")
                print("\n" + "="*60 + "\n")
            except Exception as e:
                print(f"\n❌ Error: {e}")
                
    finally:
        if client and client.sessions:
            await client.close_all_sessions()
            print("🔌 MCP sessions closed.")

    # try:
    #     while True:
    #         # print(SYSTEM_PROMPT)
    #         user_input = input("\nYou: ")
            

    #         if user_input.lower() in ["exit", "quit"]:
    #             print("Ending conversation...")
    #             break

    #         print("\nAssistant: ", end="", flush=True)

    #         try:
    #             # Always send the system prompt as the first message
    #             messages = [
    #                 {"role": "system", "content": SYSTEM_PROMPT},
    #                 {"role": "user", "content": user_input}
    #             ]
    #             response = await llm.ainvoke(messages)
    #             print(response.content)
    #             # Save output to output.md
    #             with open("k6code.js", "w", encoding="utf-8") as f:
    #                 f.write(response.content)
    #         except Exception as e:
    #             print(f"\nError: {e}")

    # finally:
    #     pass  # No MCP client cleanup needed

if __name__ == "__main__":
    asyncio.run(run_openai_chat())