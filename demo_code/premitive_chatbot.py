import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
import os

#########################################################################

# Load all env variables
load_dotenv()
API_URL = os.getenv('API_URL')
API_KEY = os.getenv('API_KEY')
MODEL = os.getenv('MODEL')

mcp_dir = os.path.dirname(os.path.abspath(__file__))
server_config = {
    'db_server': {
        'command': r'C:\Users\Makaty\PycharmProjects\openAI_mcp_course2026\.venv\Scripts\python.exe',
        'args': [os.path.join(mcp_dir, "mcp_server.py")],
        "transport": "stdio"
    }
}

# Send messages to the AI agent
async def query_agent(agent, messages):
    response = await agent.ainvoke({
        "messages": messages
    })
    return response

async def chat_loop():
    client = MultiServerMCPClient(server_config)
    tools = await client.get_tools()

    model = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=API_URL,
    )

    agent = create_agent(
        model=model,
        system_prompt="You are a helpful assistant that can query, answer questions on a Database.",
        tools=tools
    )

    conversation = []
    print('Type your queries or \'quite\' to exit.')
    while True:
        try:
            q = str(input('\nQuery> ')).strip()

            if q.lower() == 'quit':
                break

            message = {'role': 'user', 'content': q}
            conversation.append(message)

            reply = await query_agent(agent, conversation)
            assistant_content = reply["messages"][-1].content
            print(f"Assistant: {assistant_content}\n")
            conversation.append({"role": "assistant", "content": assistant_content})
            print('---------------------------------------------\n')
        except Exception as e:
            print(f'\n Error: {str(e)}')


if __name__ == "__main__":
    asyncio.run(chat_loop())