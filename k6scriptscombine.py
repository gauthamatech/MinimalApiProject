import pandas as pd
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")

# Load CSV
df = pd.read_csv("k6_generated_scripts.csv")

# Extract all script snippets (assuming a column named 'script')
scripts = df['K6_Script'].dropna().tolist()

# Combine into one input string
combined_input = "\n\n---\n\n".join(scripts)

# Initialize LLM
llm = ChatOpenAI(
    model="qwen/qwen3-coder",
    openai_api_base="https://openrouter.ai/api/v1",
    openai_api_key=api_key,  # Replace with your key
    temperature=0.3,
    timeout=60
)

# Create prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a software agent that merges multiple K6 load testing scripts into one cohesive and valid K6 script.Ensure the output has only k6 valid syntax and structure."),
    ("human", "Merge the following K6 test scripts into a single, comprehensive test file with no duplication and good structure:\n\n{scripts}")
])

async def combinemain():
    messages = prompt.format_messages(scripts=combined_input)
    response = await llm.ainvoke(messages)
    # Clean the response (remove ``` blocks and any language identifiers)
    cleaned_content = response.content.strip()
    if cleaned_content.startswith("```"):
        cleaned_content = cleaned_content.lstrip("`")  # remove leading ```
        # remove possible language specifier (json/javascript)
        cleaned_content = cleaned_content.split("\n", 1)[1] if "\n" in cleaned_content else cleaned_content
    if cleaned_content.endswith("```"):
        cleaned_content = cleaned_content.rstrip("`")  # remove trailing ```
    with open("merged_k6_test.js", "w", encoding="utf-8") as f:
        f.write(cleaned_content)
    print("✅ Merged K6 script saved to merged_k6_test.js")

if __name__ == "__main__":
    asyncio.run(combinemain())