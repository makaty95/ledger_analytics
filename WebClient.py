import json
import urllib.request
import urllib.error


class WebClient:

    def __init__(self, model: str, api_url: str, api_key: str):
        self.model = model
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        print('API_KEY:', api_key)



    def send_messages(self, messages: dict, method: str):
        payload = json.dumps(
            {
                'model': self.model,
                'messages': messages
            }
        ).encode('utf-8')

        req = urllib.request.Request(
            self.api_url,
            data=payload,
            method=method,
            headers=self.headers
        )

        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            return f"[HTTP {e.code} error] {err_body}"
        except urllib.error.URLError as e:
            return f"[Connection error] {e.reason}"
        except (KeyError, json.JSONDecodeError) as e:
            return f"[Unexpected response format] {e}"




