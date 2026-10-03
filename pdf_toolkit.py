"""
PDF Toolkit - Merge, Split, Page Editor (reorder/delete/rotate/extract), Compress, Themes.

Install:  pip install customtkinter tkinterdnd2 pypdf pillow pymupdf
"""
import pymupdf
import os
import queue
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox, Listbox
from tkinterdnd2 import TkinterDnD, DND_FILES

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # fallback to old library
    from PyPDF2 import PdfReader, PdfWriter

try:
    import PIL  # noqa: F401
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

try:
    import fitz  # PyMuPDF - used only for the page preview
    HAVE_FITZ = True
except ImportError:
    HAVE_FITZ = False

# ---------- THEMES ----------
THEMES = {
    "Graphite":    dict(mode="Dark", primary="#6366F1", hover="#5558E6", card="#111113", bg="#09090B",
                        list_bg="#0C0C0E", border="#27272A", muted="#A1A1AA", neutral="#1C1C1F",
                        neutral_hover="#27272A", text="#FAFAFA"),
    "Midnight":    dict(mode="Dark", primary="#3B82F6", hover="#2F6FDB", card="#0F141F", bg="#0A0D14",
                        list_bg="#0B1019", border="#1F2937", muted="#8B98AD", neutral="#172033",
                        neutral_hover="#1F2B42", text="#F1F5F9"),
    "Emerald":     dict(mode="Dark", primary="#10B981", hover="#0EA371", card="#0E1311", bg="#080B0A",
                        list_bg="#0A0E0C", border="#1F2A25", muted="#8FA69B", neutral="#16201C",
                        neutral_hover="#1F2D27", text="#F0FDF4"),
    "Ember":       dict(mode="Dark", primary="#F97316", hover="#E5650D", card="#141110", bg="#0B0908",
                        list_bg="#0E0B0A", border="#292321", muted="#A8998F", neutral="#1E1917",
                        neutral_hover="#2A2320", text="#FAF5F0"),
    # ----- premium -----
    "★ Obsidian Gold": dict(mode="Dark", primary="#B8892B", hover="#A07622", card="#0F0E0C", bg="#070707",
                            list_bg="#0A0A09", border="#2E2717", muted="#A89F8A", neutral="#17150F",
                            neutral_hover="#241F14", text="#F5F0E6"),
    "★ Royal Amethyst": dict(mode="Dark", primary="#8B5CF6", hover="#7C3AED", card="#120D1C", bg="#0A0710",
                             list_bg="#0D0916", border="#2A1F3D", muted="#A59BBB", neutral="#1A1327",
                             neutral_hover="#261B38", text="#F3EEFB"),
    "★ Aurora Teal":   dict(mode="Dark", primary="#0EA5B7", hover="#0C8E9E", card="#0A1519", bg="#050B0D",
                            list_bg="#071013", border="#16303A", muted="#86A9B3", neutral="#0F1F25",
                            neutral_hover="#16303A", text="#ECFEFF"),
    "★ Rose Gold":     dict(mode="Dark", primary="#B76E79", hover="#A05C67", card="#161010", bg="#0C0808",
                            list_bg="#100B0B", border="#2E1F1F", muted="#B09A9A", neutral="#1E1515",
                            neutral_hover="#2C1F1F", text="#FBF1F1"),
    "★ Platinum":      dict(mode="Light", primary="#1C1917", hover="#44403C", card="#FFFFFF", bg="#F5F5F4",
                            list_bg="#FAFAF9", border="#E7E5E4", muted="#78716C", neutral="#F5F5F4",
                            neutral_hover="#E7E5E4", text="#1C1917"),
    "Ocean Light": dict(mode="Light", primary="#2563EB", hover="#1D4ED8", card="#FFFFFF", bg="#F4F4F5",
                        list_bg="#FAFAFA", border="#E4E4E7", muted="#71717A", neutral="#F4F4F5",
                        neutral_hover="#E4E4E7", text="#18181B"),
    "Rose Light":  dict(mode="Light", primary="#E11D48", hover="#BE123C", card="#FFFFFF", bg="#FAF5F6",
                        list_bg="#FFFAFB", border="#F0DDE1", muted="#8A6A72", neutral="#F7ECEF",
                        neutral_hover="#F0DDE1", text="#2A0A12"),
}



# ---------- HELPERS ----------
def parse_groups(text, total):
    """'1-3, 5, 8-' -> [[0,1,2],[4],[7,...,total-1]] (0-based). Open ends allowed."""
    text = text.replace("–", "-").replace("—", "-").replace(";", ",").replace(" ", "")
    groups = []
    for part in text.split(","):
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                a, b = (int(a) if a else 1), (int(b) if b else total)
            else:
                a = b = int(part)
        except ValueError:
            raise ValueError(f"Can't read '{part}'. Use format like 1-3, 5, 8-")
        if a < 1 or b > total or a > b:
            raise ValueError(f"Range '{part}' is invalid (PDF has {total} pages)")
        groups.append(list(range(a - 1, b)))
    if not groups:
        raise ValueError("Enter a page range first, e.g. 1-3, 5, 8-")
    return groups


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.2f} {u}"
        n /= 1024


def open_reader(path):
    """Open a PDF (reads it fully into memory, so the file is never left locked)."""
    r = PdfReader(path)
    if r.is_encrypted:
        try:
            ok = r.decrypt("")
        except Exception as e:  # e.g. 'cryptography' package missing for AES
            raise ValueError(f"Can't decrypt '{os.path.basename(path)}': {e}. "
                             "Try: pip install cryptography")
        if not ok:
            raise ValueError(f"'{os.path.basename(path)}' is password-protected")
    return r


def save_writer(writer, out):
    """Write to a temp file then rename, so a failed save never leaves a broken PDF."""
    tmp = out + ".tmp"
    try:
        with open(tmp, "wb") as fh:
            writer.write(fh)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def same_file(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


class ReorderList(Listbox):
    """Listbox with real drag-to-reorder. Mutates `items` in place. label(index, item) -> str."""

    def __init__(self, master, items, label, on_change=None, **kw):
        super().__init__(master, exportselection=False, activestyle="none",
                         highlightthickness=0, borderwidth=0, cursor="hand2", **kw)
        self.items, self.label, self.on_change, self._drag = items, label, on_change, None
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))

    def refresh(self, select=None):
        top = self.yview()[0]
        self.delete(0, "end")
        if self.items:
            self.insert("end", *["   " + self.label(i, it) for i, it in enumerate(self.items)])
        self.yview_moveto(top)
        if select is not None and 0 <= select < len(self.items):
            self.selection_set(select)
            self.see(select)
        if self.on_change:
            self.on_change()

    def selected(self):
        s = self.curselection()
        return s[0] if s else None

    def _press(self, e):
        self.focus_set()
        if self.items:
            self._drag = self.nearest(e.y)
            self.selection_clear(0, "end")
            self.selection_set(self._drag)

    def _motion(self, e):
        if self._drag is None or not self.items:
            return
        j = max(0, min(self.nearest(e.y), len(self.items) - 1))
        if j != self._drag:
            self.items.insert(j, self.items.pop(self._drag))
            self._drag = j
            self.refresh(select=j)

    def move(self, delta):
        i = self.selected()
        if i is None or not 0 <= i + delta < len(self.items):
            return
        self.items[i], self.items[i + delta] = self.items[i + delta], self.items[i]
        self.refresh(select=i + delta)

    def remove_selected(self):
        i = self.selected()
        if i is not None:
            self.items.pop(i)
            self.refresh(select=min(i, len(self.items) - 1))


class PDFToolkit(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Toolkit")
        self.geometry("1040x780")
        self.minsize(940, 680)

        self.t = THEMES["Graphite"]
        self.configure(bg=self.t["bg"])        # so transparent widgets inherit the right colour
        self.bgframes = []
        self.cards, self.primaries, self.neutrals, self.muted, self.lists = [], [], [], [], []
        self.files, self.page_counts = [], {}
        self.pg_path, self.pg_items = None, []
        self.sp_path = self.cp_path = None
        self.sp_total = 0
        self.pg_doc, self.pg_base = None, {}          # preview document + original page rotations
        self._pv_cache, self._pv_job, self._pv_img = {}, None, None
        self._busy = False
        self._q = queue.Queue()

        self._build_header()
        self._build_status()
        self.tabs = ctk.CTkTabview(self, corner_radius=12, border_width=1)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        for name in ("Merge", "Split", "Pages", "Compress"):
            self.tabs.add(name)
        self._build_merge(self.tabs.tab("Merge"))
        self._build_split(self.tabs.tab("Split"))
        self._build_pages(self.tabs.tab("Pages"))
        self._build_compress(self.tabs.tab("Compress"))
        self.apply_theme("Graphite")
        self.after(60, self._poll)

    # ---------- widget factories ----------
    def card(self, parent, **kw):
        f = ctk.CTkFrame(parent, corner_radius=12, border_width=1, **kw)
        self.cards.append(f)
        return f

    def btn(self, parent, text, cmd, kind="primary", **kw):
        b = ctk.CTkButton(parent, text=text, command=cmd, font=("Segoe UI Semibold", 13), corner_radius=8, **kw)
        (self.primaries if kind == "primary" else self.neutrals).append(b)
        return b

    def listbox_for(self, parent, items, label, on_change=None):
        lb = ReorderList(parent, items, label, on_change, font=("Segoe UI", 12))
        self.lists.append(lb)
        return lb

    def muted_label(self, parent, text):
        l = ctk.CTkLabel(parent, text=text, font=("Segoe UI", 12), justify="left")
        self.muted.append(l)
        return l

    def drop_zone(self, widget, callback):
        def on_drop(e):
            pdfs = [f for f in self.tk.splitlist(e.data) if f.lower().endswith(".pdf")]
            if pdfs:
                callback(pdfs)
            else:
                self.set_status(0, "⚠ Only .pdf files can be dropped here")
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", on_drop)

    def error(self, title, msg):
        self.set_status(0, f"❌ {msg}")
        messagebox.showerror(title, msg)

    # ---------- header / status / theme ----------
    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color=self.t["bg"])
        h.pack(fill="x", padx=20, pady=(14, 6))
        left = ctk.CTkFrame(h, fg_color=self.t["bg"])
        self.bgframes += [h, left]
        left.pack(side="left")
        ctk.CTkLabel(left, text="📄 PDF Toolkit", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        self.subtitle = ctk.CTkLabel(left, text="Merge, split, edit and compress PDFs", font=("Segoe UI", 13))
        self.subtitle.pack(anchor="w")
        self.muted.append(self.subtitle)
        self.theme_menu = ctk.CTkOptionMenu(h, values=list(THEMES), width=150, command=self.apply_theme)
        self.theme_menu.pack(side="right")
        ctk.CTkLabel(h, text="🎨 Theme").pack(side="right", padx=8)

    def _build_status(self):
        bar = ctk.CTkFrame(self, fg_color=self.t["bg"])
        self.bgframes.append(bar)
        bar.pack(side="bottom", fill="x", padx=20, pady=(0, 12))
        self.status = ctk.CTkLabel(bar, text="Ready", font=("Segoe UI", 12), anchor="w")
        self.status.pack(fill="x")
        self.muted.append(self.status)
        self.progress = ctk.CTkProgressBar(bar, height=6)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(4, 0))

    def _titlebar(self, dark):
        """Dark native title bar on Windows 10/11."""
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            v = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), 4)
        except Exception:
            pass

    def apply_theme(self, name):
        t = self.t = THEMES[name]
        txt = t["text"]
        ctk.set_appearance_mode(t["mode"])
        self.configure(bg=t["bg"])
        for f in self.bgframes:
            f.configure(fg_color=t["bg"])
        for c in self.cards:
            c.configure(fg_color=t["card"], border_color=t["border"])
        for b in self.primaries:
            b.configure(fg_color=t["primary"], hover_color=t["hover"], text_color="white", border_width=0)
        for b in self.neutrals:
            b.configure(fg_color=t["neutral"], hover_color=t["neutral_hover"], text_color=txt,
                        border_width=1, border_color=t["border"])
        for l in self.muted:
            l.configure(text_color=t["muted"])
        for lb in self.lists:
            lb.configure(bg=t["list_bg"], fg=txt, selectbackground=t["primary"], selectforeground="white")
        self.tabs.configure(fg_color=t["bg"], border_color=t["border"], text_color=txt,
                            segmented_button_fg_color=t["card"],
                            segmented_button_selected_color=t["primary"],
                            segmented_button_selected_hover_color=t["hover"],
                            segmented_button_unselected_color=t["card"],
                            segmented_button_unselected_hover_color=t["neutral_hover"])
        self.progress.configure(progress_color=t["primary"], fg_color=t["border"])
        self.theme_menu.configure(fg_color=t["neutral"], button_color=t["neutral"],
                                  button_hover_color=t["neutral_hover"], text_color=txt,
                                  dropdown_fg_color=t["card"], dropdown_hover_color=t["neutral_hover"],
                                  dropdown_text_color=txt)
        for e in (self.split_entry, self.pg_range):
            e.configure(fg_color=t["list_bg"], border_color=t["border"], text_color=txt)
        for sb in (self.split_mode, self.cp_level):
            sb.configure(fg_color=t["neutral"], selected_color=t["primary"], selected_hover_color=t["hover"],
                         unselected_color=t["neutral"], unselected_hover_color=t["neutral_hover"], text_color=txt)
        self.theme_menu.set(name)
        self._titlebar(t["mode"] == "Dark")

    # ---------- background task runner (thread-safe: worker -> queue -> main thread) ----------
    def set_status(self, frac=None, text=None):
        if frac is not None:
            self.progress.set(max(0.0, min(1.0, frac)))
        if text:
            self.status.configure(text=text)

    def _poll(self):
        """Runs on the main thread; the only place worker results touch the UI."""
        try:
            while True:
                kind, a, b = self._q.get_nowait()
                if kind == "prog":
                    self.set_status(a, b)
                elif kind == "done":
                    self._busy = False
                    self.set_status(1.0, f"✅ {a}")
                else:  # error
                    self._busy = False
                    self.error("Error", a)
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def run_task(self, work):
        if self._busy:
            messagebox.showinfo("Please wait", "Another task is still running.")
            return
        self._busy = True
        self.set_status(0, "Working...")

        def prog(frac, text=None):
            self._q.put(("prog", frac, text))

        def target():
            try:
                self._q.put(("done", work(prog), None))
            except Exception as e:
                self._q.put(("err", str(e) or type(e).__name__, None))
        threading.Thread(target=target, daemon=True).start()

    def guard_out(self, out, *sources):
        """Refuse to overwrite an input file."""
        for s in sources:
            if s and same_file(out, s):
                messagebox.showerror("Save", "Choose a different file name - the output would overwrite an input file.")
                return False
        return True

    # ======================= MERGE =======================
    def _build_merge(self, tab):
        drop = self.card(tab, height=90)
        drop.pack(fill="x", pady=(4, 8))
        drop.pack_propagate(False)
        ctk.CTkLabel(drop, text="📥 Drag & drop PDFs here or click Add PDFs",
                     font=("Segoe UI", 15)).pack(expand=True)
        self.drop_zone(drop, self.merge_add)
        self.drop_zone(tab, self.merge_add)

        box = self.card(tab)
        box.pack(fill="both", expand=True)
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(top, text="📑 Files (drag to reorder)", font=("Segoe UI", 14, "bold")).pack(side="left")
        for txt, cmd in (("✕", lambda: self.mlist.remove_selected()),
                         ("↓", lambda: self.mlist.move(1)), ("↑", lambda: self.mlist.move(-1))):
            self.btn(top, txt, cmd, "neutral", width=36).pack(side="right", padx=3)
        self.mlist = self.listbox_for(box, self.files, self.merge_label, self._merge_changed)
        self.mlist.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.mlist.bind("<Delete>", lambda e: self.mlist.remove_selected())

        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", pady=(8, 0))
        self.btn(bar, "+ Add PDFs", self.merge_browse, width=130, height=40).pack(side="left")
        self.btn(bar, "Clear", self.merge_clear, "neutral", width=90, height=40).pack(side="left", padx=8)
        self.merge_go = self.btn(bar, "Merge PDFs", self.merge_start, width=200, height=44, state="disabled")
        self.merge_go.pack(side="right")

    def merge_label(self, i, p):
        if p not in self.page_counts:
            try:
                self.page_counts[p] = len(open_reader(p).pages)
            except Exception:
                self.page_counts[p] = "?"
        return f"{i + 1:>2}.  {os.path.basename(p)}    ·    {self.page_counts[p]} pages"

    def _merge_changed(self):
        self.merge_go.configure(state="normal" if len(self.files) >= 2 else "disabled")

    def merge_add(self, paths):
        self.files.extend(p for p in dict.fromkeys(paths) if p not in self.files)
        self.mlist.refresh()

    def merge_browse(self):
        self.merge_add(filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")]))

    def merge_clear(self):
        self.files.clear()
        self.mlist.refresh()
        self.set_status(0, "Ready")

    def merge_start(self):
        if len(self.files) < 2:
            return messagebox.showinfo("Merge", "Add at least 2 PDFs.")
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                           initialfile="merged.pdf")
        if not out or not self.guard_out(out, *self.files):
            return
        files = list(self.files)

        def work(prog):
            w = PdfWriter()
            for i, f in enumerate(files):
                prog(i / len(files), f"Merging {i + 1} of {len(files)}...")
                try:
                    for page in open_reader(f).pages:
                        w.add_page(page)
                except Exception as e:
                    raise ValueError(f"Can't read {os.path.basename(f)}: {e}")
            prog(0.95, "Saving...")
            save_writer(w, out)
            return f"Merged {len(files)} PDFs → {os.path.basename(out)}"
        self.run_task(work)

    # ======================= SPLIT =======================
    SPLIT_HINTS = {
        "By ranges": "Each comma-separated range becomes one file, e.g.  1-3, 4-6, 9-",
        "Every N pages": "Enter N (e.g. 5): a new file is created every N pages",
        "Each page": "Every page is saved as its own file",
    }

    def _build_split(self, tab):
        self.drop_zone(tab, lambda p: self.split_load(p[0]))
        c = self.card(tab)
        c.pack(fill="x", pady=(4, 8))
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=14)
        self.btn(row, "Open PDF", self.split_browse, width=120, height=36).pack(side="left")
        self.split_info = self.muted_label(row, "Drop or open a PDF")
        self.split_info.pack(side="left", padx=12)

        opts = self.card(tab)
        opts.pack(fill="x")
        ctk.CTkLabel(opts, text="Split mode", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.split_mode = ctk.CTkSegmentedButton(
            opts, values=list(self.SPLIT_HINTS), command=self._split_mode_changed)
        self.split_mode.set("By ranges")
        self.split_mode.pack(anchor="w", padx=14)
        self.split_entry = ctk.CTkEntry(opts, width=420)
        self.split_entry.pack(anchor="w", padx=14, pady=(12, 4))
        self.split_hint = self.muted_label(opts, self.SPLIT_HINTS["By ranges"])
        self.split_hint.pack(anchor="w", padx=14)
        self.muted_label(opts, "Files are saved as <name>_part1.pdf, _part2.pdf … in the folder you choose."
                         ).pack(anchor="w", padx=14, pady=(2, 12))
        self.split_go = self.btn(tab, "Split PDF", self.split_start, width=200, height=44)
        self.split_go.pack(side="right", pady=12)

    def _split_mode_changed(self, mode):
        self.split_entry.configure(state="normal")
        self.split_entry.delete(0, "end")
        self.split_hint.configure(text=self.SPLIT_HINTS[mode])
        if mode == "Each page":
            self.split_entry.configure(state="disabled")

    def split_browse(self):
        p = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if p:
            self.split_load(p)

    def split_load(self, path):
        try:
            n = len(open_reader(path).pages)
        except Exception as e:
            return self.error("Open PDF", f"Can't open {os.path.basename(path)}: {e}")
        self.sp_path, self.sp_total = path, n
        self.split_info.configure(text=f"{os.path.basename(path)}  ·  {n} pages  ·  {human(os.path.getsize(path))}")
        self.set_status(0, "Ready")

    def split_groups(self, mode, text):
        total = self.sp_total
        if mode == "By ranges":
            return parse_groups(text, total)
        if mode == "Every N pages":
            try:
                n = int(text.strip())
            except ValueError:
                raise ValueError("Enter a whole number for N, e.g. 5")
            if n < 1:
                raise ValueError("N must be 1 or more")
            return [list(range(i, min(i + n, total))) for i in range(0, total, n)]
        return [[i] for i in range(total)]

    def split_start(self):
        if not self.sp_path:
            return messagebox.showinfo("Split", "Open a PDF first.")
        if not os.path.exists(self.sp_path):
            return self.error("Split", "The source file no longer exists.")
        mode, text = self.split_mode.get(), self.split_entry.get()
        try:
            groups = self.split_groups(mode, text)
        except ValueError as e:
            return messagebox.showerror("Split", str(e))
        out_dir = filedialog.askdirectory(title="Choose output folder",
                                          initialdir=os.path.dirname(self.sp_path))
        if not out_dir:
            return
        base = os.path.splitext(os.path.basename(self.sp_path))[0]
        width = len(str(len(groups)))
        paths = [os.path.join(out_dir, f"{base}_part{k:0{width}d}.pdf") for k in range(1, len(groups) + 1)]
        clash = [p for p in paths if os.path.exists(p)]
        if clash and not messagebox.askyesno(
                "Overwrite?", f"{len(clash)} file(s) already exist in that folder and will be replaced. Continue?"):
            return
        if any(same_file(p, self.sp_path) for p in paths):
            return messagebox.showerror("Split", "An output file would overwrite the source PDF. Pick another folder.")
        src = self.sp_path

        def work(prog):
            r = open_reader(src)
            for k, (g, path) in enumerate(zip(groups, paths), 1):
                prog((k - 1) / len(groups), f"Writing part {k} of {len(groups)}...")
                w = PdfWriter()
                for i in g:
                    w.add_page(r.pages[i])
                save_writer(w, path)
            return f"Split into {len(groups)} file(s) → {out_dir}"
        self.run_task(work)

    # ======================= PAGES (reorder / delete / rotate / extract) =======================
    def _build_pages(self, tab):
        self.drop_zone(tab, lambda p: self.pg_load(p[0]))
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=(4, 6))
        self.btn(top, "Open PDF", self.pg_browse, width=120, height=36).pack(side="left")
        self.pg_info = self.muted_label(top, "Drop or open a PDF to edit its pages")
        self.pg_info.pack(side="left", padx=12)

        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)
        box = self.card(body, width=200)
        box.pack(side="left", fill="y")
        box.pack_propagate(False)
        self.plist = self.listbox_for(box, self.pg_items, self.pg_label, self._pg_update_info)
        self.plist.pack(fill="both", expand=True, padx=10, pady=10)
        self.plist.bind("<Delete>", lambda e: self.plist.remove_selected())
        self.plist.bind("<<ListboxSelect>>", lambda e: self.pg_preview())

        side = self.card(body, width=220)
        side.pack(side="right", fill="y", padx=(8, 0))
        side.pack_propagate(False)
        pad = dict(padx=12, pady=3, fill="x")
        ctk.CTkLabel(side, text="Selected page", font=("Segoe UI", 13, "bold")).pack(pady=(10, 2))
        r = ctk.CTkFrame(side, fg_color="transparent")
        r.pack(**pad)
        self.btn(r, "↑", lambda: self.plist.move(-1), "neutral", width=50).pack(side="left", expand=True)
        self.btn(r, "↓", lambda: self.plist.move(1), "neutral", width=50).pack(side="left", expand=True)
        self.btn(side, "⟳ Rotate 90°", self.pg_rotate, "neutral").pack(**pad)
        self.btn(side, "🗑 Delete page", self.plist.remove_selected, "neutral").pack(**pad)
        ctk.CTkLabel(side, text="By page range", font=("Segoe UI", 13, "bold")).pack(pady=(12, 2))
        self.pg_range = ctk.CTkEntry(side, placeholder_text="e.g. 2-4, 7, 10-")
        self.pg_range.pack(**pad)
        self.btn(side, "Delete range", lambda: self.pg_apply_range(False), "neutral").pack(**pad)
        self.btn(side, "Keep only range", lambda: self.pg_apply_range(True), "neutral").pack(**pad)
        self.btn(side, "⇅ Reverse order", self.pg_reverse, "neutral").pack(**pad)
        self.pg_save = self.btn(side, "💾 Save PDF", self.pg_save_start, height=42)
        self.pg_save.pack(padx=12, pady=(14, 8), fill="x", side="bottom")

        # ---- live page preview (middle) ----
        pv = self.card(body)
        pv.pack(side="left", fill="both", expand=True, padx=8)
        nav = ctk.CTkFrame(pv, fg_color="transparent")
        nav.pack(side="bottom", fill="x", padx=10, pady=(0, 8))
        self.btn(nav, "◀", lambda: self.pg_step(-1), "neutral", width=44).pack(side="left")
        self.btn(nav, "▶", lambda: self.pg_step(1), "neutral", width=44).pack(side="right")
        self.pv_caption = self.muted_label(nav, "")
        self.pv_caption.pack(expand=True)
        self.pv_holder = ctk.CTkFrame(pv, fg_color="transparent")
        self.pv_holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.pv_holder.pack_propagate(False)
        self._pv_blank = ctk.CTkImage(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1)) if HAVE_PIL else None
        self.pv_label = ctk.CTkLabel(self.pv_holder, text="Select a page to preview", font=("Segoe UI", 12),
                                     justify="center", wraplength=300)
        self.pv_label.pack(expand=True)
        self.muted.append(self.pv_label)
        self.pv_holder.bind("<Configure>", lambda e: self._pv_schedule())

    def pg_label(self, pos, it):
        rot = f"   ⟳{it['rot']}°" if it["rot"] else ""
        return f"{pos + 1:>3}.  Page {it['n'] + 1}{rot}"

    # ---------- preview ----------
    def _pv_message(self, text):
        self._pv_img = None
        self.pv_label.configure(text=text, image=self._pv_blank)
        self.pv_caption.configure(text="")

    def _pv_schedule(self):
        """Debounce: re-render shortly after the window stops resizing."""
        if self._pv_job:
            self.after_cancel(self._pv_job)
        self._pv_job = self.after(120, self.pg_preview)

    def pg_step(self, delta):
        if not self.pg_items:
            return
        i = self.plist.selected()
        j = 0 if i is None else max(0, min(i + delta, len(self.pg_items) - 1))
        self.plist.selection_clear(0, "end")
        self.plist.selection_set(j)
        self.plist.see(j)
        self.pg_preview()

    def pg_preview(self):
        self._pv_job = None
        i = self.plist.selected()
        if not self.pg_path or not self.pg_items or i is None or i >= len(self.pg_items):
            return self._pv_message("Select a page to preview" if self.pg_items else "No pages")
        if not (HAVE_FITZ and HAVE_PIL and self.pg_doc):
            return self._pv_message("Page preview needs PyMuPDF:\n\npip install pymupdf")
        it = self.pg_items[i]
        w = max(self.pv_holder.winfo_width() - 8, 120)
        h = max(self.pv_holder.winfo_height() - 8, 120)
        key = (it["n"], it["rot"], w // 16, h // 16)
        img = self._pv_cache.get(key)
        if img is None:
            try:
                page = self.pg_doc[it["n"]]
                page.set_rotation((self.pg_base.get(it["n"], 0) + it["rot"]) % 360)
                r = page.rect
                zoom = max(0.2, min(w / r.width, h / r.height, 3.0))
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                img = ctk.CTkImage(Image.frombytes("RGB", (pix.width, pix.height), pix.samples),
                                   size=(pix.width, pix.height))
            except Exception as e:
                return self._pv_message(f"Can't render this page:\n{e}")
            if len(self._pv_cache) > 40:
                self._pv_cache.clear()
            self._pv_cache[key] = img
        self._pv_img = img  # keep a reference so it isn't garbage-collected
        self.pv_label.configure(text="", image=img)
        self.pv_caption.configure(text=f"Position {i + 1} of {len(self.pg_items)}  ·  original page {it['n'] + 1}")

    def pg_browse(self):
        p = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if p:
            self.pg_load(p)

    def pg_load(self, path):
        try:
            n = len(open_reader(path).pages)
        except Exception as e:
            return self.error("Open PDF", f"Can't open {os.path.basename(path)}: {e}")
        self.pg_path = path
        self.pg_items[:] = [{"n": i, "rot": 0} for i in range(n)]
        self._pv_cache.clear()
        self.pg_doc, self.pg_base = None, {}
        if HAVE_FITZ:
            try:
                with open(path, "rb") as fh:       # from memory, so the file is never locked
                    doc = fitz.open(stream=fh.read(), filetype="pdf")
                if doc.needs_pass:
                    doc.authenticate("")
                self.pg_doc = doc
                self.pg_base = {i: doc[i].rotation for i in range(len(doc))}
            except Exception:
                self.pg_doc = None
        self.plist.refresh(select=0)  # updates the info label + preview

    def _pg_update_info(self):
        if self.pg_path:
            self.pg_info.configure(text=f"{os.path.basename(self.pg_path)}  ·  {len(self.pg_items)} pages in output")
            self.pg_preview()

    def pg_rotate(self):
        i = self.plist.selected()
        if i is not None:
            self.pg_items[i]["rot"] = (self.pg_items[i]["rot"] + 90) % 360
            self.plist.refresh(select=i)

    def pg_reverse(self):
        self.pg_items.reverse()
        self.plist.refresh()

    def pg_apply_range(self, keep):
        if not self.pg_items:
            return
        try:
            idx = {i for g in parse_groups(self.pg_range.get(), len(self.pg_items)) for i in g}
        except ValueError as e:
            return messagebox.showerror("Page range", str(e))
        self.pg_items[:] = [it for i, it in enumerate(self.pg_items) if (i in idx) == keep]
        self.plist.refresh()

    def pg_save_start(self):
        if not self.pg_path or not self.pg_items:
            return messagebox.showinfo("Save", "Nothing to save.")
        base = os.path.splitext(os.path.basename(self.pg_path))[0]
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                           initialfile=f"{base}_edited.pdf")
        if not out or not self.guard_out(out, self.pg_path):
            return
        src, items = self.pg_path, [dict(i) for i in self.pg_items]

        def work(prog):
            r = open_reader(src)
            w = PdfWriter()
            for k, it in enumerate(items):
                prog(k / len(items), f"Writing page {k + 1} of {len(items)}...")
                page = r.pages[it["n"]]
                if it["rot"]:
                    page.rotate(it["rot"])
                w.add_page(page)
            prog(0.95, "Saving...")
            save_writer(w, out)
            return f"Saved {len(items)} pages → {os.path.basename(out)}"
        self.run_task(work)

    # ======================= COMPRESS =======================
    def _build_compress(self, tab):
        self.drop_zone(tab, lambda p: self.cp_load(p[0]))
        c = self.card(tab)
        c.pack(fill="x", pady=(4, 8))
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=14)
        self.btn(row, "Open PDF", self.cp_browse, width=120, height=36).pack(side="left")
        self.cp_info = self.muted_label(row, "Drop or open a PDF to compress")
        self.cp_info.pack(side="left", padx=12)

        o = self.card(tab)
        o.pack(fill="x")
        ctk.CTkLabel(o, text="Compression level", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.cp_level = ctk.CTkSegmentedButton(o, values=["Low", "Medium", "High"])
        self.cp_level.set("Medium")
        self.cp_level.pack(anchor="w", padx=14)
        self.muted_label(
            o, "Low: lossless (streams + duplicate objects).\nMedium: images → JPEG 65%.\n"
               "High: images → JPEG 40% and downscaled (smallest, lower quality).\n"
               "Medium/High need Pillow (pip install pillow)."
        ).pack(anchor="w", padx=14, pady=12)
        self.cp_go = self.btn(tab, "Compress PDF", self.cp_start, width=200, height=44)
        self.cp_go.pack(side="right", pady=12)

    def cp_browse(self):
        p = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if p:
            self.cp_load(p)

    def cp_load(self, path):
        try:
            open_reader(path)
        except Exception as e:
            return self.error("Open PDF", f"Can't open {os.path.basename(path)}: {e}")
        self.cp_path = path
        self.cp_info.configure(text=f"{os.path.basename(path)}  ·  {human(os.path.getsize(path))}")

    def cp_start(self):
        if not self.cp_path:
            return messagebox.showinfo("Compress", "Open a PDF first.")
        level = self.cp_level.get()
        quality, maxdim = {"Low": (None, 0), "Medium": (65, 2200), "High": (40, 1400)}[level]
        if quality and not HAVE_PIL:
            return messagebox.showerror("Compress", "Pillow is required for Medium/High.\n\npip install pillow")
        base = os.path.splitext(os.path.basename(self.cp_path))[0]
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                           initialfile=f"{base}_compressed.pdf")
        if not out or not self.guard_out(out, self.cp_path):
            return
        src = self.cp_path

        def work(prog):
            r = open_reader(src)
            w = PdfWriter()
            for p in r.pages:
                w.add_page(p)
            total = len(w.pages)
            seen, recompressed = set(), 0
            for k, page in enumerate(w.pages):
                prog(k / total, f"Compressing page {k + 1} of {total}...")
                try:
                    page.compress_content_streams()
                except Exception:
                    pass
                if not quality:
                    continue
                try:
                    images = list(page.images)
                except Exception:
                    continue
                for img in images:
                    try:
                        ref = getattr(img, "indirect_reference", None)
                        key = ref.idnum if ref is not None else None
                        if key is not None and key in seen:   # shared image: don't recompress twice
                            continue
                        pil = img.image
                        if pil.mode in ("P", "CMYK"):
                            pil = pil.convert("RGB")
                        elif pil.mode not in ("RGB", "L"):    # skip 1-bit masks, alpha, etc.
                            continue
                        if max(pil.size) < 300:               # tiny images: not worth it
                            continue
                        if max(pil.size) > maxdim:
                            pil.thumbnail((maxdim, maxdim))
                        img.replace(pil, quality=quality)
                        recompressed += 1
                        if key is not None:
                            seen.add(key)
                    except Exception:
                        continue
            prog(0.9, "Optimizing and saving...")
            try:
                w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
            except Exception:
                pass
            save_writer(w, out)
            a, b = os.path.getsize(src), os.path.getsize(out)
            pct = (1 - b / a) * 100
            note = "" if b < a else "  (no gain - try a higher level)"
            imgs = f", {recompressed} image(s) recompressed" if quality else ""
            return f"{human(a)} → {human(b)}  ({pct:.0f}% smaller{imgs}){note}"
        self.run_task(work)


if __name__ == "__main__":
    PDFToolkit().mainloop()
