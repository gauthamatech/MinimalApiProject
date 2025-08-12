import pandas as pd
import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")

llm = ChatOpenAI(
    model="qwen/qwen3-coder",
    openai_api_base="https://openrouter.ai/api/v1",
    openai_api_key=api_key,
    temperature=0.3,
    timeout=60
)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", """You are an expert k6 load testing script generator.  
    Your task is to generate fully functional **k6 test scripts** based on the user-provided test flow.  
    Follow these guidelines:  

    1. **Always return code in JavaScript** using valid k6 syntax (`http`, `check`, `group`, `sleep`).  
    2. Include `import` statements, `options` block, and `export default function()`.  
    3. Use `group()` to clearly label each test step.  
    4. Ensure all `POST`, `GET`, `PUT`, and `DELETE` requests use `http` module functions (`http.post`, `http.get`, etc.).  
    5. Use `check()` for assertions with clear messages (e.g., `'Status 200 OK'`).  
    6. Parse and use IDs (like `user_id`, `category_id`) from previous responses using `JSON.parse`.  
    7. If a required value is missing (like `user_id`), gracefully skip dependent steps with console errors.  
    8. End each iteration with `sleep(1)` to simulate real user wait time.  
    9. For any field that must be unique (such as username or email), use dynamic values in your script, e.g.:
    - `username: `testuser${{__VU}}-${{__ITER}}``
    - `email: `test${{__VU}}-${{__ITER}}@example.com``
    This ensures each test iteration uses a unique value and avoids duplicate errors.
    10. Follow the structure and best practices shown in the example below. 
    11. When validating error or success messages, use `check()` to assert response body content:
        - Example: `'Delete message present': (r) => r.body.includes('User deleted')`  
        - Apply this for both positive and negative tests where response text matters. 

    ---

    ### **Example Output**
    ```javascript
    import http from 'k6/http';
    import {{ check, group, sleep }} from 'k6';

    export const options = {{
    vus: 1,
    iterations: 1,
    }};

    const BASE_URL = 'http://127.0.0.1:8001';

    export default function () {{
    let user_id = null;

    group('1. Create User (POST /users/)', function () {{
        const payload = JSON.stringify({{
        username: "johndoe",
        email: "john@example.com",
        password_hash: "hashed_password_123",
        }});
        const headers = {{ 'Content-Type': 'application/json' }};
        const res = http.post(`${{BASE_URL}}/users/`, payload, {{ headers }});

        check(res, {{
        'User created 200/201': (r) => r.status === 200 || r.status === 201,
        'Response has user_id': (r) => {{
            try {{
            const body = JSON.parse(r.body);
            user_id = body.user_id;
            return !!user_id;
            }} catch (e) {{
            console.error('❌ Failed to parse user creation response:', r.body);
            return false;
            }}
        }},
        }});
    }});

    if (!user_id) {{
        console.error('❌ user_id is undefined, skipping next steps...');
        return;
    }}

    group('2. GET User (GET /users/{{user_id}})', function () {{
        const res = http.get(`${{BASE_URL}}/users/${{user_id}}`);
        check(res, {{ 'GET User 200 OK': (r) => r.status === 200 }});
    }});

    group('3. Update User (PUT /users/{{user_id}})', function () {{
        const payload = JSON.stringify({{
        email: "newemail@example.com",
        password_hash: "new_hashed_password",
        }});
        const headers = {{ 'Content-Type': 'application/json' }};
        const res = http.put(`${{BASE_URL}}/users/${{user_id}}`, payload, {{ headers }});
        check(res, {{ 'Update User 200 OK': (r) => r.status === 200 }});
    }});

    group('4. Delete User (DELETE /users/{{user_id}})', function () {{
        const res = http.del(`${{BASE_URL}}/users/${{user_id}}`);
        check(res, {{
        'Delete User 200 OK': (r) => r.status === 200,
        'Delete message present': (r) => r.body.includes('User deleted'),
        }});
    }});

    sleep(1);
    }}
    ```
    ---

    When the user provides a test flow or sequence of API actions, return a single full k6 script following this structure. Always use dynamic values for unique fields."""),  # full system prompt here
    ("user", "{input}")
])
chain = prompt_template | llm | StrOutputParser()

async def generate_k6_script(step):
    try:
        return await chain.ainvoke({"input": step})
    except Exception as e:
        return f"// ❌ Error: {e}"

async def process_all():
    df = pd.read_csv("my_test_cases.csv")
    df = df.iloc[0:3]
    output = []

    for _, row in df.iterrows():
        test_case_id = row["Test_Case_ID"]
        test_steps = row["Test_Steps"]
        test_description = row["Test_Case_Description"]
        print(f"Generating script for {test_case_id}...")

        script = await generate_k6_script(test_steps)
        cleaned_content = script.strip()
        if cleaned_content.startswith("```"):
            cleaned_content = cleaned_content.lstrip("`")  # remove leading ```
            # remove possible language specifier (json/javascript)
            cleaned_content = cleaned_content.split("\n", 1)[1] if "\n" in cleaned_content else cleaned_content
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content.rstrip("`")  # remove trailing ```
        output.append({"Test_Case_ID": test_case_id, "Test_Case_Description": test_description, "K6_Script": cleaned_content})

    out_df = pd.DataFrame(output)
    out_df.to_csv("k6_generated_scripts.csv", index=False)
    print("✅ Done. Scripts saved to k6_generated_scripts.csv")

def main():
    asyncio.run(process_all())

if __name__ == "__main__":
    main()