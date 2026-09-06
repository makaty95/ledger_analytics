import os
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
import mysql.connector


class ChatBot:
    def __init__(self,
                 db_name: str,
                 db_host: str,
                 db_port: int,
                 db_user: str,
                 db_password: str
                 ):
        # Initial vars
        self.conversation = None
        self.agent = None
        self.client = None
        self.tools = None
        self.model = None

        mcp_dir = os.path.dirname(os.path.abspath(__file__))
        server_path = Path(mcp_dir) / "mcp_server.py"
        print(f'evaluated path: {server_path}')

        # DB config to send to the mcp server
        # env variables holds the DB info which the user wanna connect to
        self.server_config = {
            'db_server': {
                'command': r'C:\Users\Makaty\PycharmProjects\openAI_mcp_course2026\.venv\Scripts\python.exe',
                'args': [str(server_path)],
                "transport": "stdio",
                "env": {
                    **os.environ,
                    "DB_NAME": f"{db_name}",
                    "DB_HOST": f"{db_host}",
                    "DB_PORT": f"{db_port}",
                    "DB_USER": f"{db_user}",
                    "DB_PASSWORD": f"{db_password}"
                }
            }
        }

        # Load environment vars
        load_dotenv()
        self.API_URL = os.getenv('API_URL')
        self.API_KEY = os.getenv('API_KEY')
        self.MODEL = os.getenv('MODEL')

        print(f'API_KEY: {self.API_KEY}')
        print(f'API_URL: {self.API_URL}')
        print(f'MODEL: {self.MODEL}')

    # Send messages to the AI agent
    async def query_agent(self, messages: list[dict]):
        response = await self.agent.ainvoke({
            "messages": messages
        })
        return response

    async def construct_agent(self):
        self.client = MultiServerMCPClient(self.server_config)
        self.tools = await self.client.get_tools()

        print(f"Tools available: {[t.name for t in self.tools]}")

        self.model = ChatOpenAI(
            model=self.MODEL,
            api_key=self.API_KEY,
            base_url=self.API_URL,
        )

        self.agent = create_agent(
            model=self.model,
            system_prompt="You are a helpful assistant that can query, answer questions on a Database.",
            tools=self.tools
        )

        self.conversation = []


class Utils:

    @classmethod
    def test_connection(cls,
                        db_name: str,
                        db_host: str,
                        db_port: int,
                        db_user: str,
                        db_password: str):
        success = False
        try:
            test_conn = mysql.connector.connect(
                host=db_host,
                user=db_user,
                password=db_password,
                database=db_name,
                port=db_port
            )
            if test_conn.is_connected():
                print(f'MySQL Connection successful')
                success = True
        except mysql.connector.Error as e:
            print(f'MySQL Connection test failed: {e}')
        finally:
            if 'test_conn' in locals() and test_conn.is_connected():
                test_conn.close()

        return success


class Context:
    chatbot = None

    db_name: str = None
    db_host: str = None
    db_port: int = None
    db_user: str = None
    db_password: str = None

    @classmethod
    def update_connection(cls,
                          db_name: str,
                          db_host: str,
                          db_port: int,
                          db_user: str,
                          db_password: str
                          ):
        cls.db_name: str = db_name
        cls.db_host: str = db_host
        cls.db_port: int = db_port
        cls.db_user: str = db_user
        cls.db_password: str = db_password

    @classmethod
    async def init_chatbot(cls):
        cls.chatbot = ChatBot(
            db_name=cls.db_name,
            db_host=cls.db_host,
            db_port=cls.db_port,
            db_user=cls.db_user,
            db_password=cls.db_password)

        await cls.chatbot.construct_agent()
