#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微信文章批量转PDF工具 - CustomTkinter GUI版本

作者：小安
公众号：小安驿站
版本：1.0.0
功能：提供图形界面让用户选择CSV文件和保存目录，然后批量转换微信文章为PDF文件

关注公众号【小安驿站】获取更多实用工具和教程！
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import sys
import logging
from csv_links_to_pdf_playwright import process_csv_with_queue

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

class WeChatDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 配置窗口
        self.title("微信文章批量转PDF工具 - CustomTkinter版")
        self.geometry("700x600")
        self.minsize(600, 500)
        
        # 设置外观模式和主题
        ctk.set_appearance_mode("system")  # 使用系统设置的外观模式
        ctk.set_default_color_theme("blue")  # 设置主题色
        
        # 初始化变量
        self.csv_file_path = ctk.StringVar()
        self.output_dir_path = ctk.StringVar()
        self.max_workers = ctk.IntVar(value=3)
        self.is_processing = False
        
        # 创建界面
        self.create_widgets()
        
        # 居中显示窗口
        self.center_window()
        
    def center_window(self):
        """将窗口居中显示"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 标题
        title_label = ctk.CTkLabel(main_frame, text="微信文章批量转PDF工具", 
                                  font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=(10, 20))
        
        # 文件选择区域
        file_frame = ctk.CTkFrame(main_frame)
        file_frame.pack(fill="x", padx=20, pady=10)
        
        # CSV文件选择
        csv_label = ctk.CTkLabel(file_frame, text="选择CSV文件:", 
                                font=ctk.CTkFont(size=14, weight="bold"))
        csv_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        csv_select_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
        csv_select_frame.pack(fill="x", padx=10, pady=5)
        
        self.csv_entry = ctk.CTkEntry(csv_select_frame, textvariable=self.csv_file_path)
        self.csv_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        csv_browse_btn = ctk.CTkButton(csv_select_frame, text="浏览...", 
                                      command=self.browse_csv_file, width=80)
        csv_browse_btn.pack(side="right")
        
        # 输出目录选择
        output_label = ctk.CTkLabel(file_frame, text="选择输出目录:", 
                                   font=ctk.CTkFont(size=14, weight="bold"))
        output_label.pack(anchor="w", padx=10, pady=(15, 5))
        
        output_select_frame = ctk.CTkFrame(file_frame, fg_color="transparent")
        output_select_frame.pack(fill="x", padx=10, pady=5)
        
        self.output_entry = ctk.CTkEntry(output_select_frame, textvariable=self.output_dir_path)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        output_browse_btn = ctk.CTkButton(output_select_frame, text="浏览...", 
                                         command=self.browse_output_dir, width=80)
        output_browse_btn.pack(side="right")
        
        # 参数设置区域
        params_frame = ctk.CTkFrame(main_frame)
        params_frame.pack(fill="x", padx=20, pady=10)
        
        params_label = ctk.CTkLabel(params_frame, text="参数设置:", 
                                   font=ctk.CTkFont(size=14, weight="bold"))
        params_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # 并发线程数设置
        workers_frame = ctk.CTkFrame(params_frame, fg_color="transparent")
        workers_frame.pack(fill="x", padx=10, pady=10)
        
        workers_label = ctk.CTkLabel(workers_frame, text="并发线程数:")
        workers_label.pack(side="left", padx=(0, 10))
        
        workers_slider = ctk.CTkSlider(workers_frame, from_=1, to=10, 
                                      variable=self.max_workers, 
                                      number_of_steps=9, width=200)
        workers_slider.pack(side="left", padx=(0, 10))
        
        self.workers_value_label = ctk.CTkLabel(workers_frame, text=str(self.max_workers.get()))
        self.workers_value_label.pack(side="left")
        
        # 绑定滑块值变化事件
        workers_slider.configure(command=self.update_workers_value)
        
        # 操作按钮区域
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.process_btn = ctk.CTkButton(button_frame, text="开始处理", 
                                        command=self.start_processing,
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        height=40)
        self.process_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        exit_btn = ctk.CTkButton(button_frame, text="退出", 
                                command=self.quit_application,
                                height=40)
        exit_btn.pack(side="right", padx=(10, 0))
        
        # 日志显示区域
        log_frame = ctk.CTkFrame(main_frame)
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        log_label = ctk.CTkLabel(log_frame, text="处理日志:", 
                                font=ctk.CTkFont(size=14, weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # 创建文本框和滚动条来显示日志
        log_text_frame = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.log_text = ctk.CTkTextbox(log_text_frame, height=150, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        
        log_scrollbar = ctk.CTkScrollbar(log_text_frame, command=self.log_text.yview)
        log_scrollbar.pack(side="right", fill="y")
        
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        # 添加版权信息
        copyright_label = ctk.CTkLabel(main_frame, 
                                      text="关注公众号【小安驿站】获取更多实用工具和教程！",
                                      font=ctk.CTkFont(size=12))
        copyright_label.pack(pady=(0, 10))
        
    def update_workers_value(self, value):
        """更新并发线程数显示值"""
        self.workers_value_label.configure(text=str(int(value)))
        self.max_workers.set(int(value))
        
    def browse_csv_file(self):
        """浏览并选择CSV文件"""
        file_path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if file_path:
            self.csv_file_path.set(file_path)
            
    def browse_output_dir(self):
        """浏览并选择输出目录"""
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir_path.set(dir_path)
            
    def append_log(self, message):
        """向日志文本框添加消息"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")  # 滚动到最后一行
        
    def start_processing(self):
        """开始处理CSV文件"""
        if self.is_processing:
            messagebox.showwarning("警告", "正在处理中，请稍候...")
            return
            
        csv_file = self.csv_file_path.get()
        output_dir = self.output_dir_path.get()
        
        # 检查必要参数
        if not csv_file:
            messagebox.showerror("错误", "请选择CSV文件")
            return
            
        if not os.path.exists(csv_file):
            messagebox.showerror("错误", "选择的CSV文件不存在")
            return
            
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return
            
        if not os.path.exists(output_dir):
            messagebox.showerror("错误", "选择的输出目录不存在")
            return
            
        # 在新线程中开始处理
        self.is_processing = True
        self.process_btn.configure(text="处理中...", state="disabled")
        
        # 启动处理线程，并传递输出目录参数
        processing_thread = threading.Thread(
            target=self.process_csv,
            args=(csv_file, self.max_workers.get(), output_dir),
            daemon=True
        )
        processing_thread.start()
        
    def process_csv(self, csv_file, max_workers, output_dir):
        """在后台线程中处理CSV文件"""
        try:
            self.append_log(f"开始处理 {csv_file}")
            self.append_log(f"使用 {max_workers} 个并发线程")
            self.append_log(f"输出目录: {output_dir}")
            
            # 记录当前工作目录并切换到输出目录
            original_cwd = os.getcwd()
            os.chdir(output_dir)
            
            # 调用原有的处理函数
            stats = process_csv_with_queue(csv_file, max_workers=max_workers)
            
            # 恢复原来的工作目录
            os.chdir(original_cwd)
            
            if stats:
                self.append_log(f"处理完成。成功: {stats['completed']}, 失败: {stats['failed']}")
            else:
                self.append_log("处理完成")
                
        except Exception as e:
            self.append_log(f"处理过程中发生错误: {str(e)}")
            logging.error(f"处理过程中发生错误: {str(e)}")
        finally:
            # 恢复按钮状态
            self.after(0, self.reset_process_button)
            
    def reset_process_button(self):
        """重置处理按钮状态"""
        self.is_processing = False
        self.process_btn.configure(text="开始处理", state="normal")
        
    def quit_application(self):
        """退出应用程序"""
        if self.is_processing:
            if messagebox.askyesno("确认", "正在处理中，确定要退出吗？"):
                self.destroy()
        else:
            self.destroy()


def main():
    """主函数"""
    app = WeChatDownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()