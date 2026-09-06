import asyncio
import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

#########################################################################

# Load all env variables
load_dotenv()
API_URL = os.getenv('API_URL')
API_KEY = os.getenv('API_KEY')
MODEL = os.getenv('MODEL')

mcp_dir = os.path.dirname(os.path.abspath(__file__))
server_params = StdioServerParameters(
    command=r'C:\Users\Makaty\PycharmProjects\openAI_mcp_course2026\.venv\Scripts\python.exe',
    args=[os.path.join(mcp_dir, "mcp_server.py")],
)

client = OpenAI(api_key=API_KEY, base_url=API_URL)


def mcp_tool_to_openai_tool(mcp_tool) -> dict:
    """Convert an MCP tool definition into the OpenAI function-calling schema."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema,
        },
    }


async def query_agent(session: ClientSession, openai_tools: list, conversation: list) -> str:
    """
    Send the conversation to the model, handle any tool calls it requests
    (by executing them through the MCP session), and return the final
    assistant text reply.
    """
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=conversation,
            tools=openai_tools,
        )
        choice = response.choices[0]
        message = choice.message

        # No tool calls -> this is the final answer
        if not message.tool_calls:
            conversation.append({"role": "assistant", "content": message.content})
            return message.content

        # Model wants to call one or more tools
        conversation.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        })

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments or "{}")
            print(f"  [calling tool: {tool_name}({tool_args})]")

            result = await session.call_tool(tool_name, tool_args)
            # result.content is a list of content blocks (usually one text block)
            result_text = "".join(
                block.text for block in result.content if hasattr(block, "text")
            )

            conversation.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_text,
            })
        # loop again so the model can see the tool result(s) and respond


async def chat_loop():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = await session.list_tools()
            openai_tools = [mcp_tool_to_openai_tool(t) for t in mcp_tools.tools]
            print(f"Tools available: {[t.name for t in mcp_tools.tools]}")

            conversation = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that can query, answer questions on a Database.",
                }
            ]

            print("Type your queries or 'quit' to exit.")
            while True:
                try:
                    q = str(input('\nQuery> ')).strip()

                    if q.lower() == 'quit':
                        break

                    conversation.append({"role": "user", "content": q})

                    assistant_content = await query_agent(session, openai_tools, conversation)
                    print(f"Assistant: {assistant_content}\n")
                    print('---------------------------------------------\n')
                except Exception as e:
                    print(f'\n Error: {str(e)}')


if __name__ == "__main__":
    asyncio.run(chat_loop())