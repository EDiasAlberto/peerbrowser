import os
import requests
from dataclasses import dataclass, field


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.get_peer_url = os.path.join(base_url, "peers")
        self.add_tracker_url = os.path.join(base_url, "add")
        self.remove_tracker_url = os.path.join(base_url, "remove")

    def get_peers(self, filepath: str):
        res = requests.get(self.get_peer_url + f"?filename={filepath}")
        return res

    def add_tracker(self, filepath: str, hash: str):
        res = requests.get(self.add_tracker_url + f"?filename={filepath}&hash={hash}")
        return res

    def remove_tracker(self, ip: str, filepath):
        res = requests.get(self.remove_tracker_url + f"?ip={ip}&filename={filepath}")
        return res

