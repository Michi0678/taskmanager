import requests
import os
import re
from datetime import datetime

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def get_notion_page_content(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()["results"]

def parse_tasks_from_page(content):
    tasks = []
    current_task = None
    
    for block in content:
        if block["type"] == "heading_3":
            if current_task:
                tasks.append(current_task)
            current_task = {"name": block["heading_3"]["rich_text"][0]["text"]["content"]}
        elif block["type"] == "bulleted_list_item" and current_task:
            text = block["bulleted_list_item"]["rich_text"][0]["text"]["content"]
            if text.startswith("期限："):
                current_task["deadline"] = text.replace("期限：", "").strip()
            elif text.startswith("想定時間："):
                current_task["estimated_time"] = text.replace("想定時間：", "").strip()
    
    if current_task:
        tasks.append(current_task)
    
    return tasks

def get_database_tasks():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    response = requests.post(url, headers=HEADERS, json={})
    response.raise_for_status()
    tasks = {task["properties"]["Name"]["title"][0]["text"]["content"]: task["id"] for task in response.json()["results"]}
    return tasks

def add_task_to_database(task):
    url = "https://api.notion.com/v1/pages"
    data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "タスク名": {"title": [{"text": {"content": task["name"]}}]},
            "期限": {"date": {"start": task.get("deadline", "")}},
            "進捗": {"number": 0},
            "想定時間": {"number": int(task.get("estimated_time", 0))}
        }
    }
    response = requests.post(url, headers=HEADERS, json=data)
    response.raise_for_status()

def update_tasks():
    content = get_notion_page_content(NOTION_PAGE_ID)
    tasks = parse_tasks_from_page(content)
    existing_tasks = get_database_tasks()
    
    for task in tasks:
        if task["name"] not in existing_tasks:
            add_task_to_database(task)

def main():
    update_tasks()
    print("Tasks updated successfully")

if __name__ == "__main__":
    main()
