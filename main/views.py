import httpx
from django.shortcuts import render, redirect
from adrf.decorators import api_view
from django.template.loader import render_to_string
from rest_framework.response import Response
from rest_framework import status
import markdown
from django.utils.safestring import mark_safe

results_page = None
CLIENT_BASE_URL = "http://127.0.0.1:8080"

class DbConnectionStatus:
    db_connected = False
    host: str
    name: str

    @classmethod
    def update(cls, host: str, name: str):
        cls.host = host
        cls.name = name
        cls.db_connected = True


def render_ai_message_html(text: str) -> str:
    markdown_reply = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    return render_to_string(
        "partials/ui/_ai_message.html",
        {"response": {"message": mark_safe(markdown_reply)}},
    )



# Create your views here.
async def main_view(request):
    if not DbConnectionStatus.db_connected:
        return redirect('init_connection/')

    json = await fetch_page_results()
    content = json.get("content")
    blocks = content.get("content", [])
    title = content.get("title", "Untitled Report")

    with httpx.Client(timeout=None) as client:
        conversation_resp = client.get(f"{CLIENT_BASE_URL}/conversation")

    raw_messages  = conversation_resp.json().get("messages", []) if conversation_resp.status_code == 200 else []

    conversation = []
    for msg in raw_messages:
        role = msg.get("role")
        if role == "user":
            conversation.append({"role": "user", "text": msg["content"]})
        elif role == "assistant":
            conversation.append({"role": "assistant", "html": render_ai_message_html(msg["content"])})


    return render(
        request,
        'main_page.html',
        {
            "db_info": {
                "name": DbConnectionStatus.name,
                "host": DbConnectionStatus.host,
            },
            "title": title,
            "content": blocks,
            "conversation": conversation,
        }
    )


def init_connection(request):
    return render(request, "connect_page.html", {})


@api_view(['POST'])
async def connect_db(request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f'{CLIENT_BASE_URL}/connect',
            json = {
                "db_name": request.data.get('name'),
                "db_host": request.data.get('host'),
                "db_port": int(request.data.get('port')),
                "db_user": request.data.get('user'),
                "db_password": request.data.get('password'),
            }
        )

        if resp.status_code == 200:
            DbConnectionStatus.update(name=request.data.get('name'), host=request.data.get('host'))
            return Response(resp.json(), status=status.HTTP_200_OK)
        return Response({"error": resp.text}, status=status.HTTP_400_BAD_REQUEST)


# This endpoint will take a user query and return the whole rendered HTML
# for the AI chat message (includes the AI reply)
@api_view(['POST'])
async def chat(request):
    message = request.data.get('message')
    if not message:
        return Response({"error": "message is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(
                f"{CLIENT_BASE_URL}/chat",
                json={"message": message},
            )
    except httpx.RequestError as e:
        return Response({"error": f"Could not reach mcp client service: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

    if resp.status_code != 200:
        return Response({"error": resp.text}, status=resp.status_code)

    reply = resp.json().get("reply")
    ai_html = render_ai_message_html(reply)
    return Response({"ai_html": ai_html}, status=status.HTTP_200_OK)


async def fetch_page_results():
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(
                f"{CLIENT_BASE_URL}/resource",
                json={"resource_uri": "report://current"},
            )
    except httpx.RequestError as e:
        return Response({"error": f"Could not reach mcp client service: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

    return resp.json()



@api_view(['GET'])
async def results_page(request):
    json = await fetch_page_results()
    content = json.get("content")
    print(f"Content: \n{content}")

    blocks = content.get("content", [])
    title = content.get("title", "Untitled Report")

    html = render_to_string("partials/results/_results.html", {"content": blocks})
    print("HTML:\n", html)

    # Return both HTML snippet and structured content for Chart.js
    return Response({
        "title": title,
        "results_html": html,
        "content": blocks
    }, status=status.HTTP_200_OK)


async def disconnect(request):
    DbConnectionStatus.db_connected = False
    DbConnectionStatus.name = None
    DbConnectionStatus.host = None

    # Tell the FastAPI service to tear down its session too
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            await client.post(f"{CLIENT_BASE_URL}/disconnect")
        except httpx.RequestError:
            pass  # even if the MCP service is unreachable, still let the user proceed to reconnect

    return redirect('init_connection/')

