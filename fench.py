import aiohttp
import asyncio
import os
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from notion_client import Client

# 获取当前日期
def get_date():
    return datetime.now().strftime("%Y%m%d")

# 当前日期
DATE = get_date()
DATE = '20241227'

# 文件路径
NEWS_PATH = os.path.join(os.getcwd(), 'news')
NEWS_MD_PATH = os.path.join(NEWS_PATH, f'{DATE}.md')
README_PATH = os.path.join(os.getcwd(), 'README.md')
CATALOGUE_JSON_PATH = os.path.join(NEWS_PATH, 'catalogue.json')

# 确保文件夹存在
os.makedirs(NEWS_PATH, exist_ok=True)

# 打印调试信息
print('DATE:', DATE)
print('NEWS_PATH:', NEWS_PATH)
print('README_PATH:', README_PATH)
print('CATALOGUE_JSON_PATH:', CATALOGUE_JSON_PATH)

#设置notion
NOTION_API_TOKEN = "MyNotionToken"
DATABASE_ID = "MyPageId"

# 初始化 Notion 客户端
notion = Client(auth=NOTION_API_TOKEN)

# 异步请求函数
async def fetch(url, session):
    async with session.get(url) as response:
        return await response.text()

# 获取新闻列表
async def get_news_list(date, session):
    url = f'http://tv.cctv.com/lm/xwlb/day/{date}.shtml'
    html = await fetch(url, session)
    soup = BeautifulSoup(html, 'html.parser')
    
    links = []
    for a in soup.find_all('a', href=True):
        link = a['href']
        if link not in links:
            links.append(link)
    
    abstract = links.pop(0)  # 第一个链接作为新闻摘要
    print('成功获取新闻列表')
    return {
        'abstract': abstract,
        'news': links
    }

# 获取新闻摘要
async def get_abstract(link, session):
    html = await fetch(link, session)
    soup = BeautifulSoup(html, 'html.parser')
    abstract = soup.select_one('#page_body > div.allcontent > div.video18847 > div.playingCon > div.nrjianjie_shadow > div > ul > li:nth-child(1) > p')
    if abstract:
        return abstract.get_text().replace('；', '；\n\n').replace('：', '：\n\n')
    return ''

# HTML到Markdown的转换
def html_to_markdown(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 替换 <strong> 标签为 Markdown 加粗
    for strong in soup.find_all('strong'):
        strong.string = f"**{strong.get_text(strip=True)}**"

    markdown = ""
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        markdown += f"{text}\n\n"
    return markdown.strip()

# 获取单条新闻内容
async def get_single_news(link, session):
    html = await fetch(link, session)
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('#page_body > div.allcontent > div.video18847 > div.playingVideo > div.tit')
    content = soup.select_one('#content_area')
    return {
        'title': title.get_text().replace('[视频]', '').strip() if title else None,
        'content': html_to_markdown(content.prettify()) if content else None,
    }

# 获取新闻内容
async def get_news(links, session):
    tasks = [get_single_news(link, session) for link in links]
    news = await asyncio.gather(*tasks)
    print('成功获取所有新闻')
    return news

# 将数据处理为Markdown格式
def news_to_markdown(date, abstract, news, links):
    md_news = ''
    for i, item in enumerate(news):
        title = item['title']
        content = item['content']
        link = links[i]
        md_news += f'### {title}\n\n{content}\n\n[查看原文]({link})\n\n'
    
    return f'# 《新闻联播》 ({date})\n\n## 新闻摘要\n\n{abstract}\n\n## 详细新闻\n\n{md_news}\n\n---\n\n(更新时间戳: {int(datetime.now().timestamp())})\n\n'

# 保存文本到文件
def save_text_to_file(save_path, text):
    with open(save_path, 'w', encoding='utf-8') as file:
        file.write(text)

# 更新目录
def update_catalogue(catalogue_json_path, readme_md_path, date, abstract):
    # 更新 catalogue.json
    if os.path.exists(catalogue_json_path):
        with open(catalogue_json_path, 'r', encoding='utf-8') as file:
            catalogue_json = json.load(file)
    else:
        catalogue_json = []

    catalogue_json.insert(0, {
        'date': date,
        'abstract': abstract,
    })
    
    with open(catalogue_json_path, 'w', encoding='utf-8') as file:
        json.dump(catalogue_json, file, ensure_ascii=False, indent=2)
    
    print('更新 catalogue.json 完成')
    
    # 更新 README.md
    with open(readme_md_path, 'r', encoding='utf-8') as file:
        readme_content = file.read()
    
    new_entry = f'- [{date}](./news/{date}.md)\n'
    updated_content = readme_content.replace('<!-- INSERT -->', f'<!-- INSERT -->\n{new_entry}')
    
    with open(readme_md_path, 'w', encoding='utf-8') as file:
        file.write(updated_content)
    
    print('更新 README.md 完成')


#添加notion页面
def create_news_page(content):
    
    # Split content into lines and filter empty lines
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    
    # Prepare the blocks for the page
    blocks = []
    for line in lines:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": line}}]
            },
        })
    
    try:
        page = notion.pages.create(
            parent={
                "type": "page_id",
                "page_id": DATABASE_ID
            },
            properties={
                "title":[
                    {
                        "type": "text",
                        "text": {
                            "content": DATE
                        }
                    }
                ]
            },
            children=blocks
        )
        print('创建notion摘要完成')
    except Exception as e:
        print(f"创建页面失败：{e}") 
    return page

#在创建的页面中追加内容
def update_news_page(page_id, title, content, link):
    blocks=[]
    blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{
                "type": "text",
                "text": {
                    "content": title,
                    "link": {"url": link}
                }
            }]
        }
    })
    
    #添加粗体支持
    def parse_markdown_to_notion(paragraph):
         """
         将 Markdown 格式的 **加粗文本** 转换为 Notion rich_text 结构。
         """
         rich_text = []
         pattern = re.compile(r"(\*\*(.*?)\*\*)|([^\*]+)")  # 匹配 **粗体** 或普通文本
         matches = pattern.finditer(paragraph)
         
         for match in matches:
             if match.group(1):  # 匹配到粗体部分
                 rich_text.append({
                     "type": "text",
                     "text": {"content": match.group(2)},  # 提取粗体文本
                     "annotations": {"bold": True}  # 设置粗体
                 })
             elif match.group(3):  # 匹配到普通文本
                 rich_text.append({
                     "type": "text",
                     "text": {"content": match.group(3)}  # 普通文本内容
                 })
         
         return rich_text 
    
    paragraphs = content.split('\n\n')
    for paragraph in paragraphs:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": parse_markdown_to_notion(paragraph)
            }
        })

    try:
        notion.blocks.children.append(block_id=page_id, children=blocks)
        print("更新noiton页面成功")
    except Exception as e:
        print(f"更新页面失败：{e}")

# 主程序
async def main():
    async with aiohttp.ClientSession() as session:
        news_list = await get_news_list(DATE, session)
        abstract = await get_abstract(news_list['abstract'], session)
        news = await get_news(news_list['news'], session)
        
        #md = news_to_markdown(DATE, abstract, news, news_list['news'])
        #save_text_to_file(NEWS_MD_PATH, md)
        #update_catalogue(CATALOGUE_JSON_PATH, README_PATH, DATE, abstract)

        page = create_news_page(abstract)
        for i, item in enumerate(news):
            update_news_page(page["id"], item["title"], item["content"], news_list['news'][i])
        print('全部成功, 程序结束')

# 运行
if __name__ == '__main__':
    asyncio.run(main())