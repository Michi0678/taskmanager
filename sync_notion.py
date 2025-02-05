import requests
import os

# 環境変数から Notion API キーを取得
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
PAGE_ID = "your_page_id"  # NotionページのID
DATABASE_ID = "191bc67a34dc809eb521cfa9047e1131"  # NotionデータベースのID

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# ページ内のToDoリストを取得
def get_todo_list():
    url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print("❌ エラー: ページの取得に失敗")
        return []

    blocks = response.json().get("results", [])
    todo_items = {}

    for block in blocks:
        if block["type"] == "to_do":
            task_text = block["to_do"]["rich_text"][0]["text"]["content"]
            completed = block["to_do"]["checked"]
            todo_items[task_text] = completed

    return todo_items

# データベースのタスクを取得
def get_database_tasks():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    response = requests.post(url, headers=headers, json={})

    if response.status_code != 200:
        print("❌ データベースの取得に失敗")
        return {}

    tasks = response.json()["results"]
    task_dict = {}

    for task in tasks:
        task_name = task["properties"]["Name"]["title"][0]["text"]["content"]
        task_dict[task_name] = task["id"]

    return task_dict

# タスクを同期
def sync_tasks():
    page_tasks = get_todo_list()
    db_tasks = get_database_tasks()

    for task_name, completed in page_tasks.items():
        if task_name not in db_tasks and not completed:
            add_task_to_database(task_name)

    for task_name, task_id in db_tasks.items():
        if task_name not in page_tasks:
            delete_task_from_database(task_id)

# データベースにタスクを追加
def add_task_to_database(task_name):
    url = "https://api.notion.com/v1/pages"
    data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": task_name}}]}
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"✅ タスク追加成功: {task_name}")
    else:
        print(f"❌ タスク追加失敗: {task_name}")

# データベースからタスクを削除
def delete_task_from_database(task_id):
    url = f"https://api.notion.com/v1/pages/{task_id}"
    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        print(f"✅ タスク削除成功: {task_id}")
    else:
        print(f"❌ タスク削除失敗: {task_id}")

# 実行
if __name__ == "__main__":
    sync_tasks()
