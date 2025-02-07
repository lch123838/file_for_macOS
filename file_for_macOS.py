import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import datetime
import stat
import sys
import shutil
import zipfile
import subprocess
import threading
import logging
from PIL import Image, ImageTk
import send2trash

# 配置日志
logging.basicConfig(filename='file_manager.log', level=logging.ERROR)

class FileManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("文件管理器 - macOS")
        self.geometry("1024x768")
        
        # 请求管理员权限（需要用户输入密码）
        if os.geteuid() != 0:
            os.system(f"osascript -e 'do shell script \"python3 {__file__}\" with administrator privileges'")
            self.destroy()
            return
        
        self.current_path = "/"
        self.clipboard = None  # 用于复制/粘贴
        self.history = []  # 路径历史记录
        self.create_widgets()
        self.update_file_list()
        
    def create_widgets(self):
        # 地址栏
        self.address_frame = ttk.Frame(self)
        self.address_frame.pack(pady=5, fill=tk.X)
        
        self.back_button = ttk.Button(self.address_frame, text="← 返回", command=self.go_back)
        self.back_button.pack(side=tk.LEFT, padx=2)
        
        self.refresh_button = ttk.Button(self.address_frame, text="🔄 刷新", command=self.update_file_list)
        self.refresh_button.pack(side=tk.LEFT, padx=2)
        
        self.address_bar = ttk.Entry(self.address_frame)
        self.address_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.address_bar.bind("<Return>", self.navigate_from_address_bar)
        
        self.search_entry = ttk.Entry(self.address_frame)
        self.search_entry.pack(side=tk.LEFT, padx=2)
        self.search_button = ttk.Button(self.address_frame, text="搜索", command=self.search_files)
        self.search_button.pack(side=tk.LEFT, padx=2)
        
        # 文件列表
        self.tree = ttk.Treeview(self, columns=("大小", "类型", "修改时间", "权限"), selectmode="extended")
        self.tree.heading("#0", text="名称")
        self.tree.heading("大小", text="大小")
        self.tree.heading("类型", text="类型")
        self.tree.heading("修改时间", text="修改时间")
        self.tree.heading("权限", text="权限")
        
        self.tree.column("#0", width=300)
        self.tree.column("大小", width=100)
        self.tree.column("类型", width=100)
        self.tree.column("修改时间", width=150)
        self.tree.column("权限", width=100)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_double_click)
        
        # 右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="打开", command=self.open_selected)
        self.context_menu.add_command(label="以最高权限打开", command=self.open_selected_as_admin)
        self.context_menu.add_command(label="在访达中打开", command=self.open_in_finder)
        self.context_menu.add_command(label="复制", command=self.copy_selected)
        self.context_menu.add_command(label="复制绝对路径", command=self.copy_absolute_path)
        self.context_menu.add_command(label="粘贴", command=self.paste_clipboard)
        self.context_menu.add_command(label="删除", command=self.delete_selected)
        self.context_menu.add_command(label="重命名", command=self.rename_selected)
        self.context_menu.add_command(label="压缩", command=self.compress_selected)
        self.context_menu.add_command(label="解压", command=self.extract_selected)
        
        # 绑定右键点击事件
        if sys.platform == "darwin":
            self.tree.bind("<Button-2>", self.show_context_menu)  # macOS 右键
        else:
            self.tree.bind("<Button-3>", self.show_context_menu)  # Windows/Linux 右键
        
        # 详细信息
        self.details_text = tk.Text(self, height=8)
        self.details_text.pack(fill=tk.X)
        
        # 文件预览
        self.preview_frame = ttk.Frame(self)
        self.preview_frame.pack(fill=tk.X, pady=5)
        self.preview_label = ttk.Label(self.preview_frame, text="文件预览")
        self.preview_label.pack()
        
        # 快捷键
        self.bind("<Control-c>", lambda e: self.copy_selected())
        self.bind("<Control-v>", lambda e: self.paste_clipboard())
        self.bind("<F5>", lambda e: self.update_file_list())
        self.bind("<Delete>", lambda e: self.delete_selected())
        
    def update_file_list(self):
        self.tree.delete(*self.tree.get_children())
        self.address_bar.delete(0, tk.END)
        self.address_bar.insert(0, self.current_path)
        
        try:
            for item in sorted(os.listdir(self.current_path)):
                full_path = os.path.join(self.current_path, item)
                try:
                    stat_info = os.stat(full_path, follow_symlinks=False)
                    
                    # 跳过无法访问的文件
                    if not os.path.exists(full_path):
                        continue
                        
                    # 获取文件类型
                    file_type = "文件夹" if os.path.isdir(full_path) else "文件"
                    
                    # 获取修改时间
                    mtime = datetime.datetime.fromtimestamp(stat_info.st_mtime)
                    
                    # 获取权限
                    permissions = stat.filemode(stat_info.st_mode)
                    
                    # 获取大小
                    size = self.convert_size(stat_info.st_size) if not os.path.isdir(full_path) else "--"
                    
                    # 颜色区分
                    tag = ""
                    if item.startswith("."):
                        tag = "hidden_folder" if os.path.isdir(full_path) else "hidden_file"
                    else:
                        tag = "folder" if os.path.isdir(full_path) else "file"
                    
                    self.tree.insert("", "end", text=item, values=(
                        size,
                        file_type,
                        mtime.strftime("%Y-%m-%d %H:%M:%S"),
                        permissions
                    ), tags=(tag,))
                except (FileNotFoundError, PermissionError) as e:
                    logging.error(f"跳过 {item}: {str(e)}")
        except PermissionError:
            messagebox.showerror("权限不足", "您没有权限访问此目录")
        
        # 设置颜色
        self.tree.tag_configure("folder", background="#7f7f00")
        self.tree.tag_configure("file", background="#000000")
        self.tree.tag_configure("hidden_folder", background="#7f0000")
        self.tree.tag_configure("hidden_file", background="#7f007f")
            
    def convert_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"
    
    def on_double_click(self, event):
        item = self.tree.selection()[0]
        name = self.tree.item(item, "text")
        new_path = os.path.join(self.current_path, name)
        try:
            if os.path.isdir(new_path):
                self.current_path = new_path
                self.update_file_list()
            else:
                self.open_selected()
        except PermissionError:
            messagebox.showerror("错误", "无法访问此目录")
            
    def navigate_from_address_bar(self, event):
        path = self.address_bar.get()
        if os.path.exists(path):
            self.current_path = os.path.abspath(path)
            self.update_file_list()
        else:
            messagebox.showerror("错误", "路径无效")
            
    def go_back(self):
        parent_dir = os.path.dirname(self.current_path)
        if parent_dir != self.current_path:  # 防止根目录无限循环
            self.current_path = parent_dir
            self.update_file_list()
            
    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
            
    def delete_selected(self):
        items = self.tree.selection()
        if not items:
            return
        
        if not messagebox.askyesno("确认删除", "确定要删除选中的文件吗？"):
            return
        
        for item in items:
            name = self.tree.item(item, "text")
            full_path = os.path.join(self.current_path, name)
            try:
                send2trash.send2trash(full_path)  # 使用回收站
            except Exception as e:
                messagebox.showerror("错误", f"删除失败: {str(e)}")
        self.update_file_list()
            
    def rename_selected(self):
        item = self.tree.selection()[0]
        old_name = self.tree.item(item, "text")
        new_name = simpledialog.askstring("重命名", "输入新名称:", initialvalue=old_name)
        if new_name:
            old_path = os.path.join(self.current_path, old_name)
            new_path = os.path.join(self.current_path, new_name)
            try:
                os.rename(old_path, new_path)
                self.update_file_list()
            except Exception as e:
                messagebox.showerror("错误", f"重命名失败: {str(e)}")
    
    def copy_selected(self):
        items = self.tree.selection()
        if not items:
            return
        
        self.clipboard = [os.path.join(self.current_path, self.tree.item(item, "text")) for item in items]
        messagebox.showinfo("复制", f"已复制 {len(self.clipboard)} 个文件/文件夹")
    
    def copy_absolute_path(self):
        items = self.tree.selection()
        if not items:
            return
        
        paths = [os.path.join(self.current_path, self.tree.item(item, "text")) for item in items]
        self.clipboard_clear()
        self.clipboard_append("\n".join(paths))
        messagebox.showinfo("复制绝对路径", f"已复制 {len(paths)} 个路径")
    
    def paste_clipboard(self):
        if not self.clipboard:
            messagebox.showwarning("粘贴", "剪贴板为空")
            return
        
        for src in self.clipboard:
            dest = os.path.join(self.current_path, os.path.basename(src))
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)
            except Exception as e:
                messagebox.showerror("错误", f"粘贴失败: {str(e)}")
        self.update_file_list()
    
    def compress_selected(self):
        items = self.tree.selection()
        if not items:
            return
        
        zip_path = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP 文件", "*.zip")])
        if not zip_path:
            return
        
        def _compress_task():
            try:
                with zipfile.ZipFile(zip_path, "w") as zipf:
                    for item in items:
                        full_path = os.path.join(self.current_path, self.tree.item(item, "text"))
                        if os.path.isdir(full_path):
                            for root, dirs, files in os.walk(full_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, start=full_path)
                                    zipf.write(file_path, arcname)
                        else:
                            zipf.write(full_path, os.path.basename(full_path))
                messagebox.showinfo("压缩", f"已压缩到: {zip_path}")
            except Exception as e:
                messagebox.showerror("错误", f"压缩失败: {str(e)}")
        
        threading.Thread(target=_compress_task).start()
    
    def extract_selected(self):
        items = self.tree.selection()
        if not items:
            return
        
        extract_path = filedialog.askdirectory()
        if not extract_path:
            return
        
        def _extract_task():
            try:
                for item in items:
                    full_path = os.path.join(self.current_path, self.tree.item(item, "text"))
                    with zipfile.ZipFile(full_path, "r") as zipf:
                        zipf.extractall(extract_path)
                messagebox.showinfo("解压", f"已解压到: {extract_path}")
            except Exception as e:
                messagebox.showerror("错误", f"解压失败: {str(e)}")
        
        threading.Thread(target=_extract_task).start()
    
    def open_selected(self):
        items = self.tree.selection()
        if not items:
            return
        
        for item in items:
            full_path = os.path.join(self.current_path, self.tree.item(item, "text"))
            try:
                if sys.platform == "darwin":
                    subprocess.run(["open", full_path])
                elif sys.platform == "win32":
                    os.startfile(full_path)
                else:
                    subprocess.run(["xdg-open", full_path])
            except Exception as e:
                messagebox.showerror("错误", f"打开失败: {str(e)}")
    
    def open_selected_as_admin(self):
        items = self.tree.selection()
        if not items:
            return
        
        for item in items:
            full_path = os.path.join(self.current_path, self.tree.item(item, "text"))
            try:
                if sys.platform == "darwin":
                    subprocess.run(["sudo", "open", full_path])
                elif sys.platform == "win32":
                    subprocess.run(["runas", "/user:Administrator", full_path])
                else:
                    subprocess.run(["sudo", "xdg-open", full_path])
            except Exception as e:
                messagebox.showerror("错误", f"以最高权限打开失败: {str(e)}")
    
    def open_in_finder(self):
        items = self.tree.selection()
        if not items:
            return
        
        for item in items:
            full_path = os.path.join(self.current_path, self.tree.item(item, "text"))
            try:
                if sys.platform == "darwin":
                    subprocess.run(["open", "-R", full_path])
                elif sys.platform == "win32":
                    subprocess.run(["explorer", "/select,", full_path])
                else:
                    subprocess.run(["xdg-open", os.path.dirname(full_path)])
            except Exception as e:
                messagebox.showerror("错误", f"在访达中打开失败: {str(e)}")
    
    def search_files(self):
        keyword = self.search_entry.get()
        if not keyword:
            return
        
        results = []
        for root, dirs, files in os.walk(self.current_path):
            for item in dirs + files:
                if keyword.lower() in item.lower():
                    results.append(os.path.join(root, item))
        
        if results:
            messagebox.showinfo("搜索结果", f"找到 {len(results)} 个结果:\n" + "\n".join(results))
        else:
            messagebox.showinfo("搜索结果", "未找到匹配的文件或文件夹。")

if __name__ == "__main__":
    app = FileManager()
    app.mainloop()