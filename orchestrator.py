# orchestrator.py
from agents import Agent, Runner
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import os
from agents.mcp import MCPServerStdio

from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

class UnifiedSpecOutput(BaseModel):
    combined_markdown: str


async def get_orchestrator():
    server = MCPServerStdio(
        name = "Context7",
        params= {
          "command": "npx",
          "args": ["-y", "@upstash/context7-mcp"]
        },
        client_session_timeout_seconds=60
    )
    await server.connect()
    return Agent(
        name="API Spec Orchestrator",
        model="gpt-4.1-mini",
        mcp_servers=[server],
        instructions="""
🔧 Before starting:**Non-Negotiable**
Use the `Context7` tool **always to understand and verify HTTP response status codes** using **MDN Web Docs**. This is your reference source for interpreting what each status code means and when to use it accurately across the API.
-**Tell user if you have used the Context7 tool to verify the HTTP response status code, AT the Very bottom , if not used tell that too**.
---

You will receive:

1. ✅ A human-readable API spec (with validation and examples)
2. 🧾 A YAML OpenAPI 3.1 spec

Merge both into a unified QA specification document that includes:

---

### 🔄 Combined API Overview
- Key endpoints with summaries from both specs
- For each endpoint, list all input fields and specify whether each is required or optional
-- Include the Base URL in the output, like BASE URL: `{{BASE_URL}}

---

### ✅ Happy Path Scenarios
- Valid input examples that should pass for each endpoint  with expected response code (e.g., 200 , 300 , etc)

---

### ❌ Negative Path Scenarios
- Invalid input examples with expected response code (e.g., 400, 404, 422, etc.) and error message
- Empty input with expected response code and error message

---

### 🧪 Test Cases
- Bullet-style test cases derived from validation logic
- For each endpoint, include at least 2 happy and 2 negative tests

---

### ⚠️ Edge Case Scenarios
- Describe boundary, unusual, or rare input cases for each endpoint
- Note any backend/frontend mismatches or quirks

---

Return the full result as markdown.
""",
        output_type=UnifiedSpecOutput
    )
