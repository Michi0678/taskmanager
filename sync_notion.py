import requests
import os
import sys
import logging
from datetime import datetime, timedelta

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数の取得
def get_env_vars():
    env_vars = {
        "NOTION_API_KEY": os.getenv("NOTION_API_KEY"),
        "NOTION_PAGE_ID": os.getenv("NOTION_PAGE_ID"),
        "NOTION_DATABASE_ID": os.getenv("NOTION_DATABASE_ID")
    }
    
    for key, value in env_vars.items():
        if not value:
            logger.error(f"環境変数が設定されていません: {key}")
            sys.exit(1)
    
    return env_vars

# Notion APIヘッダー
def get_headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

# NotionページからToDoリストを取得
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

        logger.info(f"ToDoリストを取得: {len(todo_items)} 件")
        return todo_items
    
    except requests.exceptions.RequestException as e:
        logger.error(f"ToDoリストの取得に失敗: {str(e)}")
        return {}

# データベースのタスク一覧を取得
def get_database_tasks(database_id, headers):
    try:
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        response = requests.post(url, headers=headers, json={})
        response.raise_for_status()
        
        tasks = response.json().get("results", [])
        task_dict = {}
        
        for task in tasks:
            try:
                task_name = task["properties"]["名前"]["title"][0]["text"]["content"]
                task_status = task["properties"]["ステータス"]["select"]["name"]
                task_dict[task_name] = {"id": task["id"], "status": task_status}
            except (KeyError, IndexError) as e:
                logger.warning(f"データベース内の無効なタスクをスキップ: {str(e)}")
                continue
        
        logger.info(f"データベース内のタスク取得: {len(task_dict)} 件")
        return task_dict
    
    except requests.exceptions.RequestException as e:
        logger.error(f"データベースの取得に失敗: {str(e)}")
        return {}

# データベースにタスクを追加
def add_task_to_database(task_name, database_id, headers):
    try:
        url = "https://api.notion.com/v1/pages"
        deadline = (datetime.utcnow() + timedelta(days=7)).isoformat()
        
        data = {
            "parent": {"database_id": database_id},
            "properties": {
                "名前": {"title": [{"text": {"content": task_name}}]},
                "期限": {"date": {"start": deadline}},
                "ステータス": {"status": {"equals": "未着手"}},
                "説明": {"rich_text": [{"text": {"content": "自動追加されたタスク"}}]}
            }
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"タスク追加成功: {task_name}")
        return True
    
    except requests.exceptions.RequestException as e:
        logger.error(f"タスク追加失敗 {task_name}: {str(e)}")
        return False

# データベースからタスクを削除
def delete_task_from_database(task_id, headers):
    try:
        url = f"https://api.notion.com/v1/pages/{task_id}"
        response = requests.patch(url, headers=headers, json={"archived": True})
        response.raise_for_status()
        logger.info(f"タスク削除成功: {task_id}")
        return True
    
    except requests.exceptions.RequestException as e:
        logger.error(f"タスク削除失敗 {task_id}: {str(e)}")
        return False

# タスクを同期
def sync_tasks(page_id, database_id, headers):
    page_tasks = get_todo_list(page_id, headers)
    db_tasks = get_database_tasks(database_id, headers)
    
    sync_results = {"added": 0, "deleted": 0, "errors": 0}

    for task_name, completed in page_tasks.items():
        if task_name not in db_tasks and not completed:
            if add_task_to_database(task_name, database_id, headers):
                sync_results["added"] += 1
            else:
                sync_results["errors"] += 1

    for task_name, task_data in db_tasks.items():
        if task_name not in page_tasks and task_data["status"] == "完了":
            if delete_task_from_database(task_data["id"], headers):
                sync_results["deleted"] += 1
            else:
                sync_results["errors"] += 1
    
    return sync_results


# メイン処理
def main():
    try:
        env_vars = get_env_vars()
        headers = get_headers(env_vars["NOTION_API_KEY"])
        
        results = sync_tasks(
            env_vars["NOTION_PAGE_ID"],
            env_vars["NOTION_DATABASE_ID"],
            headers
        )
        
        logger.info(f"同期完了 - 追加: {results['added']}, 削除: {results['deleted']}, エラー: {results['errors']}")
        if results["errors"] > 0:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
