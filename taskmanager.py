import requests
import os
import re
from datetime import datetime
# from dotenv import load_dotenv
# load_dotenv()

def get_notion_page_content(page_id, headers):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=headers)
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

def get_database_tasks(database_id, headers):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    response = requests.post(url, headers=headers, json={})
    response.raise_for_status()
    tasks = response.json().get("results", [])

    task_dict = {}
    for task in tasks:
        name = task["properties"]["タスク名"]["title"][0]["text"]["content"]
        progress = task["properties"]["進捗"]["number"]
        expected_time = task["properties"]["想定時間"]["number"]
        task_dict[name] = {"id": task["id"], "progress": progress, "expected_time": expected_time}
    
    return task_dict

def add_task_to_database(task, database_id, headers):
    url = "https://api.notion.com/v1/pages"
    data = {
        "parent": {"database_id": database_id},
        "properties": {
            "タスク名": {"title": [{"text": {"content": task["name"]}}]},
            "期限": {"date": {"start": task["deadline"]}},
            "進捗": {"number": 0},
            "想定時間": {"number": int(task["estimated_time"])}
        }
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

def update_tasks(task_page_id, database_id, headers):
    content = get_notion_page_content(task_page_id, headers)
    tasks = parse_tasks_from_page(content)
    existing_tasks = get_database_tasks(database_id, headers)
    
    for task in tasks:
        if task["name"] not in existing_tasks:
            add_task_to_database(task, database_id, headers)

def get_journal_entries(journal_page_id, headers):
    url = f"https://api.notion.com/v1/blocks/{journal_page_id}/children"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    blocks = response.json().get("results", [])

    today = datetime.today().strftime("%Y-%m-%d")
    tasks = {}
    current_task = None

    for block in blocks:
        if block["type"] == "heading_2":
            if today in block["heading_2"]["rich_text"][0]["text"]["content"]:
                current_task = None
        elif block["type"] == "heading_3":
            current_task = None
            current_task = block["heading_3"]["rich_text"][0]["text"]["content"]
            tasks[current_task] = {"time": 0, "progress": 0}
        elif block["type"] == "bulleted_list_item" and current_task:
            text = block["bulleted_list_item"]["rich_text"][0]["text"]["content"]
            if "本日の取り組み時間" in text:
                tasks[current_task]["time"] = int(text.split("：")[1].strip())
            elif "本日の進捗割合" in text:
                tasks[current_task]["progress"] = int(text.split("：")[1].strip().replace("%", ""))
    
    return tasks

def update_task_progress(task_id, progress, expected_time, headers):
    url = f"https://api.notion.com/v1/pages/{task_id}"
    data = {
        "properties": {
            "進捗": {"number": progress},
            "想定時間": {"number": expected_time}
        }
    }
    response = requests.patch(url, headers=headers, json=data)
    response.raise_for_status()

def process_journal_entries(journal_page_id, database_id, headers):
    journal_tasks = get_journal_entries(journal_page_id, headers)
    database_tasks = get_database_tasks(database_id, headers)
    
    for task_name, entry in journal_tasks.items():
        if task_name in database_tasks:
            task = database_tasks[task_name]
            new_progress = entry["progress"]
            time_spent = entry["time"]
            remaining_progress = 100 - new_progress
            new_expected_time = (task["expected_time"] * remaining_progress / (100 - task["progress"])) if (100 - task["progress"]) > 0 else 0
            update_task_progress(task["id"], new_progress, new_expected_time, headers)
            print(f"Updated {task_name}: Progress {new_progress}%, Expected Time {new_expected_time}h")
            
            
def delete_completed_tasks_from_database(database_id, headers):
    tasks = get_database_tasks(database_id, headers)
    for task_name, task in tasks.items():
        if task["progress"] == 100:
            url = f"https://api.notion.com/v1/pages/{task['id']}"
            data = {"archived": True}  # Notionでは削除ではなくアーカイブ
            response = requests.patch(url, headers=headers, json=data)
            response.raise_for_status()
            print(f"Archived completed task: {task_name}")



def strike_through_completed_tasks(task_page_id, completed_tasks, headers):
    content = get_notion_page_content(task_page_id, headers)
    
    in_block = False
    for block in content:
        block_id = block["id"]
        
        if block["type"] == "heading_3":
            task_name = block["heading_3"]["rich_text"][0]["text"]["content"]
            if task_name in completed_tasks:
                in_block = True
                updated_text = [{
                    "type": "text",
                    "text": {"content": task_name},
                    "annotations": {"bold": False, "italic": False, "strikethrough": True}
                }]
                update_notion_block_text(block_id, "heading_3", updated_text, headers)
            else:
                in_block = False

        elif block["type"] == "bulleted_list_item":
            if "rich_text" in block["bulleted_list_item"] and block["bulleted_list_item"]["rich_text"]:
                text = block["bulleted_list_item"]["rich_text"][0]["text"]["content"]
                if in_block:
                    updated_text = [{
                        "type": "text",
                        "text": {"content": text},
                        "annotations": {"bold": False, "italic": False, "strikethrough": True}
                    }]
                    update_notion_block_text(block_id, "bulleted_list_item", updated_text, headers)


def update_notion_block_text(block_id, block_type, updated_text, headers):
    """Notionのブロックテキストを更新する関数"""
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    data = {block_type: {"rich_text": updated_text}}  # block_type に応じて適切なキーを使用

    response = requests.patch(url, headers=headers, json=data)

    if response.status_code != 200:
        print(f"Error updating block {block_id}: {response.text}")
    response.raise_for_status()




def clean_up_completed_tasks(task_page_id, database_id, headers):
    tasks = get_database_tasks(database_id, headers)
    completed_tasks = [name for name, task in tasks.items() if task["progress"] == 100]
    
    if completed_tasks:
        strike_through_completed_tasks(task_page_id, completed_tasks, headers)
        delete_completed_tasks_from_database(database_id, headers)

        print("Cleanup completed for finished tasks.")


def main():
    notion_api_key = os.getenv("NOTION_API_KEY")
    notion_database_id = os.getenv("NOTION_DATABASE_ID")
    notion_task_page_id = os.getenv("NOTION_TASK_PAGE_ID")
    notion_journal_page_id = os.getenv("NOTION_JOURNAL_PAGE_ID")

    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    update_tasks(notion_task_page_id, notion_database_id, headers)
    process_journal_entries(notion_journal_page_id, notion_database_id, headers)
    clean_up_completed_tasks(notion_task_page_id, notion_database_id, headers)

if __name__ == "__main__":
    main()
