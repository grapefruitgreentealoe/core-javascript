import os
import requests
import markdownify
from notion_client import Client

# Notion API 설정
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_API_KEY)

def fetch_notion_pages():
    """ 노션 데이터베이스에서 페이지 목록 가져오기 """
    response = notion.databases.query(database_id=DATABASE_ID)
    return response["results"]

def notion_to_markdown(page):
    """ 노션 페이지를 Markdown으로 변환 """
    title = page["properties"]["Name"]["title"][0]["plain_text"]
    content_blocks = notion.blocks.children.list(block_id=page["id"])["results"]
    
    markdown_content = f"# {title}\n\n"
    
    for block in content_blocks:
        if block["type"] == "paragraph":
            markdown_content += block["paragraph"]["rich_text"][0]["plain_text"] + "\n\n"
        elif block["type"] == "heading_1":
            markdown_content += f"# {block['heading_1']['rich_text'][0]['plain_text']}\n\n"
        elif block["type"] == "heading_2":
            markdown_content += f"## {block['heading_2']['rich_text'][0]['plain_text']}\n\n"
        elif block["type"] == "heading_3":
            markdown_content += f"### {block['heading_3']['rich_text'][0]['plain_text']}\n\n"

    return title, markdown_content

def save_markdown_files():
    """ 노션 데이터를 Markdown 파일로 저장하고 커밋 메시지 생성 """
    pages = fetch_notion_pages()
    commit_messages = []

    for page in pages:
        title, content = notion_to_markdown(page)
        filename = f"blog/{title.replace(' ', '_')}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        
        commit_messages.append(f"Updated: {title}")  # 커밋 메시지로 사용

    # 커밋 메시지를 저장
    with open("commit_messages.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(commit_messages))

    print("✅ Markdown 변환 완료! 커밋 메시지 저장 완료!")

if __name__ == "__main__":
    save_markdown_files()
