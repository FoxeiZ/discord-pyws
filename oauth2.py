import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from time import sleep
from typing import Callable, Literal, Optional, Union
from urllib import parse

import httpx

endpoints_mapping: dict[str, dict[str, Callable]] = {
    "CONNECT": {},
    "DELETE": {},
    "GET": {},
    "HEAD": {},
    "OPTIONS": {},
    "PATCH": {},
    "POST": {},
    "PUT": {},
    "TRACE": {},
}


def endpoint(url=None, method="GET"):
    def decorator(func):
        endpoints_mapping[method][url if url else f"/{func.__name__}"] = func
        return func

    return decorator


def generate_uri(
    client_id: int,
    redirect_url: str,
    scope: Union[str, list[str]],
    state: Optional[str] = None,
    skip_prompt: Optional[bool] = False,
    response_type: Optional[Literal["code", "token"]] = "code",
    guild_id: Optional[Union[int, str]] = None,
    disable_guild_select: Optional[bool] = None,
    permissions: Optional[Union[int, str]] = None,
) -> str:
    params = {
        "client_id": client_id,
        "scope": " ".join(scope) if isinstance(scope, list) else scope,
        "state": state,
        "redirect_uri": redirect_url,
        "prompt": "none" if skip_prompt else None,
        "response_type": response_type,
        "guild_id": guild_id,
        "disable_guild_select": disable_guild_select,
        "permissions": permissions,
    }
    return f"https://discord.com/oauth2/authorize?{parse.urlencode({key: value for key, value in params.items() if value is not None})}"


def exchange_code(
    client_id: int, client_secret: str, redirect_url: str, code: str
) -> dict:
    response = httpx.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_url,
        },
    )

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 400:
        return {
            "error": "invalid_grant",
            "error_description": "the code, client id, client secret or the redirect uri is invalid/don't match.",
        }
    elif response.status_code == 429:
        return {
            "error": "rate_limit",
            "error_description": f"You are being Rate Limited. Retry after: {response.json()['retry_after']}",
        }
    else:
        return {
            "error": "unknown",
            "error_description": f"Unexpected HTTP {response.status_code}",
        }


class MyServer(BaseHTTPRequestHandler):
    args: dict | list | None

    @staticmethod
    def encode(data):
        return bytes(data, "utf-8")

    def default_get_method(self):
        self.send_response(200)
        self.send_header("cache-control", "no-cache")
        self.end_headers()
        self.wfile.write(self.encode("Hello, World!"))

    def send_404(self):
        self.send_response(404)
        self.send_header("cache-control", "no-cache")
        self.end_headers()
        self.wfile.write(self.encode(f"'{self.path}' Not Found"))

    def do_GET(self):
        get_mapping = endpoints_mapping["GET"]
        if not get_mapping:
            return self.default_get_method()

        parse_get = parse.urlparse(self.path)
        self.args = parse.parse_qs(parse_get.query)

        if parse_get.path in get_mapping:
            return get_mapping[parse_get.path](self)

        return self.send_404()

    def default_post_method(self):
        self.send_response(200)
        self.send_header("accept-ranges", "bytes")
        self.end_headers()
        self.wfile.write(b"POST request received")

    def do_POST(self):
        post_endpoint = endpoints_mapping["POST"]
        if not post_endpoint:
            return self.default_post_method()

        if self.path in post_endpoint:
            return post_endpoint[self.path](self)

        return self.send_404()

    def default_options_method(self):
        allow_methods = [k for k, v in endpoints_mapping.items() if v]
        allow_methods.extend(
            method
            for method in ["GET", "POST", "OPTIONS"]
            if method not in allow_methods
        )
        self.send_response(204)
        self.send_header("Allow", ", ".join(allow_methods))
        self.send_header("cache-control", "no-cache")
        self.end_headers()

    def do_OPTIONS(self):
        options_endpoint = endpoints_mapping["OPTIONS"]
        if self.path in options_endpoint:
            return options_endpoint[self.path](self)

        return self.default_options_method()

    def redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()


@endpoint("/")
def index_handler(server: MyServer):
    return server.redirect(
        generate_uri(750352128479985816, "http://localhost:8080/oauth2", "identify")
    )


@endpoint("/oauth2")
def oauth2_handler(server: MyServer):
    if not server.args:
        return

    if not server.args.get("code"):  # type: ignore
        return server.redirect(
            generate_uri(
                750352128479985816,
                "http://localhost:8080/oauth2",
                ["identify", "rpc.activities.write"],
            )
        )

    code: str = server.args.get("code")  # type: ignore
    server.send_response(200)
    server.send_header("cache-control", "no-cache")
    server.send_header("Content-Type", "application/json")
    server.end_headers()
    server.wfile.write(
        server.encode(
            json.dumps(
                exchange_code(
                    750352128479985816,
                    "",
                    "http://localhost:8080/oauth2",
                    code,
                )
            )
        )
    )


if __name__ == "__main__":
    hostName = "localhost"
    serverPort = 8080

    webServer = HTTPServer((hostName, serverPort), MyServer)
    thrd_server = Thread(target=webServer.serve_forever, daemon=True)
    print("Server started http://%s:%s" % (hostName, serverPort))

    thrd_server.start()

    try:
        while True:
            sleep(120)
    except KeyboardInterrupt:
        webServer.shutdown()
    finally:
        thrd_server.join()
