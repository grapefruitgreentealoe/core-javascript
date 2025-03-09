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
    """ Notion 페이지를 Markdown으로 변환 (모든 블록 타입 지원) """
    title = page["properties"]["Name"]["title"]
    title_text = title[0]["plain_text"] if title else "Untitled"

    content_blocks = notion.blocks.children.list(block_id=page["id"])["results"]
    markdown_content = f"# {title_text}\n\n"

    for block in content_blocks:
        block_type = block["type"]
        text = block[block_type].get("rich_text", [])
        
        if not text:  
            markdown_content += "\n"  # 빈 블록 처리
            continue  

        text_content = text[0]["plain_text"]

        # 📌 블록 타입별 Markdown 변환
        if block_type == "paragraph":
            markdown_content += text_content + "\n\n"
        elif block_type == "heading_1":
            markdown_content += f"# {text_content}\n\n"
        elif block_type == "heading_2":
            markdown_content += f"## {text_content}\n\n"
        elif block_type == "heading_3":
            markdown_content += f"### {text_content}\n\n"
        elif block_type == "bulleted_list_item":  # 🔹 리스트 아이템 처리
            markdown_content += f"- {text_content}\n"
        elif block_type == "numbered_list_item":  # 🔹 번호 리스트 처리
            markdown_content += f"1. {text_content}\n"
        elif block_type == "quote":  # 🔹 인용 블록 처리
            markdown_content += f"> {text_content}\n\n"
        elif block_type == "code":  # 🔹 코드 블록 처리
            language = block["code"].get("language", "plaintext")
            markdown_content += f"```{language}\n{text_content}\n```\n\n"

    return title_text, markdown_content

def save_markdown_files():
    """ 노션 데이터를 Markdown 파일로 저장하고 커밋 메시지 생성 """
    pages = fetch_notion_pages()
    commit_messages = []

    #  폴더가 없으면 자동 생성

    os.makedirs("blog", exist_ok=True)


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
