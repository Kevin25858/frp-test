"""HTTP handlers for FRP Monitor web interface"""

from aiohttp import web


class WebHandlers:
    def __init__(self, server_instance):
        self.server = server_instance

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def handle_clients(self, request: web.Request) -> web.Response:
        return web.json_response(self.server.get_clients())

    async def handle_client_detail(self, request: web.Request) -> web.Response:
        name = request.match_info["name"]
        client = self.server.get_client(name)
        if client:
            return web.json_response(client)
        return web.json_response({"error": "not found"}, status=404)

    async def handle_metrics(self, request: web.Request) -> web.Response:
        name = request.match_info["name"]
        hours = int(request.query.get("hours", 1))
        return web.json_response(self.server.get_metrics(name, hours))
