import os
import requests
from dotenv import load_dotenv


class RestconfClient:
    """Cliente HTTP reutilizable para las operaciones RESTCONF."""

    def __init__(self):
        load_dotenv(interpolate=False)
        host = os.getenv("ROUTER_HOST", "").strip()
        port = os.getenv("ROUTER_PORT", "443")
        username = os.getenv("ROUTER_USERNAME", "")
        password = os.getenv("ROUTER_PASSWORD", "")

        if not host or not username or not password:
            raise ValueError("Configura ROUTER_HOST, ROUTER_USERNAME y ROUTER_PASSWORD en .env")

        self.base_url = f"https://{host}:{port}/restconf/data"
        self.session = requests.Session()
        self.session.auth = (username, password)
        verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
        ca_bundle = os.getenv("ROUTER_CA_BUNDLE", "").strip()
        self.session.verify = (ca_bundle or True) if verify_ssl else False
        self.session.headers.update({
            "Accept": "application/yang-data+json",
            "Content-Type": "application/yang-data+json"
        })

    def request(self, method, endpoint, payload=None, params=None, headers=None):
        if method != "GET" and os.getenv("ALLOW_WRITES", "false").lower() != "true":
            raise ValueError("Escritura desactivada: configura ALLOW_WRITES=true en instancia autorizada")
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.request(
            method=method, url=url, json=payload,
            params=params, headers=headers, timeout=15, allow_redirects=False
        )
        if 300 <= response.status_code < 400:
            raise ValueError("Redireccion inesperada de RESTCONF")
        response.raise_for_status()
        return response

    def get(self, endpoint, params=None):
        return self.request("GET", endpoint, params=params).json()

    def post(self, endpoint, payload):
        return self.request("POST", endpoint, payload).status_code

    def patch(self, endpoint, payload):
        return self.request("PATCH", endpoint, payload).status_code

    def put(self, endpoint, payload):
        return self.request("PUT", endpoint, payload).status_code

    def delete(self, endpoint):
        return self.request("DELETE", endpoint).status_code

    def yang_patch(self, endpoint, payload):
        return self.request("PATCH", endpoint, payload, headers={"Content-Type": "application/yang-patch+json"}).status_code
