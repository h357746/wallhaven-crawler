import requests
import os
from bs4 import BeautifulSoup
import random

# https://wallhaven.cc/toplist?page=1
# https://konachan.com/post?page=2&tags=
first_page= int(input("请输入要爬取的起始页数："))
last_page = int(input("请输入要爬取的结尾页数："))
n = 0
headers = {}
for page in range(first_page, last_page + 1):
    print("正在爬取第{}页的图片...".format(page))
    user_agent_list = [
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; WOW64) Gecko/20100101 Firefox/61.0",
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36",
        "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)",
        "Mozilla/5.0 (Macintosh; U; PPC Mac OS X 10.5; en-US; rv:1.9.2.15) Gecko/20110303 Firefox/3.6.15",
    ]
    headers['User-Agent'] = random.choice(user_agent_list)
    html = requests.get("https://konachan.com/post?page={}&tags=".format(page), headers=headers)
    soup = BeautifulSoup(html.text, 'lxml')
    link = soup.select("ul li a.thumb[href]")
    print("第{}页共有{}张图片".format(page, len(link)))
    for i in link:
        true_html = requests.get("https://konachan.com" + i['href'], headers=headers)
        new_soup = BeautifulSoup(true_html.text, 'lxml')
        new_link = new_soup.select_one('#highres')
        print("正在下载第{}张图片".format(link.index(i)+1))
        if not os.path.exists('konachan'):
            os.mkdir('konachan')
        with open('konachan/{}.jpg'.format(i['href'].split('/')[-2]), 'wb')as f:
            f.write(requests.get(new_link['href'], headers=headers).content)
