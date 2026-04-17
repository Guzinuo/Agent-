import json


def load_json_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_inspection_framework():
    return load_json_file("framework/inspection_framework.json")


def load_issue_framework():
    return load_json_file("framework/issue_framework.json")