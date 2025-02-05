import requests

NOTION_API_KEY = "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"  # 先ほどコピーしたAPIキー
DATABASE_ID = "191bc67a34dc809eb521cfa9047e1131"  # データベースのID

url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    print("✅ Notionデータベースに接続成功！")
    print(response.json())  # データベースの情報を表示
else:
    print("❌ エラー: Notionデータベースに接続できません")
    print(response.text)
