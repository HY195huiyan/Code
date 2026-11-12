import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from collections import defaultdict
import threading
import queue

class DuplicateFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("同名文件筛查工具")
        self.root.geometry("1100x750")
        self.root.configure(bg="#F5F7FA")
        
        self.display_cache = {}  
        self.is_scanning = False
        self.result_queue = queue.Queue()

        # ================= 统一样式设置 =================
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.style.configure("Custom.Treeview", 
                             background="#FFFFFF", 
                             foreground="#333333", 
                             rowheight=32, 
                             fieldbackground="#FFFFFF",
                             borderwidth=0,
                             font=("Microsoft YaHei", 9))
        
        self.style.layout("Custom.Treeview", [('Custom.Treeview.treearea', {'sticky': 'nswe'})])
        self.style.configure("Vertical.TScrollbar", gripcount=0, background="#D3D3D3", darkcolor="#F5F7FA", lightcolor="#F5F7FA", troughcolor="#F5F7FA", bordercolor="#F5F7FA", arrowcolor="#999999")

        # ================= 顶部设置区 =================
        frame_top = tk.Frame(root, bg="#F5F7FA", pady=15, padx=15)
        frame_top.pack(fill=tk.X)

        tk.Label(frame_top, text="扫描路径:", bg="#F5F7FA", font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar(value=r"Z:\int12\GameArt")
        entry_path = tk.Entry(frame_top, textvariable=self.path_var, width=70, font=("Consolas", 10), bd=0, highlightthickness=1, highlightbackground="#D1D5DB", highlightcolor="#3B82F6")
        entry_path.grid(row=0, column=1, padx=10, pady=5, ipady=4)
        
        btn_browse = tk.Button(frame_top, text="浏览...", command=self.browse_folder, bg="#E5E7EB", fg="#374151", relief="flat", font=("Microsoft YaHei", 9), padx=10, cursor="hand2")
        btn_browse.grid(row=0, column=2)

        # 筛选行
        frame_filter = tk.Frame(frame_top, bg="#F5F7FA")
        frame_filter.grid(row=1, column=0, columnspan=3, sticky="w", pady=(15,0))
        
        tk.Label(frame_filter, text="筛选文件名:", bg="#F5F7FA", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_entry = tk.Entry(frame_filter, textvariable=self.filter_var, width=40, font=("Consolas", 10), bd=0, highlightthickness=1, highlightbackground="#D1D5DB", highlightcolor="#3B82F6")
        self.filter_entry.pack(side=tk.LEFT, padx=10, ipady=4)
        self.filter_entry.bind("<Return>", lambda event: self.refresh_filter())
        
        self.refresh_btn = tk.Button(frame_filter, text="🔄 刷新筛选", command=self.refresh_filter, bg="#3B82F6", fg="white", relief="flat", font=("Microsoft YaHei", 9, "bold"), padx=15, cursor="hand2")
        self.refresh_btn.pack(side=tk.LEFT)

        # ================= 按钮区 =================
        frame_btn = tk.Frame(root, bg="#F5F7FA", pady=10)
        frame_btn.pack(fill=tk.X)
        
        self.scan_btn = tk.Button(frame_btn, text="▶ 开始扫描目录", command=self.start_scan_thread, bg="#10B981", fg="white", relief="flat", font=("Microsoft YaHei", 11, "bold"), padx=20, pady=5, cursor="hand2")
        self.scan_btn.pack(side=tk.LEFT, padx=15)
        
        btn_copy = tk.Button(frame_btn, text="复制所有结果", command=self.copy_all_to_clipboard, bg="#F59E0B", fg="white", relief="flat", font=("Microsoft YaHei", 10), padx=15, pady=5, cursor="hand2")
        btn_copy.pack(side=tk.LEFT, padx=5)
        
        btn_clear = tk.Button(frame_btn, text="清空", command=self.clear_results, bg="#EF4444", fg="white", relief="flat", font=("Microsoft YaHei", 10), padx=15, pady=5, cursor="hand2")
        btn_clear.pack(side=tk.LEFT, padx=5)

        # ================= 结果主展示区 =================
        frame_tree = tk.Frame(root, bg="#FFFFFF", bd=1, relief="solid", highlightbackground="#E5E7EB")
        frame_tree.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        self.tree = ttk.Treeview(frame_tree, columns=("info",), show="tree", selectmode="browse", style="Custom.Treeview")
        
        # 既然子节点也是树形结构，我们把 #0 列（文件名列）在子节点时收缩
        self.tree.column("#0", width=350, minwidth=250, stretch=False) 
        self.tree.column("info", width=700, stretch=True)
        
        self.tree.tag_configure("filename_tag", font=("Microsoft YaHei", 10, "bold"), foreground="#1F2937")
        self.tree.tag_configure("path_tag", font=("Consolas", 9), foreground="#4B5563")
        
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        
        tree_scroll = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ================= 状态栏 =================
        self.status_var = tk.StringVar(value="准备就绪。点击路径可快速复制。")
        status_label = tk.Label(root, textvariable=self.status_var, bg="#E5E7EB", fg="#4B5563", font=("Microsoft YaHei", 9), anchor="w", padx=15, pady=5)
        status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.poll_status()

    def on_tree_double_click(self, event):
        item = self.tree.focus()
        if item and self.tree.get_children(item):
            self.tree.item(item, open=not self.tree.item(item, "open"))

    def on_tree_click(self, event):
        """左键单击任意区域，智能识别是否点击了路径子节点并复制"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
            
        parent = self.tree.parent(item)
        if parent: # 如果有父节点，说明点击的是路径（子节点）
            # 获取该行单元格显示的完整文本
            cell_values = self.tree.item(item, "values")
            if cell_values:
                path_text = cell_values[0]
                
                # 关键优化：用正则表达式或字符串拼接安全剥离前缀
                # 形如 "[12.50 MB]   Z:\int12\GameArt\..." 或 "[未知大小]   D:\..."
                try:
                    # 寻找第一个 "]" 字符，截取后面的所有内容
                    clean_path = path_text.split("]", 1)[1].strip()
                    
                    # 复制到剪贴板
                    self.root.clipboard_clear()
                    self.root.clipboard_append(clean_path)
                    
                    display_path = clean_path if len(clean_path) < 60 else clean_path[:57] + "..."
                    self.status_var.set(f"📋 已复制路径: {display_path}")
                except IndexError:
                    pass

    def browse_folder(self):
        folder_selected = filedialog.askdirectory(initialdir=self.path_var.get())
        if folder_selected:
            self.path_var.set(folder_selected)

    def start_scan_thread(self):
        self.clear_results()
        self.is_scanning = True
        self.scan_btn.config(state=tk.DISABLED, text="⏳ 正在查找...", bg="#9CA3AF")
        self.status_var.set("🔍 正在查找中，请稍候...")
        
        self.result_queue = queue.Queue()
        threading.Thread(target=self.scan_files_worker, daemon=True).start()

    def poll_status(self):
        if self.is_scanning:
            try:
                data = self.result_queue.get_nowait()
                if data[0] == "DONE":
                    self.finish_scan(data[1])
                elif data[0] == "ERROR":
                    self.show_error(data[1])
            except queue.Empty:
                pass
        
        self.root.after(1000, self.poll_status)

    def scan_files_worker(self):
        root_dir = self.path_var.get()
        if not os.path.exists(root_dir):
            self.result_queue.put(("ERROR", "路径不存在"))
            return

        file_dict = defaultdict(list)
        try:
            for dirpath, _, filenames in os.walk(root_dir):
                for filename in filenames:
                    full_path = os.path.join(dirpath, filename)
                    file_key = filename.lower() 
                    file_dict[file_key].append(full_path)
            
            duplicates = {k: v for k, v in file_dict.items() if len(v) > 1}
            self.result_queue.put(("DONE", duplicates))
            
        except Exception as e:
            self.result_queue.put(("ERROR", str(e)))

    def finish_scan(self, duplicates):
        self.is_scanning = False
        self.display_cache = duplicates
        self.scan_btn.config(state=tk.NORMAL, text="▶ 开始扫描目录", bg="#10B981")
        
        self.status_var.set(f"✅ 查找完成！共找到 {len(self.display_cache)} 组同名文件。点击任意路径可复制。")
        self.render_display()

    def refresh_filter(self):
        if not self.display_cache:
            self.status_var.set("暂无数据可筛选。")
            return
        self.render_display()
        self.status_var.set(f"✅ 筛选已刷新。")

    def render_display(self):
        search_text = self.filter_var.get().strip().lower()
        current_scroll = self.tree.yview()[0]
        
        for item in self.tree.get_children():
            self.tree.delete(item)

        filtered_duplicates = {}
        for name, paths in self.display_cache.items():
            if search_text in name:
                filtered_duplicates[name] = paths

        if not filtered_duplicates:
            self.tree.insert("", "end", text="  没有找到符合条件的重复同名文件。", tags=("path_tag",))
        else:
            for name, paths in sorted(filtered_duplicates.items()):
                parent_id = self.tree.insert("", "end", text=f" 📄 {name}", open=True, values=("",), tags=("filename_tag",))
                
                for p in paths:
                    try:
                        size_mb = os.path.getsize(p) / (1024 * 1024)
                        info_text = f"[{size_mb:.2f} MB]   {p}"
                    except:
                        info_text = f"[未知大小]   {p}"
                    
                    self.tree.insert(parent_id, "end", text="", values=(info_text,), tags=("path_tag",))

        self.root.update_idletasks()
        self.tree.yview_moveto(current_scroll)

    def clear_results(self):
        self.is_scanning = False
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.filter_var.set("") 
        self.display_cache = {}
        self.status_var.set("准备就绪。点击路径可快速复制。")
        self.scan_btn.config(state=tk.NORMAL, text="▶ 开始扫描目录", bg="#10B981")

    def copy_all_to_clipboard(self):
        output_text = ""
        for item in self.tree.get_children():
            name = self.tree.item(item, "text").replace("📄 ", "")
            if not name or "没有找到" in name:
                continue
            output_text += f"【文件名】: {name}\n"
            for child in self.tree.get_children(item):
                path = self.tree.item(child, "values")[0]
                output_text += f"   └─ {path}\n"
            output_text += "\n"
            
        if output_text:
            self.root.clipboard_clear()
            self.root.clipboard_append(output_text)
            self.status_var.set("✅ 已复制全部结果到剪贴板！")
        else:
            self.status_var.set("没有内容可复制。")

    def show_error(self, msg):
        self.is_scanning = False
        self.scan_btn.config(state=tk.NORMAL, text="▶ 开始扫描目录", bg="#10B981")
        self.status_var.set("发生错误")
        messagebox.showerror("错误", msg)

if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateFinderApp(root)
    root.mainloop()
