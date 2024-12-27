import aiohttp
import asyncio
from bs4 import BeautifulSoup
import os
import json
from datetime import datetime

# 获取当前日期
def get_date():
    return datetime.now().strftime("%Y%m%d")

# 当前日期
DATE = get_date()

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

# 主程序
async def main():
    async with aiohttp.ClientSession() as session:
        news_list = await get_news_list(DATE, session)
        abstract = await get_abstract(news_list['abstract'], session)
        news = await get_news(news_list['news'], session)
        md = news_to_markdown(DATE, abstract, news, news_list['news'])
        
        save_text_to_file(NEWS_MD_PATH, md)
        update_catalogue(CATALOGUE_JSON_PATH, README_PATH, DATE, abstract)
        print('全部成功, 程序结束')

# 运行
if __name__ == '__main__':
    asyncio.run(main())