# subagent3_runner.py
import os
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
    
    1. Always extract the Base URL from the configuration file in the API folder. Do not hardcode or guess the Base URL; parse it directly from the config file. 
                                     
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
    - Parse the API app setup, endpoints, and models.
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
        - ⚠️ For all error codes (e.g., 400, 404, 422), extract the **actual error message** returned in the source code:
        - Parse `raise HTTPException`, `ValueError`, and any `Response(..., content=...)` usage
        - If there is a middleware and it has error messages, **give more weight to those errors than others** when extracting error messages
        - Include the **exact message** (e.g., "Email already registered", "User not found", etc.)
        - Do not invent or generalize error messages — always match what’s in the code


    5. Generate a clean API Summary Table with heading API Summary.  
    For each endpoint, write a human-readable summary in the following format:

        ### [METHOD] [PATH]
        Headers:
        Content-Type: application/json
        [Authorization: Bearer <token>] (if applicable)

        - Path Parameters: [list or None]
        - Query Parameters: [list or None]
        - Request Body (application/json):
        ```json
        {{ ...example... }}
        ```
        - For every parameter (path, query, body):
            - Clearly state whether it is required or optional
            - Clearly state whether it must be unique (e.g., unique username, unique email)
        - Response:
        - 200 OK: ...
        - 400: "Actual error message from code, e.g., 'Missing required field: email'"
        - 404: "Actual error message from code, e.g., 'User not found'"
        - 422: "Actual error message from code, e.g., 'Invalid email format'"

    6. For each endpoint, IMMEDIATELY AFTER the summary, include a section titled **Validation Details** with:
        - ✅ Example of valid input (JSON)
        - ❌ Example of invalid input (JSON)
        - Notes on what causes a 400, 422, or 404 response
        - For every parameter, specify again if it is required, optional, and/or unique

        Use this template for the Validation Details section:

        Validation Details:
        ✅ Valid Input Example:
        ```json
        {{ ...valid example... }}
        ```
        ❌ Invalid Input Example:
        ```json
        {{ ...invalid example... }}
        ```
        Notes:
            - 400: [actual message from raise HTTPException or validation error]
            - 404: [actual message from raise HTTPException or not found logic]
            - 422: [actual message from API validation error or inferred from model]
        Parameter Requirements:
            - [parameter]: required/optional, unique/not unique

        Do not skip the Validation Details section for any endpoint. If unsure, infer likely validation rules from the models and API code.

    ---

    🧾 Output Format Summary
    - Include the Base URL in the output, like BASE URL: `{{BASE_URL}}`
    Your response must include two sections:
    1. ✅ Human-Readable API Spec  
    - Includes:
        - Endpoint path and method
        - Headers
        - Required and optional parameters
        - Unique values parameters
        - Path/body/query parameters
        - JSON request example
        - JSON response example
        - **Validation Details**: what will pass/fail, with valid/invalid input examples and **actual error messages**

    ---

    """
    )
    return SYSTEM_PROMPT

def get_openai_api_key():
    load_dotenv()
    return os.getenv("OPENAI_API_KEY")

async def run_chat3_agent(prompt: str) -> str:
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
        agent = MCPAgent(
            llm=llm,client=client, max_steps=30,memory_enabled=True,system_prompt=build_system_prompt())
       # messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        response = await agent.run(prompt)
        return response
    finally:
        if hasattr(client, 'close'):
            await client.close()
        elif hasattr(client, 'disconnect'):
            await client.disconnect()
