import os
from dataclasses import dataclass, field


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.get_peer_url = os.path.join(base_url, "peers")
        self.add_tracker_url = os.path.join(base_url, "add")

    def get_peers(self, domain: str, page: str):
        filepath = os.path.join(domain, page)
        res = requests.get(self.get_peer_url + f"?filename={filepath}")
        return res

    def add_tracker(self, path: str, name: str, hash:str):
        filepath = os.path.join(path, name)
        res = requests.get(self.add_tracker_url + f"?filename={filepath}&hash={hash}")
        return res

