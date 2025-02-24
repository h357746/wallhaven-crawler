import multiprocessing
import requests
import os
from bs4 import BeautifulSoup
import base64
import random
import threading
from queue import Queue
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from urllib3.exceptions import SSLError
import sys
import time
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFrame,
    QMainWindow,
    QMessageBox,
    QFormLayout,
    QSizePolicy,
)
from PyQt6.QtGui import QPixmap, QImage, QIcon
from PyQt6.QtCore import Qt, QTimer, QMetaObject, QVariant, pyqtSlot
from PyQt6 import QtGui
from icon import iconImg
from background import backgroundImg


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
    text_widget.setTextColor(Qt.GlobalColor.white)  # 设置文本颜色为白色
    text_widget.append(message)
    text_widget.setTextColor(Qt.GlobalColor.black)  # 恢复默认文本颜色


def get_key_and_name(name, options_list):
    for option in options_list:
        if option["name"] == name:
            return option["key"], option["name"]
    return "", ""


def on_focus_in(event, entry, default_text):
    if entry.get() == default_text:
        entry.delete(0, len(default_text))
        entry.setStyleSheet("color: black")


def on_focus_out(event, entry, default_text):
    if entry.get() == "":
        entry.setText(default_text)
        entry.setStyleSheet("color: gray")


def show_image_preview(image_path):
    pass  # 或者替换为 PyQt6 的图像显示方法


def download_image(image_url, image_filename, window):
    try:
        response = requests.get(
            image_url,
            headers=headers,
            proxies=window.proxies,  # 使用 window.proxies
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
        image_queue.put(image_filename)  # 将图片路径放入 image_queue
        # 调用 update_preview 来更新图片预览
        QMetaObject.invokeMethod(
            window,
            "update_preview",
            Qt.ConnectionType.QueuedConnection,
        )
        return True
    except requests.RequestException as e:
        gui_queue.put(f"下载图片时出错：{e}")
        return False
    except Exception as e:
        gui_queue.put(f"未知错误：{e}")
        return False


def crawl_images(page, window):
    global stop_event

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

    # 修改为使用 window.type_key, window.r18_key, window.sort_key, window.ai_key
    url = f"https://wallhaven.cc/toplist?page={page}&categories={window.type_key}&sorting={window.sort_key}&ai_art_filter={window.ai_key}&purity={window.r18_key}"

    while not stop_event.is_set():
        try:
            response = requests.get(
                url,
                headers=headers,
                proxies=window.proxies,
                verify=False,
                timeout=60,  # 使用 window.proxies
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
                        proxies=window.proxies,  # 使用 window.proxies
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
                        if download_image(
                            image_url, image_filename, window
                        ):  # 传递 window 对象
                            image_queue.put(image_filename)
                        time.sleep(8)
                except requests.RequestException as e:
                    gui_queue.put(f"下载图片时出错：{e}，失败图片Url：{link['href']}")
                    time.sleep(8)
                    if stop_event.is_set():
                        gui_queue.put("爬取已停止...")
                        break
                    continue
                except Exception as e:
                    gui_queue.put(f"未知错误：{e}，失败图片Url：{link['href']}")
                    time.sleep(8)
                    if stop_event.is_set():
                        gui_queue.put("爬取已停止...")
                        break
                    continue
            break  # 如果成功则退出循环
        except requests.RequestException as e:
            gui_queue.put(f"请求出错：{e}")
            time.sleep(8)
        except SSLError as e:
            gui_queue.put(f"SSL 错误：{e}")
            time.sleep(8)

        except Exception as e:
            gui_queue.put(f"未知错误：{e}")
            time.sleep(8)


def thread_function(window):
    for page in range(
        window.first_page, window.last_page + 1
    ):  # 修改为使用 window.first_page 和 window.last_page
        crawl_images(page, window)  # 传递 window 对象


def update_gui():
    while not gui_queue.empty():
        message = gui_queue.get()
        # 使用 QMetaObject.invokeMethod 来确保在主线程中更新 GUI
        from PyQt6.QtCore import QMetaObject, Qt

        QMetaObject.invokeMethod(
            window,
            "print_to_text",
            Qt.ConnectionType.QueuedConnection,
            QVariant(str, message),
        )
    QTimer.singleShot(100, update_gui)


class WallhavenCrawler(QMainWindow):  # 修改为继承自 QMainWindow
    def __init__(self):
        super().__init__()
        self.initUI()
        # 初始化实例变量
        self.type_name = ""
        self.r18_name = ""
        self.sort_name = ""
        self.ai_name = ""
        self.proxies = {}  # 初始化 proxies 属性
        self.first_page = 0  # 新增实例变量
        self.last_page = 0  # 新增实例变量
        self.is_valid = True  # 新增标志来指示对象是否仍然有效

    def initUI(self):
        self.setWindowTitle("壁纸爬虫")
        self.setGeometry(100, 100, 1200, 800)  # 调整窗口大小以适应横向布局
        self.setWindowOpacity(0.95)

        # 设置图标
        icon_data = iconImg  # 确保 icon 是一个 base64 编码的字符串
        icon = base64.b64decode(icon_data)  # 解码 base64 字符串为二进制数据
        Pixmap = QtGui.QPixmap()  # 用于绘制图像的类
        Pixmap.loadFromData(icon)  # 使用解码后的二进制数据加载 QPixmap
        icon = QtGui.QIcon(Pixmap)  # 使用 QPixmap 创建 QIcon
        self.setWindowIcon(icon)
        # 设置背景图片
        bgImg = base64.b64decode(backgroundImg)
        bg_image = QImage.fromData(bgImg)  # 使用 QImage.fromData() 解码字节数据
        if not bg_image.isNull():  # 检查图像是否有效
            bg_pixmap = QPixmap.fromImage(bg_image)  # 将 QImage 转换为 QPixmap
            self.bg_label = QLabel(self)
            self.bg_label.setPixmap(bg_pixmap)
            self.bg_label.setGeometry(0, 0, 1200, 800)
            self.bg_label.setScaledContents(True)  # 设置背景图片自适应窗口大小
            self.bg_label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )  # 设置大小策略为可扩展
        else:
            gui_queue.put("背景图片加载失败，请检查 background 变量的内容")

        # 主布局
        main_layout = QHBoxLayout()  # 使用 QHBoxLayout 来放置左侧和右侧布局

        # 左侧布局
        left_layout = QVBoxLayout()

        # 使用 QFormLayout 来对齐标签和输入框
        form_layout = QFormLayout()

        # 类型选择
        type_label = QLabel("请选择分类：")
        type_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.type_var = QComboBox()
        self.type_var.addItems([item["name"] for item in typeList])
        form_layout.addRow(type_label, self.type_var)

        # R18选择
        r18_label = QLabel("请选择颜色等级：")
        r18_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.r18_var = QComboBox()
        self.r18_var.addItems([item["name"] for item in r18List])
        form_layout.addRow(r18_label, self.r18_var)

        # 排序方式
        sort_label = QLabel("请选择排序方式：")
        sort_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.sort_var = QComboBox()
        self.sort_var.addItems([item["name"] for item in sortList])
        form_layout.addRow(sort_label, self.sort_var)

        # AI选择
        ai_label = QLabel("请选择是否包含AI：")
        ai_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.ai_var = QComboBox()
        self.ai_var.addItems([item["name"] for item in aiList])
        form_layout.addRow(ai_label, self.ai_var)

        # Cookies输入框
        cookie_label = QLabel("请输入cookies（如有需要）：")
        cookie_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.cookie_entry = QLineEdit()
        self.cookie_entry.setPlaceholderText("请输入cookies")
        form_layout.addRow(cookie_label, self.cookie_entry)

        # 起始页数输入框
        first_page_label = QLabel("请输入起始页数：")
        first_page_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.first_page_entry = QLineEdit()
        self.first_page_entry.setPlaceholderText("请输入起始页数")
        form_layout.addRow(first_page_label, self.first_page_entry)

        # 结束页数输入框
        last_page_label = QLabel("请输入结束页数：")
        last_page_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.last_page_entry = QLineEdit()
        self.last_page_entry.setPlaceholderText("请输入结束页数")
        form_layout.addRow(last_page_label, self.last_page_entry)

        # 代理输入框
        proxy_label = QLabel("请输入代理地址（如有需要）：")
        proxy_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.proxy_entry = QLineEdit()
        self.proxy_entry.setPlaceholderText("127.0.0.1:7890")
        form_layout.addRow(proxy_label, self.proxy_entry)

        # 添加表单布局到左侧布局
        form_widget = QWidget()
        form_widget.setLayout(form_layout)
        left_layout.addWidget(form_widget)

        # 按钮布局
        button_layout = QHBoxLayout()
        self.crawl_button = QPushButton("开始爬取")
        self.crawl_button.clicked.connect(lambda: self.get_user_input())
        button_layout.addWidget(self.crawl_button)

        self.stop_button = QPushButton("停止爬取")
        self.stop_button.clicked.connect(self.stop_all_crawls)
        self.stop_button.setEnabled(False)  # 初始状态下停止按钮禁用
        button_layout.addWidget(self.stop_button)

        left_layout.addLayout(button_layout)

        # 输出区域
        self.output_label = QLabel("日志信息：")
        self.output_label.setStyleSheet("color: white")  # 修改字体颜色为白色
        self.output_text = QTextEdit(self)  # 假设使用 QTextEdit 作为输出文本控件
        self.output_text.setReadOnly(True)
        self.output_text.setFixedHeight(500)  # 固定日志预览区域的高度
        left_layout.addWidget(self.output_label)
        left_layout.addWidget(self.output_text)

        # 添加左侧布局到主布局
        main_layout.addLayout(left_layout)

        # 图片预览区域
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        preview_frame.setLineWidth(2)
        preview_layout = QVBoxLayout()
        preview_frame.setLayout(preview_layout)
        preview_frame.setFixedWidth(600)  # 调整图片预览区域的宽度

        # 设置 preview_label 的 objectName
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 居中显示图片
        self.preview_label.setObjectName("preview_label")
        preview_layout.addWidget(self.preview_label)

        main_layout.addWidget(preview_frame)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # 定时器用于处理GUI队列
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_gui_queue)
        self.timer.start(100)

        # 设置关闭事件
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.destroyed.connect(self.on_close)

    def get_user_input(self):
        self.type_key, self.type_name = get_key_and_name(
            self.type_var.currentText(), typeList
        )
        self.r18_key, self.r18_name = get_key_and_name(
            self.r18_var.currentText(), r18List
        )
        self.sort_key, self.sort_name = get_key_and_name(
            self.sort_var.currentText(), sortList
        )
        self.ai_key, self.ai_name = get_key_and_name(self.ai_var.currentText(), aiList)

        # 检查必填项
        if not self.type_key or self.type_key == "":
            QMessageBox.critical(self, "错误", "请选择分类")
            return
        if not self.r18_key or self.r18_key == "":
            QMessageBox.critical(self, "错误", "请选择颜色等级")
            return
        if not self.sort_key or self.sort_key == "":
            QMessageBox.critical(self, "错误", "请选择排序方式")
            return
        if not self.ai_key or self.ai_key == "":
            QMessageBox.critical(self, "错误", "请选择是否包含AI")
            return
        if not self.first_page_entry.text() or not self.last_page_entry.text():
            QMessageBox.critical(self, "错误", "请输入起始页数和结束页数")
            return
        if self.r18_key in ("101", "001", "011", "111"):
            cookies = self.cookie_entry.text()
            if not cookies or cookies == "请输入cookies":
                QMessageBox.critical(self, "错误", "请输入cookies")
                return
            headers["cookie"] = cookies

        # 获取代理配置
        proxy_address = self.proxy_entry.text()
        if proxy_address and proxy_address != "127.0.0.1:7890":
            self.proxies = {
                "http": f"http://{proxy_address}",
                "https": f"http://{proxy_address}",
            }
        else:
            self.proxies = {}

        self.first_page = int(self.first_page_entry.text())  # 设置实例变量
        self.last_page = int(self.last_page_entry.text())  # 设置实例变量
        # 启动一个新的线程来运行爬取任务
        threading.Thread(target=self.start_crawl).start()
        self.crawl_button.setEnabled(False)  # 禁用开始爬取按钮
        self.stop_button.setEnabled(True)  # 启用停止爬取按钮

    def show_image_preview(self, image_path):
        # 在这里实现 PyQt6 的图像显示方法
        preview_label = self.findChild(QLabel, "preview_label")
        if preview_label:
            pixmap = QPixmap(image_path)
            preview_label.setPixmap(
                pixmap.scaled(
                    preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def print_to_text(self, text_widget, message):
        text_widget.setTextColor(Qt.GlobalColor.white)
        text_widget.append(message)

    @pyqtSlot()  # 声明为槽函数
    def update_gui(self):
        while not gui_queue.empty():
            message = gui_queue.get()
            self.print_to_text(self.output_text, message)
        QTimer.singleShot(100, self.update_gui)

    @pyqtSlot()
    def update_preview(self):
        if not image_queue.empty():
            image_path = image_queue.get()
            self.show_image_preview(image_path)
            QTimer.singleShot(100, self.update_preview)  # 继续检查队列
        else:
            gui_queue.put(f"预览图片.......")

    def start_crawl(self):
        global stop_event, download_folder, proxies, output_text
        stop_event.clear()  # 清除停止事件
        self.crawl_button.setEnabled(False)  # 禁用开始爬取按钮
        gui_queue.put(f"开始执行.......")

        # 动态创建文件夹
        download_folder = (
            f"壁纸_{self.type_name}_{self.r18_name}_{self.sort_name}_{self.ai_name}"
        )
        # 新增: 判断文件夹是否存在，如果不存在则创建
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
            gui_queue.put(f"创建文件夹: {download_folder}")

        # 使用 ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(thread_function, self)]  # 传递 window 对象
            for future in futures:
                try:
                    future.result()  # 等待所有任务完成
                except Exception as e:
                    gui_queue.put(f"任务执行出错：{e}")

        # 使用 QMetaObject.invokeMethod 来确保在主线程中更新 GUI
        if self.is_valid:  # 检查对象是否仍然有效
            QMetaObject.invokeMethod(self, "update_gui", Qt.ConnectionType.QueuedConnection)
        gui_queue.put(f"执行结束.......")

        # 使用 QMetaObject.invokeMethod 来确保在主线程中更新 GUI
        if self.is_valid:  # 检查对象是否仍然有效
            QMetaObject.invokeMethod(
                self,
                "set_crawl_button_enabled",
                Qt.ConnectionType.QueuedConnection,
            )

    @pyqtSlot()
    def set_crawl_button_enabled(self):
        self.crawl_button.setEnabled(True)  # 恢复开始爬取按钮

    def process_gui_queue(self):
        while not gui_queue.empty():
            message = gui_queue.get()
            self.print_to_text(self.output_text, message)

    def stop_all_crawls(self):
        global stop_event
        stop_event.set()  # 设置停止事件
        gui_queue.put("停止所有爬取请求已发送...")
        gui_queue.put("爬取已停止...")
        self.reset_state()
        self.crawl_button.setEnabled(True)  # 恢复开始爬取按钮
        self.stop_button.setEnabled(False)  # 禁用停止爬取按钮

    def reset_state(self):
        self.output_text.setReadOnly(False)  # 重新启用输出框
        self.output_text.clear()  # 清空输出框
        self.output_text.setReadOnly(True)  # 禁用输出框
        self.crawl_button.setEnabled(True)  # 重新启用开始爬取按钮
        self.stop_button.setEnabled(False)  # 禁用停止爬取按钮

    def on_close(self):
        self.stop_all_crawls()
        self.is_valid = False  # 设置标志为无效
        self.close()  # 使用self.close()来关闭窗口
        sys.exit()  # 确保控制台也正常退出

    def resizeEvent(self, event):
        if hasattr(self, "bg_label") and self.bg_label:
            self.bg_label.setGeometry(0, 0, event.size().width(), event.size().height())
        super().resizeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WallhavenCrawler()
    window.show()
    sys.exit(app.exec())
