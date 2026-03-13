import httpx

original_client = httpx.Client
original_client_async = httpx.AsyncClient


class NoProxyClient(original_client):
    def __init__(self, *args, **kwargs):
        kwargs['verify'] = False
        super().__init__(*args, **kwargs)

    def _get_proxy_map(
            self, proxies, allow_env_proxies: bool
    ):
        return {}

class NoProxyClientAsync(original_client_async):
    def __init__(self, *args, **kwargs):
        kwargs['verify'] = False
        super().__init__(*args, **kwargs)

    def _get_proxy_map(
            self, proxies, allow_env_proxies: bool
    ):
        return {}

httpx.Client = NoProxyClient
httpx.AsyncClient = NoProxyClientAsync

