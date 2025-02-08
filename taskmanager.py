import requests
import os
import re
from datetime import datetime

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_TASK_PAGE_ID = os.getenv("NOTION_TASK_PAGE_ID")
NOTION_JOURNAL_PAGE_ID = os.getenv("NOTION_JOURNAL_PAGE_ID")

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
    tasks = response.json().get("results", [])

    task_dict = {}
    for task in tasks:
        name = task["properties"]["タスク名"]["title"][0]["text"]["content"]
        progress = task["properties"]["進捗"]["number"]
        expected_time = task["properties"]["想定時間"]["number"]
        task_dict[name] = {"id": task["id"], "progress": progress, "expected_time": expected_time}
    
    return task_dict

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
    content = get_notion_page_content(NOTION_TASK_PAGE_ID)
    tasks = parse_tasks_from_page(content)
    existing_tasks = get_database_tasks()
    
    
    for task in tasks:
        if task["name"] not in existing_tasks:
            add_task_to_database(task)

    
def get_journal_entries():
    url = f"https://api.notion.com/v1/blocks/{NOTION_JOURNAL_PAGE_ID}/children"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    blocks = response.json().get("results", [])

    today = datetime.today().strftime("%Y-%m-%d")
    tasks = {}
    current_task = None

    for block in blocks:
        if block["type"] == "heading_2":
            if today in block["heading_2"]["rich_text"][0]["text"]["content"]:
                current_task = None
        elif block["type"] == "heading_3" and current_task is None:
            current_task = block["heading_3"]["rich_text"][0]["text"]["content"]
            tasks[current_task] = {"time": 0, "progress": 0}
        elif block["type"] == "bulleted_list_item" and current_task:
            text = block["bulleted_list_item"]["rich_text"][0]["text"]["content"]
            if "本日の取り組み時間" in text:
                tasks[current_task]["time"] = int(text.split("：")[1].strip())
            elif "本日の進捗割合" in text:
                tasks[current_task]["progress"] = int(text.split("：")[1].strip().replace("%", ""))
    
    return tasks


def update_task_progress(task_id, progress, expected_time):
    url = f"https://api.notion.com/v1/pages/{task_id}"
    data = {
        "properties": {
            "進捗": {"number": progress},
            "想定時間": {"number": expected_time}
        }
    }
    response = requests.patch(url, headers=HEADERS, json=data)
    response.raise_for_status()

def process_journal_entries():
    journal_tasks = get_journal_entries()
    database_tasks = get_database_tasks()
    
    for task_name, entry in journal_tasks.items():
        if task_name in database_tasks:
            task = database_tasks[task_name]
            new_progress = entry["progress"]
            time_spent = entry["time"]
            remaining_progress = 100 - new_progress
            new_expected_time = (task["expected_time"] * remaining_progress / (100 - task["progress"])) if (100 - task["progress"]) > 0 else 0
            update_task_progress(task["id"], new_progress, new_expected_time)
            print(f"Updated {task_name}: Progress {new_progress}%, Expected Time {new_expected_time}h")


def main():
    # update_tasks()
    process_journal_entries()
    
if __name__ == "__main__":
    main()