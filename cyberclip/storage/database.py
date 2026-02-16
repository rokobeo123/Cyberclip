"""SQLite database backend for CyberClip."""
import json
import os
import sqlite3
from typing import List, Optional

from cyberclip.storage.models import ClipboardItem, AppSettings, TabRule
from cyberclip.utils.constants import DB_PATH, APP_DATA_DIR, MAX_ITEMS_PER_TAB


class Database:
    def __init__(self):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_type TEXT NOT NULL DEFAULT 'text',
                text_content TEXT DEFAULT '',
                image_path TEXT DEFAULT '',
                source_app TEXT DEFAULT '',
                tab TEXT DEFAULT 'General',
                pinned INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                extra_data TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tab_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_pattern TEXT NOT NULL,
                tab_name TEXT NOT NULL,
                enabled INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_items_tab ON items(tab);
            CREATE INDEX IF NOT EXISTS idx_items_created ON items(created_at);
            CREATE INDEX IF NOT EXISTS idx_items_pinned ON items(pinned);
        """)
        self.conn.commit()

    def add_item(self, item: ClipboardItem) -> int:
        cur = self.conn.execute(
            """INSERT INTO items (content_type, text_content, image_path,
               source_app, tab, pinned, created_at, extra_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item.content_type, item.text_content, item.image_path,
             item.source_app, item.tab, int(item.pinned),
             item.created_at, item.extra_data)
        )
        self.conn.commit()
        item.id = cur.lastrowid
        self._enforce_limit(item.tab)
        return item.id

    def _enforce_limit(self, tab: str):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM items WHERE tab=?", (tab,)
        ).fetchone()[0]
        if count > MAX_ITEMS_PER_TAB:
            excess = count - MAX_ITEMS_PER_TAB
            self.conn.execute(
                """DELETE FROM items WHERE id IN (
                    SELECT id FROM items
                    WHERE tab=? AND pinned=0
                    ORDER BY created_at ASC LIMIT ?
                )""", (tab, excess)
            )
            self.conn.commit()

    def get_items(self, tab: Optional[str] = None, limit: int = 100) -> List[ClipboardItem]:
        if tab:
            rows = self.conn.execute(
                "SELECT * FROM items WHERE tab=? ORDER BY created_at DESC LIMIT ?",
                (tab, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM items ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_items_fifo(self, tab: Optional[str] = None) -> List[ClipboardItem]:
        if tab:
            rows = self.conn.execute(
                "SELECT * FROM items WHERE tab=? ORDER BY created_at ASC",
                (tab,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM items ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def delete_item(self, item_id: int):
        self.conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        self.conn.commit()

    def toggle_pin(self, item_id: int) -> bool:
        row = self.conn.execute(
            "SELECT pinned FROM items WHERE id=?", (item_id,)
        ).fetchone()
        if row:
            new_val = 0 if row[0] else 1
            self.conn.execute(
                "UPDATE items SET pinned=? WHERE id=?", (new_val, item_id)
            )
            self.conn.commit()
            return bool(new_val)
        return False

    def clear_tab(self, tab: str):
        self.conn.execute(
            "DELETE FROM items WHERE tab=? AND pinned=0", (tab,)
        )
        self.conn.commit()

    def clear_all(self):
        self.conn.execute("DELETE FROM items WHERE pinned=0")
        self.conn.commit()

    def search_items(self, query: str, tab: Optional[str] = None) -> List[ClipboardItem]:
        if tab:
            rows = self.conn.execute(
                "SELECT * FROM items WHERE tab=? AND text_content LIKE ? ORDER BY created_at DESC",
                (tab, f"%{query}%")
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM items WHERE text_content LIKE ? ORDER BY created_at DESC",
                (f"%{query}%",)
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_tabs(self) -> List[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT tab FROM items ORDER BY tab"
        ).fetchall()
        tabs = [r[0] for r in rows]
        if "General" not in tabs:
            tabs.insert(0, "General")
        return tabs

    def item_exists(self, text: str, tab: str) -> bool:
        row = self.conn.execute(
            "SELECT id FROM items WHERE text_content=? AND tab=? LIMIT 1",
            (text, tab)
        ).fetchone()
        return row is not None

    # Settings
    def save_setting(self, key: str, value):
        val_str = json.dumps(value)
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, val_str)
        )
        self.conn.commit()

    def get_setting(self, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        if row:
            return json.loads(row[0])
        return default

    def save_all_settings(self, settings: AppSettings):
        data = {
            "picking_style": settings.picking_style,
            "ghost_mode": settings.ghost_mode,
            "strip_formatting": settings.strip_formatting,
            "auto_enter": settings.auto_enter,
            "auto_tab": settings.auto_tab,
            "super_paste_enabled": settings.super_paste_enabled,
            "ghost_type_speed": settings.ghost_type_speed,
            "theme": settings.theme,
            "blacklist": settings.blacklist,
            "hotkeys": settings.hotkeys,
            "window_x": settings.window_x,
            "window_y": settings.window_y,
            "window_width": settings.window_width,
            "window_height": settings.window_height,
        }
        for k, v in data.items():
            self.save_setting(k, v)

    def load_settings(self) -> AppSettings:
        s = AppSettings()
        s.picking_style = self.get_setting("picking_style", "FIFO")
        s.ghost_mode = self.get_setting("ghost_mode", False)
        s.strip_formatting = self.get_setting("strip_formatting", False)
        s.auto_enter = self.get_setting("auto_enter", False)
        s.auto_tab = self.get_setting("auto_tab", False)
        s.super_paste_enabled = self.get_setting("super_paste_enabled", False)
        s.ghost_type_speed = self.get_setting("ghost_type_speed", 15)
        s.theme = self.get_setting("theme", "cyberpunk")
        s.blacklist = self.get_setting("blacklist", [])
        s.hotkeys = self.get_setting("hotkeys", {})
        s.window_x = self.get_setting("window_x", -1)
        s.window_y = self.get_setting("window_y", -1)
        s.window_width = self.get_setting("window_width", 420)
        s.window_height = self.get_setting("window_height", 680)
        return s

    # Tab rules
    def save_tab_rule(self, rule: TabRule) -> int:
        if rule.id:
            self.conn.execute(
                "UPDATE tab_rules SET app_pattern=?, tab_name=?, enabled=? WHERE id=?",
                (rule.app_pattern, rule.tab_name, int(rule.enabled), rule.id)
            )
        else:
            cur = self.conn.execute(
                "INSERT INTO tab_rules (app_pattern, tab_name, enabled) VALUES (?, ?, ?)",
                (rule.app_pattern, rule.tab_name, int(rule.enabled))
            )
            rule.id = cur.lastrowid
        self.conn.commit()
        return rule.id

    def get_tab_rules(self) -> List[TabRule]:
        rows = self.conn.execute("SELECT * FROM tab_rules").fetchall()
        return [TabRule(id=r[0], app_pattern=r[1], tab_name=r[2], enabled=bool(r[3])) for r in rows]

    def delete_tab_rule(self, rule_id: int):
        self.conn.execute("DELETE FROM tab_rules WHERE id=?", (rule_id,))
        self.conn.commit()

    def _row_to_item(self, row) -> ClipboardItem:
        return ClipboardItem(
            id=row["id"],
            content_type=row["content_type"],
            text_content=row["text_content"],
            image_path=row["image_path"],
            source_app=row["source_app"],
            tab=row["tab"],
            pinned=bool(row["pinned"]),
            created_at=row["created_at"],
            extra_data=row["extra_data"],
        )

    def close(self):
        self.conn.close()
