
import os
import tempfile
from datetime import datetime
from io import BytesIO
import io
import pandas as pd
import logging
import asyncio
import openai
import streamlit as st
from dotenv import load_dotenv
# from pyvisionai import describe_image_openai
from langchain_openai import ChatOpenAI  
from langchain_core.prompts import ChatPromptTemplate
from typing import Generator
from runner import runnermain  # assuming runner.py and this Streamlit script are in same folder
from testcasegeneration import generate_test_cases_from_spec_file

# Set Streamlit page config as the first Streamlit command
# st.set_page_config(page_title="QA Spec Assistant with Test Case Generation", layout="wide")

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_FOLDER = "api_specs"
TEST_CASES_FOLDER = "test_cases"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEST_CASES_FOLDER, exist_ok=True)


SUGGESTIONS_PROMPT = """
You are a API assistant tasked with reviewing the following API specification. Your objective is to conduct a deep, critical analysis to uncover any gaps, ambiguities, or risks in the test strategy.

Provide 3–5 thoughtful, high-impact observations or questions that will help improve test coverage, usability, and product resilience. Categorize your insights using the markdown bullet list format under the following headings:

**Clarification Requests**
Identify unclear requirements or vague assumptions in the spec that could lead to misinterpretation during testing.

Ask precise questions that would help eliminate ambiguity or define edge behaviors.

**Missing Info **
Suggest additional functional, integration, or regression test cases that may have been overlooked.

Include negative paths, permission roles, multi-platform behavior, or locale/timezone impacts.

**UI Edge Cases**
Point out any high-risk visual or behavioral scenarios (e.g., long content, slow connections, animation interruptions, device rotation).

Consider screen size variations, error states, unusual input patterns, or rapid user actions.

Tone: Be proactive, precise, and user-centric. Aim to prevent bugs before they happen and ensure inclusive, resilient product quality.
"""

SPEC_UPDATE_PROMPT = """
You are a API assistant helping to update an existing API Specification document in response to user feedback.

Your task is to merge the user's requested changes seamlessly into the current API spec without rewriting or discarding unrelated content. Your updates should maintain the tone, formatting, and markdown structure of the original document. The changes should feel natural, precise, and non-disruptive, as if they were part of the original spec from the beginning.

🔧 Merging Rules:
Additions: When the user asks to add something, insert it into the most contextually appropriate section. Ensure the new content matches the voice and formatting of the surrounding material.

Removals: If the user asks to remove something, delete only that specific item or line. Do so gracefully—avoid leaving gaps or breaking sentence or list structure.

Modifications: If the user requests a change, modify only the relevant portion. Do not alter surrounding or unrelated content.

Preservation: Keep all other existing content exactly as it is—unchanged and intact.

Structure & Format: Maintain the same markdown structure, indentation, headings, bullet points, and section breaks.

Tone & Flow: Ensure your edits are linguistically and contextually smooth, without any abrupt transitions or inconsistencies in language.

📌 Special Case:
If the user mentions "approve" or "approved", respond only with: APPROVED

📝 Input Format:
Current API Spec: {current_spec}

User Request: {user_input}

✅ Your Output:
Return the updated API Specification, keeping all formatting and unmentioned content unchanged. Do not explain your edits—just present the final merged document.
"""

# === Session State Setup ===
def initialize_session_state():
    """Initialize all session state variables"""
    defaults = {
        "api_spec": "",
        "ai_suggestions": "",
        "editable_spec": "",
        "chat_history": [],
        "show_suggestions": False,
        "approved": False,
        "processing": False,
        "test_cases_generated": False,
        "test_cases_df": None,
        "test_cases_file": None,
        "generating_test_cases": False,
        "k6_scripts_generated" : False,
        "k6_scripts_combined": False,
        "k6_run_response" :None

    }
    
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


# def generate_ai_suggestions(spec):
#     """Generate AI suggestions for the API spec"""
#     try:
#         response = openai_client.chat.completions.create(
#             model="gpt-4.1-nano",
#             messages=[
#                 {"role": "system", "content": SUGGESTIONS_PROMPT},
#                 {"role": "user", "content": spec}
#             ],
#             max_tokens=500
#         )
#         return response.choices[0].message.content.strip()
#     except Exception as e:
#         st.error(f"❌ Error generating suggestions: {e}")
#         return ""

def update_spec_from_user_input(user_input, current_spec):
    """Update API spec based on user input while preserving existing content"""
    try:
        # Check if user is approving
        if any(word in user_input.lower() for word in ['approve', 'approved', 'looks good', 'lgtm']):
            return "APPROVED"
        
        # Check if user wants to ignore suggestions
        if any(word in user_input.lower() for word in ['ignore', 'skip suggestions', 'no suggestions']):
            return "IGNORE_SUGGESTIONS"
            
        prompt = SPEC_UPDATE_PROMPT.format(
            current_spec=current_spec,
            user_input=user_input
        )
        
        response = openai_client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        st.error(f"❌ Error updating spec: {e}")
        return current_spec

def save_spec(content):
    """Save the API spec to a markdown file"""
    try:
        filename = f"api_spec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(OUTPUT_FOLDER, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return filepath
    except Exception as e:
        st.error(f"❌ Error saving spec: {e}")
        return None

def handle_chat_input(user_input):
    """Handle user chat input and update the spec accordingly"""
    if not user_input.strip():
        return
    
    st.session_state.processing = True
    
    # Add user message to chat history
    st.session_state.chat_history.append({
        "role": "user", 
        "content": user_input,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    # Process the input
    result = update_spec_from_user_input(user_input, st.session_state.editable_spec)
    
    if result == "APPROVED":
        # User approved the spec
        filepath = save_spec(st.session_state.editable_spec)
        if filepath:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"✅ API Spec approved and saved to `{filepath}`",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            st.session_state.approved = True
        
    elif result == "IGNORE_SUGGESTIONS":
        # User wants to ignore suggestions
        st.session_state.show_suggestions = False
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "📝 Suggestions hidden. You can continue chatting to modify the API spec.",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
    else:
        # Update the spec
        st.session_state.editable_spec = result
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "✅ API Spec updated based on your request.",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    
    st.session_state.processing = False

def display_progress_tracker():
    step_labels = [
        "API Spec Generation",
        "Approve API Spec",
        "Generate Test Cases",
        "Approve Test Cases",
        "Generate K6 Scripts",
        "Combine K6 Scripts",
        "Run K6 Tests"
    ]

    step_states = [
        bool(st.session_state.get("api_spec")),
        bool(st.session_state.get("approved")),
        bool(st.session_state.get("test_cases_generated")),
        bool(st.session_state.get("test_cases_approved")),
        bool(st.session_state.get("k6_scripts_generated")),
        bool(st.session_state.get("k6_scripts_combined")),
        bool(st.session_state.get("k6_run_response"))
    ]

    current_index = step_states.index(False) if False in step_states else len(step_labels)

    if "progress_checkpoint" not in st.session_state:
        st.session_state.progress_checkpoint = -1


    with st.sidebar:


        for i, label in enumerate(step_labels):
            if i < current_index:
                icon = "✅"
                color = "#4CAF50"  # Green
            elif i == current_index:
                icon = "🟡"
                color = "#FFA500"  # Orange
            else:
                icon = "⚪"
                color = "#999999"  # Gray

            st.markdown(
                f"<div style='margin-bottom:6px; color:{color}; font-size:0.9rem;'>{icon} {label}</div>",
                unsafe_allow_html=True
            )


def display_chat_interface():
    """Display the chat interface for spec interaction"""
    st.subheader("💬 Chat with API Spec")
    
    if st.session_state.chat_history:
        for message in st.session_state.chat_history[-10:]:
            with st.chat_message(message["role"]):
                st.markdown(f"*{message['timestamp']}*: {message['content']}")
    
    if not st.session_state.processing and not st.session_state.approved:
        user_message = st.chat_input("Chat with API assistant...")

    if user_message:
        handle_chat_input(user_message)
        st.rerun()

def display_improved_ui():
    """Display improved UI for API spec and suggestions"""
    st.subheader("📋 API Specification")
    
    with st.expander("API Spec Details", expanded=False):
        st.markdown(st.session_state.editable_spec)
    
    import re
    if st.session_state.show_suggestions and st.session_state.ai_suggestions:
        st.subheader("AI Insights & Queries")

        suggestions = st.session_state.ai_suggestions.splitlines()
        sections = {
            # "Clarification Requests": [],
            # "Missing Info": [],
            # "UI Edge Cases":[]
        }

        current_section = None
        start_parsing = False

        for line in suggestions:
            line = line.strip()
            if not line:
                continue

            # Match section headers with or without '-' at start
            header_match = re.match(r"-?\s*\*\*(.+?)\*\*", line)
            if header_match:
                current_section = header_match.group(1).strip()
                start_parsing = True
                continue

            if not start_parsing or current_section not in sections:
                continue

            # Bullet or continuation
            if line.startswith("-"):
                sections[current_section].append(line[1:].strip())
            else:
                if sections[current_section]:
                    sections[current_section][-1] += " " + line.strip()

        # Render parsed suggestions
        if any(sections.values()):
            for title, points in sections.items():
                if points:
                    with st.expander(title, expanded=False):
                        for point in points:
                            st.markdown(f"- <span style='color: white; font-weight: bold'>{point}</span>", unsafe_allow_html=True)
        else:
            st.warning("No suggestions available. This may indicate the API spec lacks testable elements or the AI output is empty.")

          
def display_suggestions():
    """Display AI suggestions if available"""
    if st.session_state.show_suggestions and st.session_state.ai_suggestions:
        st.subheader("💡 AI Suggestions & Questions")
        st.markdown(st.session_state.ai_suggestions)
        st.info("💬 Use the chat below to address these suggestions or type 'ignore suggestions' to hide them.")

def display_test_cases():
    """Display and allow editing of generated test cases"""
    if st.session_state.test_cases_generated and st.session_state.edited_test_cases_df is not None:
        st.subheader("📋 Generated Test Cases")
        
        # Convert DataFrame to editable format using st.data_editor
        edited_df = st.data_editor(
            st.session_state.edited_test_cases_df,
            num_rows="dynamic"
        )
        
        st.session_state.edited_test_cases_df = edited_df
        
        if st.button("✅ Approve Test Cases"):
            st.session_state.test_cases_approved = True
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_filename = f"my_test_cases.csv"
            csv_path = os.path.join(TEST_CASES_FOLDER, csv_filename)
            edited_df.to_csv(csv_path, index=False)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "✅ Test cases have been approved.",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            st.rerun()


def main():
    """Main application function"""
    # Streamlit setup
    # st.set_page_config(page_title="QA Spec Assistant with Test Case Generation", layout="wide")
    st.title("API SPEC ASSISTANT")
    
    # Initialize session state
    initialize_session_state()
    
    # Show upload section only if not approved
    if not st.session_state.approved and not st.session_state.test_cases_generated:
        # Replace this with your actual folder path
        FOLDER_PATH = "MiddlewareMinApi"

        # Display folder path
        st.markdown(f"**📁 API Path:** `{os.path.abspath(FOLDER_PATH)}`")

        st.markdown("### 📄 API Summary")
        st.write(f"This FastAPI project is a simple RESTful API for managing Users, Categories, and Items, backed by a PostgreSQL database. It defines a total of 12 endpoints: 4 each for users (POST, GET, PUT, DELETE), categories, and items. The application uses Pydantic for input validation, UUIDs for primary keys, and raw SQL via psycopg2 for database interactions. Middleware is included to customize 422 validation errors. The database schema includes three main tables (users, categories, items), where items are linked to categories using foreign keys. Configuration is handled through environment variables using python-dotenv.")
        
        
        if st.button("Generate API Spec"):
            with st.spinner("🔍 Generating unified API spec..."):  
                import asyncio  
                spec = asyncio.run(runnermain())
                
                # if spec:
                #     suggestions = generate_ai_suggestions(spec)
                    
                #     # Update session state
                st.session_state.api_spec = spec
                st.session_state.editable_spec = spec
                    # st.session_state.ai_suggestions = suggestions
                st.session_state.show_suggestions = True
                st.session_state.chat_history = []
                st.session_state.approved = False
                st.session_state.test_cases_generated = False
                    
                st.rerun()
    
    # Display spec if available and not yet moved to test case generation
    if st.session_state.api_spec and not st.session_state.test_cases_generated and not st.session_state.approved:
        
        display_improved_ui()
        
        display_chat_interface()
          
        # Manual approve button
        if not st.session_state.approved:
            if st.button("✅ Approve API SPEC", key="approve_button"):
                filepath = save_spec(st.session_state.editable_spec)
                if filepath:
                    st.session_state.approved = True
                    st.success(f"✅ API Spec approved and saved to `{filepath}`")
                    st.rerun()

    # Show test case generation section if approved
    if st.session_state.approved and not st.session_state.test_cases_generated:
        st.markdown("---")
        st.subheader("🧪 Test Case Generation")
        st.info("Your API specification has been approved. Now generate comprehensive test cases.")
        # Update session state
        
        if st.button("🚀 Generate Test Cases", disabled=st.session_state.generating_test_cases):
            generate_test_cases_from_spec_file("Unified_API_Spec.md", "my_test_cases.csv")
            df =pd.read_csv("my_test_cases.csv")
            st.session_state.generating_test_cases = False
            st.session_state.test_cases_df = df
            st.session_state.edited_test_cases_df = df.copy()
            st.session_state.test_cases_generated = True
            st.rerun()

    # Display test cases if generated
    if st.session_state.test_cases_generated:

        if not st.session_state.get("test_cases_approved"):
            # Show test cases and approval UI
            display_test_cases()
        else:
            # if "k6_scripts_generated" not in st.session_state:
            #     st.session_state["k6_scripts_generated"] = False
            # if "k6_scripts_combined" not in st.session_state:
            #     st.session_state["k6_scripts_combined"] = False
            if not st.session_state["k6_scripts_generated"]:
                st.success("✅ Test cases have been saved and approved.")
                if st.button("⚡ Generate k6 Scripts"):
                    import asyncio
                    from k6scriptgeneration import process_all
                    with st.spinner("🔍 Generating k6 script..."): 
                        asyncio.run(process_all())
                    st.session_state["k6_scripts_generated"] = True
                    st.success("✅ k6 scripts generated and saved to k6_generated_scripts.csv.")
                    df = pd.read_csv("k6_generated_scripts.csv")
                    for _, row in df.iterrows():
                        with st.expander(row["Test_Case_Description"], expanded=False):
                            st.markdown(f"```javascript\n{row['K6_Script']}\n```")
                    st.rerun()
            elif not st.session_state["k6_scripts_combined"]:
                st.success("✅ k6 scripts generated and saved to k6_generated_scripts.csv.")
                df = pd.read_csv("k6_generated_scripts.csv")
                for _, row in df.iterrows():
                    with st.expander(row["Test_Case_Description"], expanded=False):
                        st.markdown(f"```javascript\n{row['K6_Script']}\n```")
                if st.button("🔗 Combine k6 Scripts"):
                    import asyncio
                    from k6scriptscombine import combinemain
                    with st.spinner("🔍 Combining k6 scripts..."): 
                        asyncio.run(combinemain())
                    st.session_state["k6_scripts_combined"] = True
                    st.success("✅ k6 scripts combined and saved to merged_k6_test.js.")
                    st.rerun()
            elif st.session_state["k6_scripts_combined"]:
                if "show_k6_combined_success" not in st.session_state:
                    st.session_state["show_k6_combined_success"] = True
                if st.session_state["show_k6_combined_success"]:
                    st.success("✅ k6 scripts combined and saved to merged_k6_test.js.")

                # Show "Run k6 Scripts" button
                if "k6_run_response" not in st.session_state:
                    st.session_state["k6_run_response"] = None

                if st.session_state["show_k6_combined_success"]:
                    if st.button("▶️ Run k6 Scripts"):
                        import asyncio
                        from k6mcp_runner import run_k6_agent_query
                        with st.spinner("🚦 Running k6 scripts..."):
                            response = asyncio.run(run_k6_agent_query())
                            st.session_state["k6_run_response"] = response
                        st.session_state["show_k6_combined_success"] = False
                        st.rerun()

                # Display the k6 run response if available
                if st.session_state["k6_run_response"]:
                    st.subheader("k6 Run Results")
                    st.markdown(st.session_state["k6_run_response"])
                # Show "Start New API Spec" button at the bottom
                if st.button("🔄 Start New API Spec"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()



if __name__ == "__main__":
    display_progress_tracker()
    main()