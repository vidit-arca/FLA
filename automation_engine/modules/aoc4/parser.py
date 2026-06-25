import json

class AOC4Parser:
    def __init__(self, config_path: str):
        self.config_path = config_path
        with open(config_path, "r") as f:
            self.config = json.load(f)

    def parse_all(self, docs: dict, ocr_outputs: dict) -> dict:
        print("[*] AOC 4 Parser initialized (Stub)")
        # TODO: Implement MCA specific parsing logic
        return {}
