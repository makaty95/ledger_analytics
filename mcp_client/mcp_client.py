import json
import os
from contextlib import AsyncExitStack

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi import status
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
from pydantic import BaseModel, AnyUrl
from starlette.responses import JSONResponse

from services import Utils

load_dotenv()
API_URL = os.getenv('API_URL')
API_KEY = os.getenv('API_KEY')
MODEL = os.getenv('MODEL')

client = OpenAI(api_key=API_KEY, base_url=API_URL)

app = FastAPI()


class DatabaseConfig(BaseModel):
    db_name: str
    db_host: str
    db_port: int
    db_user: str
    db_password: str


class ChatRequest(BaseModel):
    message: str


class ResourceRequest(BaseModel):
    resource_uri: str


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


class Context:
    session: ClientSession | None = None
    exit_stack: AsyncExitStack | None = None
    openai_tools: list | None = None
    conversation: list | None = None


@app.post("/connect")
async def connect_db(config: DatabaseConfig):
    # Close previous connection if one exists
    if Context.exit_stack:
        await Context.exit_stack.aclose()

    valid_connection = Utils.test_connection(
        config.db_name,
        config.db_host,
        config.db_port,
        config.db_user,
        config.db_password)
    if not valid_connection:
        return JSONResponse(
            content={"success": 'False', 'Reason': 'Invalid DB connection'},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    server_params = StdioServerParameters(
        command=r"C:\Users\Makaty\PycharmProjects\openAI_mcp_course2026\.venv\Scripts\python.exe",
        args=[
            r"C:\Users\Makaty\PycharmProjects\openAI_mcp_course2026\mcp_server\mcp_server.py"
        ],
        env={
            **os.environ,
            "DB_NAME": config.db_name,
            "DB_HOST": config.db_host,
            "DB_PORT": str(config.db_port),
            "DB_USER": config.db_user,
            "DB_PASSWORD": config.db_password,
        }
    )

    # Keep the context managers alive
    Context.exit_stack = AsyncExitStack()

    read, write = await Context.exit_stack.enter_async_context(
        stdio_client(server_params)
    )

    Context.session = await Context.exit_stack.enter_async_context(
        ClientSession(read, write)
    )

    # Initialize MCP connection
    await Context.session.initialize()

    # Fetch all tools
    tools = await Context.session.list_tools()

    # Fetch all resources
    resources = await Context.session.list_resources()

    # Convert MCP tool schemas to OpenAI function-calling format, and
    # reset the conversation for this new connection
    Context.openai_tools = [mcp_tool_to_openai_tool(t) for t in tools.tools]
    Context.conversation = [
        {
            "role": "system",
            "content": (
                "You are a helpful analytics assistant. You can query a MySQL database "
                "using the available tools and analyze the returned data. "
                "Present your analysis on the results page using paragraphs and charts: "
                "use add_paragraph_block for written explanations and insights, and the "
                "appropriate add_*_chart_block tool for visualizing data (bar charts for "
                "comparing categories, line charts for trends over time, pie charts for "
                "proportions of a whole, scatter charts for relationships between two "
                "numeric variables). try to explain the charts you create by utilizing paragraphs. "
                "IMPORTANT: don't forget to call clear_results_page as your very first action whenever "
                "the user asks a new question that should produce a new report, before "
                "adding any new blocks. Do not skip this step. "
                "Only use real values returned by the database when creating charts — "
                "never invent or estimate data. "
                "Put your full analysis into the report using add_paragraph_block and the "
                "chart tools — be as thorough as the analysis genuinely requires there. "
                "However, keep your final chat reply to the user short "
                "since the detailed analysis is already visible in the report — just "
                "briefly acknowledge what you found or point out the key takeaway. "
                "Add blocks in the exact order they should appear on the page. "
                "Use clear, concise language suitable for a business analytics dashboard. "
                "Be efficient: avoid unnecessary back-and-forth so the user isn't left "
                "waiting."
            ),
        }
    ]

    return JSONResponse(
        content={
            "success": 'True',
            "tools": [tool.name for tool in tools.tools],
            "resources": [
                {
                    "uri": str(resource.uri),
                    "name": str(resource.name),
                    "description": str(resource.description)
                } for resource in resources.resources
            ],
        },
        status_code=status.HTTP_200_OK
    )


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


async def connect_testing_db():
    await connect_db(DatabaseConfig(
        db_name="learning_db",
        db_user="root",
        db_password="makaty",
        db_port=3306,
        db_host="localhost"
    ))


@app.post("/chat")
async def chat(request: ChatRequest):
    if Context.session is None:
        raise HTTPException(status_code=400, detail="Not connected to a database yet. Call /connect first.")

    Context.conversation.append({"role": "user", "content": request.message})

    reply = await query_agent(Context.session, Context.openai_tools, Context.conversation)

    return {"reply": reply}


async def query_resource(session: ClientSession, resource_uri: str) -> str:
    resource = await session.read_resource(AnyUrl(resource_uri))
    text = [
        content.text
        for content in resource.contents
        if hasattr(content, "text")
    ]

    return "\n".join(text)


@app.post("/resource")
async def get_resource(request: ResourceRequest):
    resource_uri = request.resource_uri
    if not resource_uri:
        return JSONResponse(
            content={"success": 'False', "Reason": "resource URI not specified"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    text = await query_resource(Context.session, resource_uri)
    print("Returned from query:\n")
    print(text)
    return JSONResponse(
        content={
            "success": True,
            "uri": resource_uri,
            "content": json.loads(text)
        },
        status_code=status.HTTP_302_FOUND
    )

@app.post("/disconnect")
async def disconnect():
    if Context.exit_stack:
        await Context.exit_stack.aclose()

    Context.session = None
    Context.exit_stack = None
    Context.openai_tools = None
    Context.conversation = None

    return {"success": True}


@app.get("/conversation")
async def get_conversation():
    if Context.conversation is None:
        return {"messages": []}
    # Filter out the system prompt. the frontend only needs user&assistant messages
    messages = [m for m in Context.conversation if m.get("role") in ("user", "assistant") and m.get("content")]
    return {"messages": messages}


@app.get("/health")
async def health():
    return {
        "connected": Context.session is not None
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
