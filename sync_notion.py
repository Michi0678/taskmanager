import requests
import os
import sys
import logging

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数の検証と取得
def get_required_env_vars():
    required_vars = {
        "NOTION_API_KEY": os.getenv("NOTION_API_KEY"),
        "NOTION_PAGE_ID": os.getenv("NOTION_PAGE_ID"),
        "NOTION_DATABASE_ID": os.getenv("NOTION_DATABASE_ID")
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
        
    return required_vars

# API設定
def get_headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

# ページ内のToDoリストを取得
def get_todo_list(page_id, headers):
    try:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        blocks = response.json().get("results", [])
        todo_items = {}

        for block in blocks:
            if block["type"] == "to_do":
                task_text = block["to_do"]["rich_text"][0]["text"]["content"]
                completed = block["to_do"]["checked"]
                todo_items[task_text] = completed

        logger.info(f"Successfully retrieved {len(todo_items)} todo items from page")
        return todo_items
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get todo list: {str(e)}")
        return {}

# データベースのタスクを取得
def get_database_tasks(database_id, headers):
    try:
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        response = requests.post(url, headers=headers, json={})
        response.raise_for_status()

        tasks = response.json()["results"]
        task_dict = {}

        for task in tasks:
            try:
                task_name = task["properties"]["Name"]["title"][0]["text"]["content"]
                task_dict[task_name] = task["id"]
            except (KeyError, IndexError) as e:
                logger.warning(f"Skipping malformed task: {str(e)}")
                continue

        logger.info(f"Successfully retrieved {len(task_dict)} tasks from database")
        return task_dict
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get database tasks: {str(e)}")
        return {}

# データベースにタスクを追加
def add_task_to_database(task_name, database_id, headers):
    try:
        url = "https://api.notion.com/v1/pages"
        data = {
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {"title": [{"text": {"content": task_name}}]}
            }
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"Successfully added task: {task_name}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to add task {task_name}: {str(e)}")
        return False

# データベースからタスクを削除
def delete_task_from_database(task_id, headers):
    try:
        url = f"https://api.notion.com/v1/pages/{task_id}"
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        logger.info(f"Successfully deleted task: {task_id}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to delete task {task_id}: {str(e)}")
        return False

# タスクを同期
def sync_tasks(page_id, database_id, headers):
    page_tasks = get_todo_list(page_id, headers)
    db_tasks = get_database_tasks(database_id, headers)

    sync_results = {
        "added": 0,
        "deleted": 0,
        "errors": 0
    }

    for task_name, completed in page_tasks.items():
        if task_name not in db_tasks and not completed:
            if add_task_to_database(task_name, database_id, headers):
                sync_results["added"] += 1
            else:
                sync_results["errors"] += 1

    for task_name, task_id in db_tasks.items():
        if task_name not in page_tasks:
            if delete_task_from_database(task_id, headers):
                sync_results["deleted"] += 1
            else:
                sync_results["errors"] += 1

    return sync_results

def main():
    try:
        env_vars = get_required_env_vars()
        headers = get_headers(env_vars["NOTION_API_KEY"])
        
        results = sync_tasks(
            env_vars["NOTION_PAGE_ID"],
            env_vars["NOTION_DATABASE_ID"],
            headers
        )
        
        logger.info(
            f"Sync completed - Added: {results['added']}, "
            f"Deleted: {results['deleted']}, "
            f"Errors: {results['errors']}"
        )
        
        if results["errors"] > 0:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()