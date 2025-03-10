import os
import re
from datetime import datetime, timedelta, timezone
from notion_client import Client

# 환경 변수로 로컬 실행인지 확인 (기본은 False로 두기)
IS_LOCAL = os.getenv("IS_LOCAL", "false").lower() == "true"

if IS_LOCAL:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ [로컬 실행] .env 파일 로드 완료")
else:
    print("🚀 [CI/CD 실행] .env 파일 무시, 환경변수 직접 사용")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
notion = Client(auth=NOTION_API_KEY)

# ✅ 마지막 실행 시간 기록 파일
LAST_UPDATED_FILE = "last_updated.txt"


# ✅ 마지막 실행 시간 읽기
def read_last_run_time():
    try:
        with open(LAST_UPDATED_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "2000-01-01T00:00:00.000+09:00"  # 기본값 KST



# ✅ 현재 시간 기록 (작업 끝난 후 호출)
def write_current_run_time():
    KST = timezone(timedelta(hours=9))  # ✅ +9시간 timezone 정의
    now = datetime.now(KST)  # KST 기준 시간
    now_kst = now.isoformat(timespec='milliseconds')  # 밀리초 포함
    with open(LAST_UPDATED_FILE, "w") as f:
        f.write(now_kst)


# ✅ 최근 수정된 페이지만 가져오기
def fetch_recent_notion_pages(last_run_time):
    response = notion.databases.query(
        database_id=DATABASE_ID,
        filter={
        "timestamp": "last_edited_time",  # 어떤 시간인지 명시
        "last_edited_time": {
            "on_or_after": last_run_time  # 기준 시간 이후
            }
        }
    )
    return response["results"]




# ✅ Notion 데이터베이스에서 페이지 목록 가져오기 (상단 이동)
def fetch_notion_pages():
    response = notion.databases.query(database_id=DATABASE_ID)
    return response["results"]

# ✅ Rich text 변환
def parse_rich_text(rich_text):
    return "".join([part.get("plain_text", "") for part in rich_text]) if rich_text else ""



# ✅ 하위 블록 재귀 파싱
def parse_children(block_id, indent=0):
    children = notion.blocks.children.list(block_id=block_id)["results"]
    content = ""
    for child in children:
        content += parse_block(child, indent)
    return content


# ✅ 블록 재귀 파싱 (중첩 리스트, 토글, 컬럼 등 대응)
def parse_block(block, indent=0):
    block_type = block["type"]
    text = parse_rich_text(block[block_type].get("rich_text", []))
    space = "  " * indent  # 들여쓰기
    markdown = ""

    # ✅ 기본 블록 변환
    if block_type == "paragraph":
        markdown += f"{space}{text}\n\n"
    elif block_type == "heading_1":
        markdown += f"{space}# {text}\n\n"
    elif block_type == "heading_2":
        markdown += f"{space}## {text}\n\n"
    elif block_type == "heading_3":
        markdown += f"{space}### {text}\n\n"
    elif block_type == "bulleted_list_item":
        markdown += f"{space}- {text}\n"
    elif block_type == "numbered_list_item":
        markdown += f"{space}1. {text}\n"
    elif block_type == "to_do":
        checked = block["to_do"]["checked"]
        markdown += f"{space}- [{'x' if checked else ' '}] {text}\n"
    elif block_type == "quote":
        markdown += f"{space}> {text}\n\n"
    elif block_type == "code":
        language = block["code"].get("language", "plaintext")
        markdown += f"{space}```{language}\n{text}\n```\n\n"
    elif block_type == "divider":
        markdown += f"{space}---\n\n"
    elif block_type == "callout":
        markdown += f"{space}> 💡 {text}\n\n"
    elif block_type == "image":
        url = block["image"]["file"]["url"] if block["image"]["type"] == "file" else block["image"]["external"]["url"]
        markdown += f"{space}![image]({url})\n\n"
    elif block_type == "file":
        url = block["file"]["url"]
        markdown += f"{space}[File]({url})\n\n"
    elif block_type == "synced_block":
        markdown += f"{space}> **Synced Block:**\n\n"
        markdown += parse_children(block["id"], indent + 1)
    elif block_type == "toggle":
        toggle_content = parse_children(block["id"], indent + 1)
        markdown += f"{space}<details>\n{space}<summary>{text}</summary>\n\n{toggle_content}\n{space}</details>\n\n"
    elif block_type == "column_list":
        markdown += f"{space}**Column List:**\n\n"
        markdown += parse_children(block["id"], indent + 1)
    elif block_type == "column":
        markdown += f"{space}**Column:**\n\n"
        markdown += parse_children(block["id"], indent + 1)
    elif block_type == "child_page":
        page_title = parse_rich_text(block["child_page"].get("title", ""))
        markdown += f"{space}[Page: {page_title}]\n\n"
    elif block_type == "child_database":
         markdown += parse_database_table(block, indent)
    elif block_type == "table":
        markdown += parse_table(block, indent)  # ✅ 테이블 블록 처리
    elif block_type == "table_row":
        return ""  # 테이블 안에서만 처리, 개별로는 무시
    else:
        markdown += f"{space}**[Unsupported block: {block_type}]**\n\n"

    # ✅ 하위 블록이 있다면 재귀
    if block.get("has_children"):
        markdown += parse_children(block["id"], indent + 1)

    return markdown

def parse_database_table(block, indent=0):
    space = "  " * indent
    markdown = ""

    # 데이터베이스 ID
    database_id = block['id']
    print(f"📊 데이터베이스 ID: {database_id}")

    # 데이터 조회
    rows = notion.databases.query(database_id=database_id)["results"]
    if not rows:
        return f"{space}**[Empty Database Table]**\n\n"

    # 헤더 가져오기
    headers = list(rows[0]['properties'].keys())
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    markdown += header_line + "\n" + separator_line + "\n"

    # 데이터 파싱
    for row in rows:
        row_data = []
        for key in headers:
            value = extract_text_from_property(row['properties'][key])
            row_data.append(value)
        row_line = "| " + " | ".join(row_data) + " |"
        markdown += row_line + "\n"

    return markdown + "\n"

def extract_text_from_property(prop):
    prop_type = prop['type']
    if prop_type in ['title', 'rich_text']:
        texts = prop[prop_type]
        return "".join([t['plain_text'] for t in texts]) if texts else ""
    elif prop_type == 'number':
        return str(prop['number']) if prop['number'] is not None else ""
    elif prop_type == 'select':
        return prop['select']['name'] if prop['select'] else ""
    elif prop_type == 'multi_select':
        return ", ".join([opt['name'] for opt in prop['multi_select']]) if prop['multi_select'] else ""
    elif prop_type == 'checkbox':
        return '✅' if prop['checkbox'] else '❌'
    else:
        return "..."


def parse_table(block, indent=0):
    space = "  " * indent
    markdown = ""
    
    # 테이블 내부의 row 가져오기
    rows = notion.blocks.children.list(block_id=block["id"])["results"]
    
    if not rows:
        return f"{space}**[Empty Table]**\n\n"
    
    table_markdown = []

    # rows 돌면서 각 셀 데이터 파싱
    for i, row in enumerate(rows):
        if row["type"] != "table_row":
            continue  # table_row가 아닌 경우 무시
        
        cells = row["table_row"]["cells"]
        cell_texts = [parse_rich_text(cell) for cell in cells]
        
        # Markdown 테이블 라인 만들기
        line = "| " + " | ".join(cell_texts) + " |"
        table_markdown.append(line)
        
        # 두 번째 줄에 구분선 추가 (헤더 구분)
        if i == 0:
            separator = "| " + " | ".join(["---"] * len(cells)) + " |"
            table_markdown.append(separator)

    # 테이블 완성
    markdown += "\n".join(table_markdown) + "\n\n"
    return markdown


# ✅ 페이지를 Markdown으로 변환
def notion_to_markdown(page):
    title = page["properties"]["Name"]["title"]
    title_text = title[0]["plain_text"] if title else "Untitled"

    print(f"🔍 변환 중: {title_text}")

    content_blocks = notion.blocks.children.list(block_id=page["id"])["results"]
    markdown_content = f"# {title_text}\n\n"

    for block in content_blocks:
        markdown_content += parse_block(block)

    return title_text, markdown_content


def save_markdown_files(pages):
    """ 노션 데이터를 Markdown 파일로 저장하고 커밋 메시지 생성 """
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

def update_readme():
    blog_dir = "blog"
    readme_path = "README.md"

    # blog 폴더 안 모든 .md 파일 가져오기
    md_files = [f for f in os.listdir(blog_dir) if f.endswith(".md")]
    
    # 파일명 정렬
    md_files.sort()

    # README.md 내용 시작
    readme_content = "# 📚 블로그 목록\n\n"

    # 파일 목록 추가
    for file in md_files:
        # 확장자 제거하고 제목 만들기
        title = os.path.splitext(file)[0].replace("_", " ")
        # 링크로 연결
        readme_content += f"- [{title}](blog/{file})\n"

    # 파일 저장
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("✅ README.md 업데이트 완료!")


if __name__ == "__main__":
    last_run_time = read_last_run_time()
    print(f"🕒 마지막 실행 시간: {last_run_time}")

    pages = fetch_recent_notion_pages(last_run_time)

    if pages:
        print(f"✅ {len(pages)}개의 글이 업데이트됨. 변환 시작!")
        save_markdown_files(pages)
        update_readme()
    else:
        print("⚠️ 새로운 업데이트가 없습니다.")

    write_current_run_time()

