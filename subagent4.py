# subagent4_runner.py
import os, asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

# files_to_combine = [
#     "main.py",
#     "dbfiles/category.py",
#     "dbfiles/items.py",
#     "dbfiles/users.py",
#     "dbfiles/dbcreation.py",
#     "dbfiles/schema.sql"
# ]

# combined_code = ""
# for file_path in files_to_combine:
#     with open(file_path, "r", encoding="utf-8") as f:
#         combined_code += f"\n# ===== {file_path} =====\n"
#         combined_code += f.read()

def build_system_prompt() -> str:
  SYSTEM_PROMPT = ("""
🧠 SYSTEM PROMPT: Extract OpenAPI Spec and Detailed API Overview from API Source Code

  You are an expert API architecture and documentation assistant.  
  You receive the complete API source code that includes endpoint routes, models, and database logic.

  ---

  🎯 Your Task

  Given the API code folder, you must:
    
    1. Always extract the Base URL from the configuration file (such as mcp.json) in the API folder. Do not hardcode or guess the Base URL; parse it directly from the config file.
                   
    2. Use the Model Context Protocol (MCP) Filesystem server to access the API code folder context.
    - Always use the MCP Filesystem server for reading files and gathering code context.
    - The server is available at:  
        ```
        npx -y @modelcontextprotocol/server-filesystem D:\\API\\MiddleMinApiProj
        ```
    - Parse the API app setup, endpoints, and models using the filesystem context.
    - Identify how endpoints are structured (CRUD, nested paths, etc.)
    - Map each endpoint to its purpose (e.g., Create User, Get Item, etc.)

    3. Understand the application architecture  
      - Parse the FastAPI app setup, endpoints, and models.
      - Identify how endpoints are structured (CRUD, nested paths, etc.)
      - Map each endpoint to its purpose (e.g., Create User, Get Item, etc.)

    4. Extract All Endpoints  
      - For each route (e.g. /users/, /categories/{{category_id}}), capture:
        - HTTP method
        - Route path
        - Associated model (if applicable)
        - Parameters: path, query, body
        - Validation rules
        - Response schema and possible error codes

    5. Generate a full OpenAPI Spec (YAML format)  
        - A valid OpenAPI 3.1.0 YAML document.
        - Include the following top-level sections: `openapi`, `info`, `servers`, `components`, and `paths`.
        - For each endpoint, specify:
        - HTTP method and path.
        - Summary and description.
        - Parameters (path, query, etc.) with types and requirements.
        - Request body schema and example (if applicable).
        - Response status codes, descriptions, and response schemas/examples.
        - Define reusable schemas in `components/schemas`.
        - If authentication is present, specify security schemes in `components/securitySchemes` and reference them in endpoints.
        - Use clear, concise field names and realistic example values.
        - Format output as YAML, not JSON or Markdown.
        - Do not include any explanation or commentary—only the OpenAPI YAML.

        Your OpenAPI spec should closely follow this example structure:

        openapi: 3.1.0
        info:
          title: Example API
          version: 1.0.0
          description: Example description
        servers:
          - url: https://api.example.com/v1
        components:
          securitySchemes:
            BearerAuth:
              type: http
              scheme: bearer
              bearerFormat: JWT
          schemas:
            Example:
              type: object
              properties:
                id:
                  type: string
                  format: uuid
                  example: eda5cbc1-a615-4da5-ae73-4a33a9acfb6a
        paths:
          /example:
            get:
              summary: Get example
              responses:
                '201':
                  description: User created
                '400':
                  description: Invalid input

    ---

    🧾 Output Format Summary

    - Include the Base URL in the output, like BASE URL: `{{BASE_URL}}`
    Your response must include :

    1. ✅ OpenAPI Spec (YAML format)  
      - Includes all endpoints, schemas, and validation rules.

    ---
    """
  )
  return SYSTEM_PROMPT

def get_openai_api_key():
    load_dotenv()
    return os.getenv("OPENAI_API_KEY")


async def run_chat4_agent(prompt: str) -> str:
    config_file = "mcp.json"

    # Create MCP client and agent with memory enabled
    client = MCPClient.from_config_file(config_file)
    try:
        llm = ChatOpenAI(
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        model="qwen/qwen3-235b-a22b-thinking-2507",
        temperature=0.3,
        timeout=60)
        agent = MCPAgent(llm=llm, client=client, max_steps=30, memory_enabled=True,system_prompt=build_system_prompt())
    # messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        response = await agent.run(prompt)
        return response
    finally:
        if hasattr(client, 'close'):
            await client.close()
        elif hasattr(client, 'disconnect'):
            await client.disconnect()
