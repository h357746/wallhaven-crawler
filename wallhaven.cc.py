import multiprocessing
import requests
import os
from bs4 import BeautifulSoup
import random
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageTk
import threading
from queue import Queue
from threading import Event
from ttkbootstrap import Style
from concurrent.futures import ThreadPoolExecutor
from requests.packages.urllib3.exceptions import SSLError
import sys
import time
from functools import partial

# 定义类别列表
typeList = [
    {"id": 0, "name": "请选择分类", "key": ""},
    {"id": 1, "name": "普通的", "key": "000"},
    {"id": 2, "name": "二次元", "key": "010"},
    {"id": 3, "name": "三次元", "key": "001"},
    {"id": 4, "name": "普通的+二次元", "key": "110"},
    {"id": 5, "name": "普通的+三次元", "key": "101"},
    {"id": 6, "name": "二次元+三次元", "key": "011"},
    {"id": 7, "name": "普通+二次元+三次元", "key": "111"},
]

r18List = [
    {"id": 0, "name": "请选择颜色等级", "key": ""},
    {"id": 1, "name": "全年龄", "key": "100"},
    {"id": 2, "name": "R17", "key": "010"},
    {"id": 3, "name": "R18", "key": "001"},
    {"id": 4, "name": "全年龄+R17", "key": "110"},
    {"id": 5, "name": "全年龄+R18", "key": "101"},
    {"id": 6, "name": "R17+R18", "key": "011"},
    {"id": 7, "name": "全年龄+R17+R18", "key": "111"},
]

sortList = [
    {"id": 0, "name": "请选择排序方式", "key": ""},
    {"id": 1, "name": "收藏量", "key": "favorites"},
    {"id": 2, "name": "排行榜", "key": "toplist"},
    {"id": 3, "name": "热门", "key": "hot"},
]

aiList = [
    {"id": 0, "name": "请选择是否包含AI", "key": ""},
    {"id": 1, "name": "无AI", "key": "0"},
    {"id": 2, "name": "有AI", "key": "1"},
]
headers = {}
stop_event = Event()  # 用于控制线程停止的事件对象
gui_queue = Queue()  # 用于GUI更新的队列
image_queue = Queue()  # 用于存储图片路径的队列
# 全局锁对象
download_lock = threading.Lock()


def print_to_text(text_widget, message):
    text_widget.config(state=tk.NORMAL)  # 确保文本框是可编辑的
    text_widget.insert(tk.END, message + "\n")
    text_widget.see(tk.END)  # 自动滚动到底部
    text_widget.config(state=tk.DISABLED)  # 禁用文本框


def process_gui_queue():
    while not gui_queue.empty():
        message = gui_queue.get()
        print_to_text(output_text, message)
    root.after(100, process_gui_queue)  # 每隔一段时间检查队列


def get_key_and_name(name, options_list):
    for option in options_list:
        if option["name"] == name:
            return option["key"], option["name"]
    return "", ""


def on_focus_in(event, entry, default_text):
    if entry.get() == default_text:
        entry.delete(0, tk.END)
        entry.config(foreground="black")


def on_focus_out(event, entry, default_text):
    if entry.get() == "":
        entry.insert(0, default_text)
        entry.config(foreground="gray")


def get_user_input():
    global type_key, type_name, r18_key, r18_name, sort_key, sort_name, ai_key, ai_name, first_page, last_page, headers, proxies, output_text

    type_key, type_name = get_key_and_name(type_var.get(), typeList)
    r18_key, r18_name = get_key_and_name(r18_var.get(), r18List)
    sort_key, sort_name = get_key_and_name(sort_var.get(), sortList)
    ai_key, ai_name = get_key_and_name(ai_var.get(), aiList)

    # 检查必填项
    if not type_key or type_key == "":
        messagebox.showerror("错误", "请选择分类")
        return
    if not r18_key or r18_key == "":
        messagebox.showerror("错误", "请选择颜色等级")
        return
    if not sort_key or sort_key == "":
        messagebox.showerror("错误", "请选择排序方式")
        return
    if not ai_key or ai_key == "":
        messagebox.showerror("错误", "请选择是否包含AI")
        return
    if not first_page_entry.get() or not last_page_entry.get():
        messagebox.showerror("错误", "请输入起始页数和结束页数")
        return
    if r18_key in ("101", "001", "011", "111"):
        cookies = cookie_entry.get()
        if not cookies or cookies == "请输入cookies":
            messagebox.showerror("错误", "请输入cookies")
            return
        headers["cookie"] = cookies

    # 获取代理配置
    proxy_address = proxy_entry.get()
    if proxy_address and proxy_address != "127.0.0.1:7890":
        proxies = {
            "http": f"http://{proxy_address}",
            "https": f"http://{proxy_address}",
        }
    else:
        proxies = {}

    first_page = int(first_page_entry.get())
    last_page = int(last_page_entry.get())
    # 启动一个新的线程来运行爬取任务
    crawl_button.config(state=tk.DISABLED)  # 禁用开始爬取按钮
    threading.Thread(target=start_crawl).start()


def show_image_preview(image_path):
    image = Image.open(image_path)
    image.thumbnail((400, 400), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(image)
    preview_label.config(image=photo)
    preview_label.image = photo  # 防止被垃圾回收


def download_image(image_url, image_filename):
    try:
        response = requests.get(
            image_url,
            headers=headers,
            proxies=proxies,
            verify=False,
            stream=True,
            timeout=60,
        )
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        block_size = 1024  # 1 Kibibyte
        downloaded_size = 0
        start_time = time.time()  # 记录开始时间
        with open(image_filename, "wb") as f:
            for data in response.iter_content(block_size):
                if stop_event.is_set():
                    gui_queue.put("爬取已停止...")
                    break
                if not data:
                    break
                f.write(data)
                downloaded_size += len(data)
                elapsed_time = time.time() - start_time  # 计算已用时间
                if elapsed_time > 0:
                    download_speed = (
                        downloaded_size / elapsed_time / 1024
                    )  # 计算下载速度（KB/s）
                else:
                    download_speed = 0
                progress = (
                    (downloaded_size / total_size) * 100 if total_size != 0 else 0
                )
                gui_queue.put(
                    f"下载图片进度: {image_filename} - {progress:.2f}% - 速度: {download_speed:.2f} KB/s"
                )
        gui_queue.put(f"成功下载图片: {image_filename}")
        return True
    except requests.RequestException as e:
        gui_queue.put(f"下载图片时出错：{e}")
        return False


def crawl_images(page):
    global stop_event, r18_key, type_key, sort_key, ai_key

    gui_queue.put(f"正在爬取第{page}页的图片...")

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
    headers["User-Agent"] = random.choice(user_agent_list)
    headers["Connection"] = "close"

    url = f"https://wallhaven.cc/toplist?page={page}&categories={type_key}&sorting={sort_key}&ai_art_filter={ai_key}&purity={r18_key}"

    while not stop_event.is_set():
        try:
            response = requests.get(
                url, headers=headers, proxies=proxies, verify=False, timeout=60
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            links = soup.select("ul li figure a.preview")

            for link in links:
                if stop_event.is_set():
                    gui_queue.put("爬取已停止...")
                    break

                try:
                    true_html = requests.get(
                        link["href"],
                        headers=headers,
                        proxies=proxies,
                        verify=False,
                        timeout=60,
                    )
                    true_html.raise_for_status()
                    new_soup = BeautifulSoup(true_html.text, "lxml")
                    new_link = new_soup.select_one("main section div img")
                    if new_link and "src" in new_link.attrs:
                        image_url = new_link["src"]
                        image_filename = f"{download_folder}/{image_url.split('/')[-1]}"

                        if (
                            os.path.exists(image_filename)
                            and os.path.getsize(image_filename) > 0
                        ):
                            gui_queue.put(f"文件已存在，跳过下载：{image_filename}")
                            continue
                        elif os.path.exists(image_filename):
                            os.remove(image_filename)
                            gui_queue.put(f"删除大小为0的文件：{image_filename}")
                            continue
                        gui_queue.put(f"开始下载图片: {image_url}")
                        if download_image(image_url, image_filename):
                            image_queue.put(image_filename)
                            root.after(0, update_preview)
                        time.sleep(5)
                except requests.RequestException as e:
                    gui_queue.put(f"下载图片时出错：{e}，失败图片Url：{link['href']}")
                    time.sleep(5)
                    if stop_event.is_set():
                        gui_queue.put("爬取已停止...")
                        break
                    continue
                except Exception as e:
                    gui_queue.put(f"未知错误：{e}，失败图片Url：{link['href']}")
                    time.sleep(5)
                    if stop_event.is_set():
                        gui_queue.put("爬取已停止...")
                        break
                    continue
            break  # 如果成功则退出循环
        except requests.RequestException as e:
            gui_queue.put(f"请求出错：{e}")
            time.sleep(5)
        except SSLError as e:
            gui_queue.put(f"SSL 错误：{e}")
            time.sleep(5)

        except Exception as e:
            gui_queue.put(f"未知错误：{e}")
            time.sleep(5)


def thread_function():
    global first_page, last_page
    for page in range(first_page, last_page + 1):
        crawl_images(page)


def start_crawl():
    global stop_event, download_folder, type_name, r18_name, sort_name, ai_name, proxies, output_text
    stop_event.clear()  # 清除停止事件
    crawl_button.config(state=tk.DISABLED)  # 禁用开始爬取按钮
    gui_queue.put(f"开始执行.......")

    # 动态创建文件夹
    download_folder = f"壁纸_{type_name}_{r18_name}_{sort_name}_{ai_name}"
    # 新增: 判断文件夹是否存在，如果不存在则创建
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
        gui_queue.put(f"创建文件夹: {download_folder}")

    # 使用 ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(thread_function)]
        for future in futures:
            try:
                future.result()  # 等待所有任务完成
            except Exception as e:
                gui_queue.put(f"任务执行出错：{e}")

    update_preview()
    gui_queue.put(f"执行结束.......")
    crawl_button.config(state=tk.NORMAL)


def update_preview():
    if not image_queue.empty():
        image_path = image_queue.get()
        show_image_preview(image_path)
        root.after(100, update_preview)  # 继续检查队列
    else:
        gui_queue.put(f"预览图片.......")


def update_gui():
    while not gui_queue.empty():
        message = gui_queue.get()
        print_to_text(output_text, message)
    root.after(100, update_gui)


def stop_all_crawls():
    global stop_event
    stop_event.set()  # 设置停止事件
    gui_queue.put("停止所有爬取请求已发送...")
    gui_queue.put("爬取已停止...")
    reset_state()
    crawl_button.config(state=tk.NORMAL)  # 恢复开始爬取按钮


def reset_state():
    global stop_event
    output_text.config(state=tk.NORMAL)  # 重新启用输出框
    output_text.delete(1.0, tk.END)  # 清空输出框
    output_text.config(state=tk.DISABLED)  # 禁用输出框
    crawl_button.config(state=tk.NORMAL)  # 重新启用开始爬取按钮


def on_close():
    stop_all_crawls()
    root.quit()  # 确保主事件循环终止
    root.destroy()  # 销毁窗口
    sys.exit()  # 添加: 确保控制台也正常退出


if __name__ == "__main__":
    # 初始化 ttkbootstrap 主题
    style = Style(theme="superhero")
    root = style.master
    root.title("壁纸爬虫")
    root.geometry("800x1200")
    # 设置窗口大小
    root.geometry("800x1200")  # 修改: 增加窗口大小
    # 加载图标并设置为窗口图标
    # 图标文件路径
    icon_path = "icon.png"

    # 检查图标文件是否存在
    if not os.path.exists(icon_path):
        gui_queue.put(f"图标文件未找到，请确保路径正确并且图标文件存在。")
    else:
        try:
            icon_photo = tk.PhotoImage(file=icon_path)
            root.wm_iconphoto(True, icon_photo)
        except tk.TclError:
            gui_queue.put(f"图标文件未找到，请确保路径正确并且图标文件存在。")

    # 设置背景画布
    canvas = tk.Canvas(root, highlightthickness=0)
    canvas.grid(row=0, column=0, rowspan=13, columnspan=2, sticky="nsew")
    bg_canvas = canvas.create_image(0, 0, anchor=tk.NW, image=None)

    # 加载背景图片
    bg_image_path = "background.png"
    if os.path.exists(bg_image_path):
        bg_image = Image.open(bg_image_path)
        bg_photo = ImageTk.PhotoImage(bg_image)
        canvas.config(
            width=bg_photo.width(), height=bg_photo.height()
        )  # 设置Canvas大小
        canvas.itemconfig(bg_canvas, image=bg_photo)
        canvas.bg_photo = bg_photo  # 防止被垃圾回收
        gui_queue.put(f"背景图片已成功加载: {bg_image_path}")
    else:
        gui_queue.put(f"背景图片文件未找到，请确保路径正确并且背景图片文件存在。")

    # 设置窗口透明度
    root.attributes("-alpha", 0.95)  # 修改: 增加透明度
    # 设置样式
    style = ttk.Style(root)
    style.configure(
        "Custom.TButton",
        font=("Helvetica", 14, "bold"),
        foreground="white",
        background="#007bff",
    )
    style.map("Custom.TButton", background=[("active", "#0056b3")])

    # 设置输入框样式
    style.configure("Custom.TEntry", fieldbackground="white", foreground="gray")

    # 设置默认透明背景
    default_bg_image = Image.new(
        "RGBA", (root.winfo_width(), root.winfo_height()), (0, 0, 0, 0)
    )
    default_bg_photo = ImageTk.PhotoImage(default_bg_image)
    root.default_bg_photo = default_bg_photo
    canvas.itemconfig(bg_canvas, image=default_bg_photo)

    # 类型选择
    type_label = ttk.Label(root, text="请选择分类：", font=("Helvetica", 14))
    type_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")

    type_var = tk.StringVar(value="请选择分类")
    type_menu = ttk.Combobox(
        root,
        textvariable=type_var,
        values=[item["name"] for item in typeList],
        state="readonly",
        font=("Helvetica", 12),
    )
    type_menu.grid(row=0, column=1, padx=20, pady=10, sticky="ew")

    # R18选择
    r18_label = ttk.Label(root, text="请选择颜色等级：", font=("Helvetica", 14))
    r18_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")

    r18_var = tk.StringVar(value="请选择颜色等级")
    r18_menu = ttk.Combobox(
        root,
        textvariable=r18_var,
        values=[item["name"] for item in r18List],
        state="readonly",
        font=("Helvetica", 12),
    )
    r18_menu.grid(row=1, column=1, padx=20, pady=10, sticky="ew")

    # 排序方式
    sort_label = ttk.Label(root, text="请选择排序方式：", font=("Helvetica", 14))
    sort_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")

    sort_var = tk.StringVar(value="请选择排序方式")
    sort_menu = ttk.Combobox(
        root,
        textvariable=sort_var,
        values=[item["name"] for item in sortList],
        state="readonly",
        font=("Helvetica", 12),
    )
    sort_menu.grid(row=2, column=1, padx=20, pady=10, sticky="ew")

    # AI选择
    ai_label = ttk.Label(root, text="请选择是否包含AI：", font=("Helvetica", 14))
    ai_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")

    ai_var = tk.StringVar(value="请选择是否包含AI")
    ai_menu = ttk.Combobox(
        root,
        textvariable=ai_var,
        values=[item["name"] for item in aiList],
        state="readonly",
        font=("Helvetica", 12),
    )
    ai_menu.grid(row=3, column=1, padx=20, pady=10, sticky="ew")

    # Cookies输入框
    cookie_label = ttk.Label(
        root, text="请输入cookies（如有需要）：", font=("Helvetica", 14)
    )
    cookie_label.grid(row=4, column=0, padx=20, pady=10, sticky="w")

    cookie_entry = ttk.Entry(
        root, style="Custom.TEntry", width=50, font=("Helvetica", 12)
    )
    cookie_entry.insert(0, "请输入cookies")
    cookie_entry.bind(
        "<FocusIn>", lambda event: on_focus_in(event, cookie_entry, "请输入cookies")
    )
    cookie_entry.bind(
        "<FocusOut>", lambda event: on_focus_out(event, cookie_entry, "请输入cookies")
    )
    cookie_entry.grid(row=4, column=1, padx=20, pady=10, sticky="ew")

    # 起始页数输入框
    first_page_label = ttk.Label(root, text="请输入起始页数：", font=("Helvetica", 14))
    first_page_label.grid(row=5, column=0, padx=20, pady=10, sticky="w")

    first_page_entry = ttk.Entry(
        root, style="Custom.TEntry", width=30, font=("Helvetica", 12)
    )
    first_page_entry.insert(0, "请输入起始页数")
    first_page_entry.bind(
        "<FocusIn>",
        lambda event: on_focus_in(event, first_page_entry, "请输入起始页数"),
    )
    first_page_entry.bind(
        "<FocusOut>",
        lambda event: on_focus_out(event, first_page_entry, "请输入起始页数"),
    )
    first_page_entry.grid(row=5, column=1, padx=20, pady=10, sticky="ew")

    # 结束页数输入框
    last_page_label = ttk.Label(root, text="请输入结束页数：", font=("Helvetica", 14))
    last_page_label.grid(row=6, column=0, padx=20, pady=10, sticky="w")

    last_page_entry = ttk.Entry(
        root, style="Custom.TEntry", width=30, font=("Helvetica", 12)
    )
    last_page_entry.insert(0, "请输入结束页数")
    last_page_entry.bind(
        "<FocusIn>", lambda event: on_focus_in(event, last_page_entry, "请输入结束页数")
    )
    last_page_entry.bind(
        "<FocusOut>",
        lambda event: on_focus_out(event, last_page_entry, "请输入结束页数"),
    )
    last_page_entry.grid(row=6, column=1, padx=20, pady=10, sticky="ew")

    # 代理输入框
    proxy_label = ttk.Label(
        root, text="请输入代理地址（如有需要）：", font=("Helvetica", 14)
    )
    proxy_label.grid(row=7, column=0, padx=20, pady=10, sticky="w")

    proxy_entry = ttk.Entry(
        root, style="Custom.TEntry", width=30, font=("Helvetica", 12)
    )
    proxy_entry.insert(0, "127.0.0.1:7890")  # 默认值
    proxy_entry.bind(
        "<FocusIn>", lambda event: on_focus_in(event, proxy_entry, "127.0.0.1:7890")
    )
    proxy_entry.bind(
        "<FocusOut>", lambda event: on_focus_out(event, proxy_entry, "127.0.0.1:7890")
    )
    proxy_entry.grid(row=7, column=1, padx=20, pady=10, sticky="ew")

    # 爬取按钮
    crawl_button = ttk.Button(
        root, text="开始爬取", command=get_user_input, style="Custom.TButton"
    )
    crawl_button.grid(row=8, column=0, padx=30, pady=20, sticky="ew")

    # 停止按钮
    stop_button = ttk.Button(
        root, text="停止所有爬取", command=stop_all_crawls, style="Custom.TButton"
    )
    stop_button.grid(row=8, column=1, padx=30, pady=20, sticky="ew")

    # 输出区域
    output_label = ttk.Label(root, text="日志信息：", font=("Helvetica", 14))
    output_label.grid(row=9, column=0, padx=20, pady=10, sticky="w")

    output_text = scrolledtext.ScrolledText(
        root, wrap=tk.WORD, width=60, height=15, font=("Helvetica", 12)
    )
    output_text.grid(row=10, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")

    # 图片预览区域
    preview_label = ttk.Label(root, text="图片预览：", font=("Helvetica", 14))
    preview_label.grid(row=11, column=0, padx=20, pady=10, sticky="w")

    preview_frame = ttk.Frame(
        root, borderwidth=2, relief="groove", width=500, height=500
    )
    preview_frame.grid(row=12, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")

    preview_label = ttk.Label(preview_frame)
    preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # 设置列权重以使组件居中
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)

    # 设置行权重以使输出文本框和预览区域可以扩展
    root.rowconfigure(10, weight=1)
    root.rowconfigure(12, weight=1)  # 使预览区域可扩展

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.after(100, process_gui_queue)  # 启动GUI队列处理器
    root.mainloop()
