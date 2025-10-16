#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微信文章批量转PDF工具

作者：小安
公众号：小安驿站
版本：1.0.0
功能：将包含微信文章链接的CSV文件批量转换为PDF文件并按公众号分类存储

关注公众号【小安驿站】获取更多实用工具和教程！
"""

import csv
import os
from playwright.sync_api import sync_playwright
import time
import subprocess
import sys
import logging
import queue
import threading
from dataclasses import dataclass

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pdf_processing.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def crop_pdf_margins(pdf_path):
    """裁剪PDF边距，移除开头和结尾的空白内容，保留左右边距并将背景设置为白色"""
    try:
        # 使用pdfCropMargins裁剪边距
        cropped_pdf_path = pdf_path.replace('.pdf', '_cropped.pdf')
        command = [
            sys.executable, '-m', 'pdfCropMargins', 
            '-o', cropped_pdf_path,
            '-p', '0.0',  # 不改变页面大小
            '-a4', '20', '20', '0', '0',  # 保留左右各20%的边距，上下不保留额外边距
            '-s',  # 删除空白页面
            '-c', 'o',  # 使用原始页面大小并设置背景为白色
            '-ms', '50',  # 设置页面空白检测阈值，使用整数值
            pdf_path
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            # 替换原文件
            os.replace(cropped_pdf_path, pdf_path)
            logging.info(f"已裁剪PDF边距: {pdf_path}")
            return True
        else:
            logging.warning(f"裁剪PDF边距失败: {result.stderr}")
            # 如果裁剪失败，删除可能创建的临时文件
            if os.path.exists(cropped_pdf_path):
                os.remove(cropped_pdf_path)
            return False
    except Exception as e:
        logging.error(f"裁剪PDF边距时出错 {pdf_path}: {str(e)}")
        return False

def save_page_as_pdf(url, filename, retries=3):
    """使用Playwright将网页保存为PDF，支持重试机制"""
    for attempt in range(retries):
        try:
            logging.info(f"正在加载: {url}" + (f" (尝试 {attempt + 1}/{retries})" if attempt > 0 else ""))
            
            # 在当前线程中启动Playwright
            with sync_playwright() as playwright:
                # 启动浏览器
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                # 访问页面
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # 检查是否需要人工验证（在headless模式下无法处理）
                if "环境异常" in page.content() or "去验证" in page.content():
                    logging.warning("检测到验证页面，此模式下无法处理，跳过...")
                    browser.close()
                    return False
                
                # 等待页面主要内容加载完成
                try:
                    page.wait_for_selector("#js_article", timeout=30000)  # 等待文章内容加载
                except:
                    logging.warning(f"等待文章内容加载超时，继续处理: {url}")
                
                # 等待图片加载完成
                # 等待所有图片加载完成或者超时
                start_time = time.time()
                while time.time() - start_time < 20:  # 最多等待20秒
                    pending_images = page.query_selector_all("img[data-src]")
                    if len(pending_images) == 0:
                        break
                    # 触发懒加载
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(1)
                
                # 滚动页面以触发图片加载 - 分步滚动确保所有图片加载
                page_height = page.evaluate("document.body.scrollHeight")
                viewport_height = page.evaluate("window.innerHeight")
                scroll_step = viewport_height * 0.8  # 每次滚动视口高度的80%
                steps = int(page_height / scroll_step) + 1
                
                for i in range(steps):
                    page.evaluate(f"window.scrollTo(0, {min(i * scroll_step, page_height)})")
                    # 等待图片加载
                    time.sleep(0.5)
                
                # 回到顶部
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1)
                
                # 创建PDF目录（如果不存在）
                pdf_dir = os.path.dirname(filename)
                if not os.path.exists(pdf_dir):
                    os.makedirs(pdf_dir)
                
                # 保存为PDF
                page.pdf(
                    path=filename,
                    format="A4",
                    print_background=True
                )
                
                # 关闭浏览器
                browser.close()
                
                # 裁剪PDF边距，移除开头和结尾的空白内容
                crop_pdf_margins(filename)
                
                logging.info(f"已保存为PDF: {filename}")
                return True
            
        except Exception as e:
            logging.error(f"保存 {url} 时出错: {str(e)}")
            # 如果不是最后一次尝试，等待一段时间再重试
            if attempt < retries - 1:
                logging.info(f"等待5秒后重试...")
                time.sleep(5)
            else:
                logging.warning(f"已达到最大重试次数，跳过此链接: {url}")
    
    return False

def sanitize_filename(filename):
    """清理文件名，移除无效字符"""
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename[:100]  # 限制文件名长度

@dataclass
class ProcessingTask:
    """处理任务数据类"""
    公众号: str
    标题: str
    链接: str
    日期: str
    文件名: str
    attempt: int = 0

class TaskQueueManager:
    """任务队列管理器"""
    def __init__(self, max_workers=1):  # 将并发数改为1以避免Playwright多线程问题
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.max_workers = max_workers
        self.workers = []
        self.completed = 0
        self.failed = 0
        self.lock = threading.Lock()
    
    def add_task(self, task: ProcessingTask):
        """添加任务到队列"""
        self.task_queue.put(task)
    
    def worker(self):
        """工作线程函数"""
        while True:
            try:
                # 从队列获取任务，超时1秒
                task = self.task_queue.get(timeout=1)
                
                # 检查是否是结束信号
                if task is None:
                    break
                
                # 处理任务
                try:
                    success = save_page_as_pdf(task.链接, task.文件名)
                    
                    with self.lock:
                        if success:
                            self.completed += 1
                            logging.info(f"处理成功: {task.标题}")
                        else:
                            self.failed += 1
                            logging.warning(f"处理失败: {task.标题}")
                except Exception as e:
                    with self.lock:
                        self.failed += 1
                    logging.error(f"处理 {task.标题} 时发生异常: {str(e)}")
                finally:
                    self.task_queue.task_done()
                    
            except queue.Empty:
                continue
    
    def start_workers(self):
        """启动工作线程"""
        for i in range(self.max_workers):
            t = threading.Thread(target=self.worker)
            t.start()
            self.workers.append(t)
    
    def stop_workers(self):
        """停止工作线程"""
        # 向队列发送结束信号
        for _ in range(self.max_workers):
            self.task_queue.put(None)
        
        # 等待所有线程结束
        for t in self.workers:
            t.join()
    
    def get_stats(self):
        """获取处理统计信息"""
        with self.lock:
            return {
                'completed': self.completed,
                'failed': self.failed,
                'pending': self.task_queue.qsize()
            }

def process_csv_with_queue(csv_file, max_workers=1):  # 将默认并发数改为1
    """使用队列管理系统处理CSV文件"""
    # 创建任务队列管理器
    queue_manager = TaskQueueManager(max_workers=max_workers)
    
    # 读取CSV文件并添加任务到队列
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                公众号 = row['公众号'].strip()
                标题 = row['标题'].strip()
                链接 = row['链接'].strip()
                日期 = row['日期'].strip()
                
                # 创建以公众号名称为名的文件夹
                公众号目录 = 公众号
                if not os.path.exists(公众号目录):
                    os.makedirs(公众号目录)
                
                # 创建安全的文件名
                safe_title = sanitize_filename(标题)
                filename = os.path.join(公众号目录, f"{日期}_{safe_title}.pdf")
                
                # 创建任务并添加到队列
                task = ProcessingTask(
                    公众号=公众号,
                    标题=标题,
                    链接=链接,
                    日期=日期,
                    文件名=filename
                )
                queue_manager.add_task(task)
    except FileNotFoundError:
        logging.error(f"找不到文件: {csv_file}")
        return
    except Exception as e:
        logging.error(f"读取CSV文件时出错: {str(e)}")
        return
    
    total_tasks = queue_manager.task_queue.qsize()
    logging.info(f"开始处理 {total_tasks} 个任务，使用 {max_workers} 个并发线程")
    
    # 启动工作线程
    queue_manager.start_workers()
    
    # 监控处理进度
    try:
        while queue_manager.task_queue.qsize() > 0:
            stats = queue_manager.get_stats()
            logging.info(f"进度: 已完成 {stats['completed']}, 失败 {stats['failed']}, 剩余 {stats['pending']}")
            time.sleep(5)  # 每5秒报告一次进度
    except KeyboardInterrupt:
        logging.info("用户中断处理过程")
    
    # 等待所有任务完成
    queue_manager.task_queue.join()
    
    # 停止工作线程
    queue_manager.stop_workers()
    
    # 最终统计
    stats = queue_manager.get_stats()
    logging.info(f"处理完成。成功: {stats['completed']}, 失败: {stats['failed']}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="将CSV文件中的链接保存为PDF文件\n\n关注公众号【小安驿站】获取更多实用工具和教程！",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用说明:
1. 准备一个CSV文件，包含以下列：公众号、标题、链接、日期
2. 脚本会自动为每个公众号创建同名文件夹
3. 文章将按"日期_标题.pdf"格式命名并保存到对应文件夹中

使用示例:
  python csv_links_to_pdf_playwright.py articles.csv
  python csv_links_to_pdf_playwright.py articles.csv --max-workers 5

注意事项:
- 确保CSV文件编码为UTF-8
- 链接必须完整包含协议(http://或https://)
- 默认使用3个并发线程，可根据需要调整
        """
    )
    parser.add_argument("csv_file", nargs='?', help="CSV文件路径")
    parser.add_argument("--max-workers", type=int, default=3, help="并发线程数 (默认: 3)")
    
    args = parser.parse_args()
    
    # 如果没有提供csv_file参数，显示帮助信息
    if not args.csv_file:
        parser.print_help()
        sys.exit(1)
    
    logging.info(f"开始处理 {args.csv_file}")
    process_csv_with_queue(args.csv_file, max_workers=args.max_workers)
    logging.info("处理完成，关注公众号【小安驿站】获取更多实用工具和教程！")
