# -*- coding: utf-8 -*-
# 国家中小学智慧教育平台 资源下载工具 v3.0 (命令行版)
# 项目地址：https://github.com/happycola233/tchMaterial-parser
# 作者：肥宅水水呀（https://space.bilibili.com/324042405）以及其他为本工具作出贡献的用户
# 最近更新于：2025-03-14

import os
import platform
import requests
from functools import partial
import threading
import json
import base64
import tempfile
import psutil

os_name = platform.system() # 获取操作系统类型

def parse(url: str) -> tuple[str, str, str] | tuple[None, None, None]: # 解析 URL
    try:
        content_id, content_type, resource_url = None, None, None

        # 简单提取 URL 中的 contentId 与 contentType（这种方法不严谨，但为了减少导入的库只能这样了）
        for q in url[url.find("?") + 1:].split("&"):
            if q.split("=")[0] == "contentId":
                content_id = q.split("=")[1]
                break

        for q in url[url.find("?") + 1:].split("&"):
            if q.split("=")[0] == "contentType":
                content_type = q.split("=")[1]
                break
        if not content_type:
            content_type = "assets_document"

        # 获得该 contentId 下资源的信息，返回数据示例：
        """
        {
            "id": "4f64356a-8df7-4579-9400-e32c9a7f6718",
            // ...
            "ti_items": [
                {
                    // ...
                    "ti_storages": [ // 资源文件地址
                        "https://r1-ndr-private.ykt.cbern.com.cn/edu_product/esp/assets/4f64356a-8df7-4579-9400-e32c9a7f6718.pkg/pdf.pdf",
                        "https://r2-ndr-private.ykt.cbern.com.cn/edu_product/esp/assets/4f64356a-8df7-4579-9400-e32c9a7f6718.pkg/pdf.pdf",
                        "https://r3-ndr-private.ykt.cbern.com.cn/edu_product/esp/assets/4f64356a-8df7-4579-9400-e32c9a7f6718.pkg/pdf.pdf"
                    ],
                    // ...
                },
                {
                    // ...（和上一个元素组成一样）
                }
            ]
        }
        """
        # 其中 $.ti_items 的每一项对应一个资源

        if "syncClassroom/basicWork/detail" in url: # 对于“基础性作业”的解析
            response = session.get(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/resources/details/{content_id}.json")
        else: # 对于课本的解析
            if content_type == "thematic_course": # 对专题课程（含电子课本、视频等）的解析
                response = session.get(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/resources/details/{content_id}.json")
            else: # 对普通电子课本的解析
                response = session.get(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{content_id}.json")

        data = response.json()
        for item in list(data["ti_items"]):
            if item["lc_ti_format"] == "pdf": # 找到存有 PDF 链接列表的项
                # resource_url: str = item["ti_storages"][0].replace("-private", "") # 获取并构建 PDF 的 URL
                resource_url: str = item["ti_storages"][0] # 获取并构建 PDF 的 URL
                break

        if not resource_url:
            if content_type == "thematic_course": # 专题课程
                resources_resp = session.get(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/thematic_course/{content_id}/resources/list.json")
                resources_data = resources_resp.json()
                for resource in list(resources_data):
                    if resource["resource_type_code"] == "assets_document":
                        for item in list(resource["ti_items"]):
                            if item["lc_ti_format"] == "pdf":
                                # resource_url: str = item["ti_storages"][0].replace("-private", "")
                                resource_url: str = item["ti_storages"][0]
                                break
                if not resource_url:
                    return None, None, None
            else:
                return None, None, None
        return resource_url, content_id, data["title"]
    except Exception as e:
        print(f"解析失败: {e}")
        return None, None, None

def download_file(url: str, save_path: str) -> None: # 下载文件
    global download_states
    response = session.get(url, headers=headers, stream=True)

    # 检测401
    if response.status_code == 401:
        print("授权失败: access_token 可能已过期或无效，请重新设置后再试！")
        open_access_token_window()
        print("授权成功: access_token ！")
        # download_btn.config(state="normal")  # 当弹出“设置token”窗口后，先行恢复下载按钮可用
        # return

    total_size = int(response.headers.get("Content-Length", 0))
    current_state = { "download_url": url, "save_path": save_path, "downloaded_size": 0, "total_size": total_size, "finished": False, "failed": False }
    download_states.append(current_state)

    print("--------- current_state", current_state)

    try:
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=131072): # 分块下载，每次下载 131072 字节（128 KB）
                file.write(chunk)
                current_state["downloaded_size"] += len(chunk)
                all_downloaded_size = sum(state["downloaded_size"] for state in download_states)
                all_total_size = sum(state["total_size"] for state in download_states)
                downloaded_number = len([state for state in download_states if state["finished"]])
                total_number = len(download_states)

                if all_total_size > 0: # 防止下面一行代码除以 0 而报错
                    download_progress = (all_downloaded_size / all_total_size) * 100
                    # 更新进度条
                    print(f"\r下载进度: {format_bytes(all_downloaded_size)}/{format_bytes(all_total_size)} ({download_progress:.2f}%) 已下载 {downloaded_number}/{total_number}", end="")
                    # 更新标签以显示当前下载进度

        current_state["downloaded_size"] = current_state["total_size"]
        current_state["finished"] = True
    except Exception as e:
        current_state["downloaded_size"], current_state["total_size"] = 0, 0
        current_state["finished"], current_state["failed"] = True, True
        print(f"\n下载失败: {e}")

    if all(state["finished"] for state in download_states):
        print("\n下载完成")
        failed_urls = [state["download_url"] for state in download_states if state["failed"]]
        if len(failed_urls) > 0:
            print(f"以下链接下载失败: {' '.join(failed_urls)}")
        else:
            print(f"文件已下载到: {os.path.dirname(save_path)}")

def format_bytes(size: float) -> str: # 格式化字节
    # 返回以 KB、MB、GB、TB 为单位的数据大小
    for x in ["字节", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:3.1f} {x}"
        size /= 1024.0
    return f"{size:3.1f} PB"

def download() -> None: # 下载资源文件
    global download_states
    download_states = [] # 初始化下载状态
    urls = [line.strip() for line in input("请输入资源页面的网址（每个网址一行），完成后按 Ctrl+D 结束输入:\n").splitlines() if line.strip()] # 获取所有非空行
    failed_links = []

    if len(urls) > 1:
        print("您选择了多个链接，将在指定的文件夹中使用教材名称作为文件名进行下载。")
        dir_path = input("请输入保存文件夹路径: ").strip()
        if not dir_path:
            return
    else:
        dir_path = None

    for url in urls:
        resource_url, content_id, title = parse(url)
        if not resource_url:
            failed_links.append(url) # 添加到失败链接
            continue

        if dir_path:
            default_filename = title or "download"
            save_path = os.path.join(dir_path, f"{default_filename}.pdf") # 构造完整路径
        else:
            default_filename = title or "download"
            save_path = input(f"请输入保存路径（默认文件名为: {default_filename}.pdf）: ").strip()
            if not save_path: # 用户取消了文件保存操作
                return

        thread_it(download_file, (resource_url, save_path)) # 开始下载（多线程，防止窗口卡死）

    if failed_links:
        print(f"以下链接无法解析:\n{', '.join(failed_links)}") # 显示警告对话框

    if not urls and not failed_links:
        print("未提供任何有效的下载链接")

def open_access_token_window():
    """
    提供用户输入 Access Token，
    并在关闭窗口时恢复“下载”按钮的可用状态。
    """
    global access_token
    # token_input = input("请粘贴从浏览器获取的 Access Token: ").strip()
    token_input = "7F938B205F876FC3C7550081F114A1A4D9D69F45966CB26AF9D9159BAB07F5CC58037A113813D63E8F0E85A6D151FCBCEC2401B03FC902E7"
    if token_input:
        set_access_token(token_input)
        print(f"Access Token {token_input} 已保存！")
    else:
        print("请输入有效的 Access Token！")

class ResourceHelper: # 获取网站上资源的数据
    def parse_hierarchy(self, hierarchy): # 解析层级数据
        if not hierarchy: # 如果没有层级数据，返回空
            return None

        parsed = {}
        for h in hierarchy:
            for ch in h["children"]:
                parsed[ch["tag_id"]] = { "display_name": ch["tag_name"], "children": self.parse_hierarchy(ch["hierarchies"]) }
        return parsed

    def fetch_book_list(self): # 获取课本列表
        # 获取电子课本层级数据
        tags_resp = session.get("https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/tags/tch_material_tag.json")
        tags_data = tags_resp.json()
        parsed_hier = self.parse_hierarchy(tags_data["hierarchies"])

        # 获取电子课本 URL 列表
        list_resp = session.get("https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/version/data_version.json")
        list_data: list[str] = list_resp.json()["urls"].split(",")

        # 获取电子课本列表
        for url in list_data:
            book_resp = session.get(url)
            book_data: list[dict] = book_resp.json()
            for book in book_data:
                if len(book["tag_paths"]) > 0: # 某些非课本资料的 tag_paths 属性为空数组
                    # 解析课本层级数据
                    tag_paths: list[str] = book["tag_paths"][0].split("/")[2:] # 电子课本 tag_paths 的前两项为“教材”、“电子教材”

                    # 如果课本层级数据不在层级数据中，跳过
                    temp_hier = parsed_hier[book["tag_paths"][0].split("/")[1]]
                    if not tag_paths[0] in temp_hier["children"]:
                        continue

                    # 分别解析课本层级
                    for p in tag_paths:
                        if temp_hier["children"] and temp_hier["children"].get(p):
                            temp_hier = temp_hier["children"].get(p)
                    if not temp_hier["children"]:
                        temp_hier["children"] = {}

                    book["display_name"] = book["title"] if "title" in book else book["name"] if "name" in book else f"(未知电子课本 {book['id']})"

                    temp_hier["children"][book["id"]] = book

        return parsed_hier

    def fetch_lesson_list(self): # 获取课件列表
        # 获取课件层级数据
        tags_resp = session.get("https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/tags/national_lesson_tag.json")
        tags_data = tags_resp.json()
        parsed_hier = self.parse_hierarchy([{ "children": [{ "tag_id": "__internal_national_lesson", "hierarchies": tags_data["hierarchies"], "tag_name": "课件资源" }] }])

        # 获取课件 URL 列表
        list_resp = session.get("https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/national_lesson/teachingmaterials/version/data_version.json")
        list_list[str] = list_resp.json()["urls"]

        # 获取课件列表
        for url in list_data:
            lesson_resp = session.get(url)
            lesson_list[dict] = lesson_resp.json()
            for lesson in lesson_data:
                if len(lesson["tag_list"]) > 0:
                    # 解析课件层级数据
                    tag_paths: list[str] = [tag["tag_id"] for tag in sorted(lesson["tag_list"], key=lambda tag: tag["order_num"])]

                    # 分别解析课件层级
                    temp_hier = parsed_hier["__internal_national_lesson"]
                    for p in tag_paths:
                        if temp_hier["children"] and temp_hier["children"].get(p):
                            temp_hier = temp_hier["children"].get(p)
                    if not temp_hier["children"]:
                        temp_hier["children"] = {}

                    lesson["display_name"] = lesson["title"] if "title" in lesson else lesson["name"] if "name" in lesson else f"(未知课件 {lesson['id']})"

                    temp_hier["children"][lesson["id"]] = lesson

        return parsed_hier

    def fetch_resource_list(self): # 获取资源列表
        book_hier = self.fetch_book_list()
        # lesson_hier = self.fetch_lesson_list() # 目前此函数代码存在问题
        return { **book_hier }

def thread_it(func, args: tuple = ()): # args 为元组，且默认值是空元组
    # 打包函数到线程
    t = threading.Thread(target=func, args=args)
    t.start()

# 初始化请求
session = requests.Session()
# 设置请求头部，包含认证信息
access_token = None
headers = { "X-ND-AUTH": 'MAC id="0",nonce="0",mac="0"' } # “MAC id”等同于“access_token”，“nonce”和“mac”不可缺省但无需有效
session.proxies = { "http": None, "https": None } # 全局忽略代理

# 尝试从注册表读取本地存储的 access_token（仅限Windows）
def load_access_token_from_registry():
    global access_token
    if os_name == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\tchMaterial-parser", 0, winreg.KEY_READ) as key:
                token, _ = winreg.QueryValueEx(key, "AccessToken")
                if token:
                    access_token = token
                    # 更新请求头
                    headers["X-ND-AUTH"] = f'MAC id="{access_token}",nonce="0",mac="0"'
        except:
            pass  # 读取失败则不做处理

# 将access_token写入注册表
def save_access_token_to_registry(token: str):
    if os_name == "Windows":
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\\tchMaterial-parser") as key:
                winreg.SetValueEx(key, "AccessToken", 0, winreg.REG_SZ, token)
        except:
            pass

# 设置并更新access_token
def set_access_token(token: str):
    global access_token, headers
    access_token = token
    headers["X-ND-AUTH"] = f'MAC id="{access_token}",nonce="0",mac="0"'
    save_access_token_to_registry(token)

# 立即尝试加载已存的access_token（如果有的话）
load_access_token_from_registry()

# 获取资源列表
try:
    resource_list = ResourceHelper().fetch_resource_list()
except Exception as e:
    resource_list = {}
    print(f"获取资源列表失败，请手动填写资源链接，或重新打开本程序: {e}")

while True:
    print("\n请选择操作:")
    print("1. 下载资源")
    print("2. 设置 Access Token")
    print("3. 退出")
    choice = input("请输入选项编号: ")

    if choice == "1":
        download()
    elif choice == "2":
        open_access_token_window()
    elif choice == "3":
        break
    else:
        print("无效的选项，请重新选择。")
