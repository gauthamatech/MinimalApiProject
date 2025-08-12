import asyncio
from subagent3 import run_chat3_agent
from subagent4 import run_chat4_agent
from orchestrator import get_orchestrator
from agents import Runner

async def runnermain():
    # module_name = input("🔹 Module name: ")
    # user_prompt = f"Generate detailed API spec"

    # task3 = run_chat3_agent(user_prompt)
    # task4 = run_chat4_agent(user_prompt)

    # spec3, spec4 = await asyncio.gather(task3, task4)

    # print("✅ Sub-agents complete.")

    # Save sub-agent outputs
    human_readable_file = f"Human_Readable_API_Spec.md"
    openapi_yaml_file = f"OpenAPI_YAML_Spec.md"
    # with open(human_readable_file, "w", encoding="utf-8") as f:
    #     f.write(spec3.strip())
    # with open(openapi_yaml_file, "w", encoding="utf-8") as f:
    #     f.write(spec4.strip())
    # print(f"📄 Human-readable API spec saved to `{human_readable_file}`")
    # print(f"📄 OpenAPI YAML spec saved to `{openapi_yaml_file}`")

    # Read sub-agent outputs from files
    with open(human_readable_file, "r", encoding="utf-8") as f:
        spec3 = f.read()
    with open(openapi_yaml_file, "r", encoding="utf-8") as f:
        spec4 = f.read()

    combined_input = f"""
        ✅ Human-Readable API Spec:
        {spec3}

        🧾 OpenAPI YAML Spec:
        {spec4}
    """

    orchestrator = await get_orchestrator()
    try:
        final_result = await Runner.run(orchestrator, combined_input)
        unified_md = final_result.final_output.combined_markdown.strip()
        output_file = f"Unified_API_Spec.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(unified_md)
        print(f"✅ Unified spec saved to `{output_file}`")
        return unified_md
    finally:
        # If orchestrator or its server has a disconnect/close method, call it here
        if hasattr(orchestrator, "disconnect"):
            await orchestrator.disconnect()
        elif hasattr(orchestrator, "close"):
            await orchestrator.close()

if __name__ == "__main__":
    try:
        asyncio.run(runnermain())
    except (asyncio.CancelledError, RuntimeError) as e:
        print(f"Shutdown error: {e}")
