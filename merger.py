import os
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinter import filedialog, Listbox
from PyPDF2 import PdfMerger
import threading
import time

# ---------- THEME ----------
ctk.set_appearance_mode("Dark")

PRIMARY = "#6366F1"
ACCENT = "#7C3AED"
CARD_BG = "#0F172A"
APP_BG = "#020617"
TEXT_MUTED = "#94A3B8"

class PDFMergerApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()

        self.title("PDF Merger")
        self.geometry("760x680")
        self.resizable(False, False)
        self.configure(bg=APP_BG)

        self.files = []

        # ---------- HEADER ----------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(pady=(20, 10))

        ctk.CTkLabel(header, text="📄 PDF Merger", font=("Segoe UI", 26, "bold")).pack()
        self.subtitle = ctk.CTkLabel(
            header,
            text="Merge your PDF files in seconds",
            font=("Segoe UI", 14),
            text_color=TEXT_MUTED
        )
        self.subtitle.pack()

        # ---------- DROP CARD ----------
        drop_card = ctk.CTkFrame(
            self, width=700, height=180,
            corner_radius=18, fg_color=CARD_BG,
            border_width=2, border_color=PRIMARY
        )
        drop_card.pack(pady=15)
        drop_card.pack_propagate(False)

        ctk.CTkLabel(
            drop_card,
            text="📥 Drag & Drop PDF files here\nor use Add PDFs",
            font=("Segoe UI", 16),
            justify="center"
        ).pack(expand=True)

        drop_card.drop_target_register(DND_FILES)
        drop_card.dnd_bind("<<Drop>>", self.drop_files)

        # ---------- FILE LIST CARD ----------
        list_card = ctk.CTkFrame(
            self, width=700, height=210,
            corner_radius=18, fg_color=CARD_BG
        )
        list_card.pack(pady=10)
        list_card.pack_propagate(False)

        top_row = ctk.CTkFrame(list_card, fg_color="transparent")
        top_row.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(
            top_row,
            text="📑 Selected Files (drag to reorder)",
            font=("Segoe UI", 15, "bold")
        ).pack(side="left")

        reorder_frame = ctk.CTkFrame(top_row, fg_color="transparent")
        reorder_frame.pack(side="right")

        ctk.CTkButton(reorder_frame, text="↑", width=40, command=self.move_up).pack(side="left", padx=4)
        ctk.CTkButton(reorder_frame, text="↓", width=40, command=self.move_down).pack(side="left", padx=4)

        # ✅ REAL LISTBOX (Tkinter)
        self.listbox = Listbox(
            list_card,
            height=7,
            bg="#020617",
            fg="white",
            selectbackground=PRIMARY,
            highlightthickness=0,
            borderwidth=0,
            font=("Segoe UI", 12),
            cursor="hand2"
        )
        self.listbox.pack(fill="x", padx=15, pady=(0, 10))
        self.listbox.bind("<Button-1>", self.on_drag_start)
        self.listbox.bind("<B1-Motion>", self.on_drag_motion)

        # ---------- PROGRESS ----------
        self.progress = ctk.CTkProgressBar(self, width=700)
        self.progress.set(0)
        self.progress.pack(pady=(10, 0))

        # ---------- ACTION BAR ----------
        action_bar = ctk.CTkFrame(self, height=80, fg_color=APP_BG)
        action_bar.pack(side="bottom", fill="x")

        left_actions = ctk.CTkFrame(action_bar, fg_color="transparent")
        left_actions.pack(side="left", padx=20)

        self.add_btn = ctk.CTkButton(
            left_actions, text="+ Add PDFs",
            width=150, height=42,
            fg_color=PRIMARY,
            hover_color="#4F46E5",
            font=("Segoe UI", 14),
            command=self.add_pdfs
        )
        self.add_btn.pack(side="left", padx=10)

        self.clear_btn = ctk.CTkButton(
            left_actions, text="Clear",
            width=120, height=42,
            fg_color="#334155",
            hover_color="#475569",
            font=("Segoe UI", 14),
            command=self.clear_files
        )
        self.clear_btn.pack(side="left", padx=10)

        right_actions = ctk.CTkFrame(action_bar, fg_color="transparent")
        right_actions.pack(side="right", padx=20)

        self.merge_btn = ctk.CTkButton(
            right_actions, text="Merge PDFs",
            width=220, height=48,
            fg_color=ACCENT,
            hover_color="#6D28D9",
            font=("Segoe UI", 16, "bold"),
            command=self.start_merge,
            state="disabled"
        )
        self.merge_btn.pack()

    # ---------- FILE HANDLING ----------
    def add_pdfs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")])
        for f in files:
            if f not in self.files:
                self.files.append(f)
        self.update_list()

    def drop_files(self, event):
        for f in self.tk.splitlist(event.data):
            if f.lower().endswith(".pdf") and f not in self.files:
                self.files.append(f)
        self.update_list()

    def update_list(self):
        self.listbox.delete(0, "end")
        for f in self.files:
            self.listbox.insert("end", os.path.basename(f))
        # ---------- Merge button enabled if >=2 files ----------
        self.merge_btn.configure(state="normal" if len(self.files) >= 2 else "disabled")

    def clear_files(self):
        self.files.clear()
        self.listbox.delete(0, "end")
        self.progress.set(0)
        self.merge_btn.configure(state="disabled")

    # ---------- REORDER ----------
    def move_up(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self.files[i-1], self.files[i] = self.files[i], self.files[i-1]
        self.update_list()
        self.listbox.select_set(i-1)

    def move_down(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] == len(self.files) - 1:
            return
        i = sel[0]
        self.files[i+1], self.files[i] = self.files[i], self.files[i+1]
        self.update_list()
        self.listbox.select_set(i+1)

    # ---------- DRAG REORDER ----------
    def on_drag_start(self, event):
        self.drag_index = self.listbox.nearest(event.y)

    def on_drag_motion(self, event):
        new_index = self.listbox.nearest(event.y)
        if new_index != self.drag_index:
            self.files[self.drag_index], self.files[new_index] = self.files[new_index], self.files[self.drag_index]
            self.update_list()
            self.listbox.select_set(new_index)
            self.drag_index = new_index

    # ---------- MERGE ----------
    def start_merge(self):
        if len(self.files) < 2:
            return
        output = filedialog.asksaveasfilename(defaultextension=".pdf")
        if not output:
            return
        threading.Thread(target=self.merge_pdfs, args=(output,), daemon=True).start()

    def merge_pdfs(self, output):
        try:
            merger = PdfMerger()
            total = len(self.files)

            for i, f in enumerate(self.files):
                merger.append(f)
                self.progress.set((i+1)/total)
                # ---------- Animated progress text ----------
                self.subtitle.configure(text=f"Merging {i+1} of {total} PDFs...")
                self.update()
                time.sleep(0.1)

            merger.write(output)
            merger.close()
            # ---------- Toast-style success ----------
            self.subtitle.configure(text="✅ PDFs merged successfully!")
            self.progress.set(1.0)
            self.after(3000, lambda: self.subtitle.configure(text="Merge your PDF files in seconds"))
        except Exception as e:
            self.subtitle.configure(text=f"❌ Error: {str(e)}")
            self.progress.set(0)


if __name__ == "__main__":
    app = PDFMergerApp()
    app.mainloop()
