# Modified: [1.2] busy_timeout=3000, integrity_check on startup with backup+recreate on corruption;
#           index on content_type; [1.7] image cleanup integration — delete image file
#           atomically when deleting a clip; startup orphan scan;
#           [4.2] position column for drag-and-drop persistence
"""SQLite database backend for CyberClip."""
import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from typing import List, Optional

from cyberclip.storage.models import ClipboardItem, AppSettings, TabRule, Snippet, AppExclusion
from cyberclip.utils.constants import DB_PATH, APP_DATA_DIR, MAX_ITEMS_PER_TAB

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        db_existed = os.path.exists(DB_PATH)
        self.conn = self._open_connection()

        # 1.2 — Integrity check on first open of an existing database
        if db_existed:
            self._check_integrity()

        self._create_tables()
        self._migrate_schema()

    # ── Connection helpers ────────────────────────────────────────────────
    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=3000")   # 1.2 — avoid "database is locked"
        conn.row_factory = sqlite3.Row
        return conn

    def _check_integrity(self):
        """1.2 — Run integrity_check; if corrupt, backup and recreate."""
        try:
            result = self.conn.execute("PRAGMA integrity_check").fetchone()
            if result and result[0] != "ok":
                logger.error("Database integrity check failed: %s — recreating", result[0])
                self._backup_and_recreate()
        except Exception as exc:
            logger.exception("Integrity check error: %s", exc)
            self._backup_and_recreate()

    def _backup_and_recreate(self):
        """Move the corrupt DB aside and open a fresh one."""
        try:
            self.conn.close()
        except Exception:
            pass
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"{DB_PATH}.corrupt_{stamp}.bak"
        try:
            shutil.move(DB_PATH, backup)
            logger.info("Corrupt database backed up to %s", backup)
        except Exception as exc:
            logger.warning("Could not backup corrupt DB: %s", exc)
        self.conn = self._open_connection()

    # ── Schema creation ───────────────────────────────────────────────────
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
                extra_data TEXT DEFAULT '',
                position INTEGER DEFAULT NULL,
                is_sensitive INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                trigger TEXT NOT NULL UNIQUE,
                content TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS exclusions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                process_name TEXT NOT NULL UNIQUE,
                enabled INTEGER DEFAULT 1
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
            CREATE INDEX IF NOT EXISTS idx_items_type ON items(content_type);
            CREATE INDEX IF NOT EXISTS idx_items_position ON items(position);
        """)
        self.conn.commit()

    def _migrate_schema(self):
        """Add columns introduced in later versions without recreating the table."""
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(items)").fetchall()}
        migrations = []
        if "position" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN position INTEGER DEFAULT NULL")
        if "is_sensitive" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN is_sensitive INTEGER DEFAULT 0")
        for sql in migrations:
            try:
                self.conn.execute(sql)
            except Exception as exc:
                logger.warning("Migration skipped (%s): %s", sql, exc)
        if migrations:
            self.conn.commit()

    # ── Image path references (used by startup orphan cleanup) ────────────
    def get_all_image_paths(self) -> set:
        """Return the set of all image_path values stored in the DB."""
        rows = self.conn.execute(
            "SELECT image_path FROM items WHERE image_path != ''"
        ).fetchall()
        return {r[0] for r in rows if r[0]}

    # ── CRUD ──────────────────────────────────────────────────────────────
    def add_item(self, item: ClipboardItem, max_items: int = MAX_ITEMS_PER_TAB) -> int:
        try:
            cur = self.conn.execute(
                """INSERT INTO items (content_type, text_content, image_path,
                   source_app, tab, pinned, created_at, extra_data, is_sensitive)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item.content_type, item.text_content, item.image_path,
                 item.source_app, item.tab, int(item.pinned),
                 item.created_at, item.extra_data, int(item.is_sensitive))
            )
            self.conn.commit()
            item.id = cur.lastrowid
            self._enforce_limit(item.tab, max_items)
            return item.id
        except sqlite3.Error as exc:
            logger.error("add_item failed: %s", exc)
            try:
                self.conn.rollback()
            except Exception:
                pass
            return -1

    def _enforce_limit(self, tab: str, max_items: int = MAX_ITEMS_PER_TAB):
        try:
            count = self.conn.execute(
                "SELECT COUNT(*) FROM items WHERE tab=?", (tab,)
            ).fetchone()[0]
            if count > max_items:
                excess = count - max_items
                # Also collect image paths for deleted items so we can clean them up
                rows = self.conn.execute(
                    """SELECT id, image_path FROM items
                       WHERE tab=? AND pinned=0
                       ORDER BY created_at ASC LIMIT ?""",
                    (tab, excess)
                ).fetchall()
                if rows:
                    ids = [r[0] for r in rows]
                    image_paths = [r[1] for r in rows if r[1]]
                    self.conn.execute(
                        f"DELETE FROM items WHERE id IN ({','.join('?' * len(ids))})", ids
                    )
                    self.conn.commit()
                    # 1.7 — delete associated image files
                    self._delete_image_files(image_paths)
        except sqlite3.Error as exc:
            logger.error("_enforce_limit failed: %s", exc)

    def get_items(self, tab: Optional[str] = None, limit: int = 100) -> List[ClipboardItem]:
        try:
            if tab:
                rows = self.conn.execute(
                    """SELECT * FROM items WHERE tab=?
                       ORDER BY CASE WHEN position IS NOT NULL THEN 0 ELSE 1 END,
                                position ASC, created_at DESC LIMIT ?""",
                    (tab, limit)
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT * FROM items
                       ORDER BY CASE WHEN position IS NOT NULL THEN 0 ELSE 1 END,
                                position ASC, created_at DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
            return [self._row_to_item(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("get_items failed: %s", exc)
            return []

    def get_items_fifo(self, tab: Optional[str] = None) -> List[ClipboardItem]:
        try:
            if tab:
                rows = self.conn.execute(
                    "SELECT * FROM items WHERE tab=? ORDER BY created_at ASC", (tab,)
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM items ORDER BY created_at ASC"
                ).fetchall()
            return [self._row_to_item(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("get_items_fifo failed: %s", exc)
            return []

    def delete_item(self, item_id: int, image_path: str = ""):
        """
        1.7 — Delete a clip and its associated image file in one operation.
        Pass *image_path* from the item (or leave blank for text items).
        """
        try:
            # Fetch image path from DB if caller didn't provide it
            if not image_path:
                row = self.conn.execute(
                    "SELECT image_path FROM items WHERE id=?", (item_id,)
                ).fetchone()
                if row:
                    image_path = row[0] or ""
            self.conn.execute("DELETE FROM items WHERE id=?", (item_id,))
            self.conn.commit()
            if image_path:
                self._delete_image_files([image_path])
        except sqlite3.Error as exc:
            logger.error("delete_item %s failed: %s", item_id, exc)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def toggle_pin(self, item_id: int) -> bool:
        try:
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
        except sqlite3.Error as exc:
            logger.error("toggle_pin failed: %s", exc)
        return False

    def clear_tab(self, tab: str):
        """Delete all unpinned items in a tab; also clean up image files."""
        try:
            rows = self.conn.execute(
                "SELECT image_path FROM items WHERE tab=? AND pinned=0", (tab,)
            ).fetchall()
            image_paths = [r[0] for r in rows if r[0]]
            self.conn.execute("DELETE FROM items WHERE tab=? AND pinned=0", (tab,))
            self.conn.commit()
            self._delete_image_files(image_paths)
        except sqlite3.Error as exc:
            logger.error("clear_tab failed: %s", exc)

    def clear_all(self):
        """Delete all unpinned items; also clean up image files."""
        try:
            rows = self.conn.execute(
                "SELECT image_path FROM items WHERE pinned=0"
            ).fetchall()
            image_paths = [r[0] for r in rows if r[0]]
            self.conn.execute("DELETE FROM items WHERE pinned=0")
            self.conn.commit()
            self._delete_image_files(image_paths)
        except sqlite3.Error as exc:
            logger.error("clear_all failed: %s", exc)

    # ── 4.2 Drag-and-drop position persistence ────────────────────────────
    def update_positions(self, item_ids: List[int]):
        """Persist drag-reorder: assign position 0…N to the given IDs in order."""
        try:
            for pos, item_id in enumerate(item_ids):
                self.conn.execute(
                    "UPDATE items SET position=? WHERE id=?", (pos, item_id)
                )
            self.conn.commit()
        except sqlite3.Error as exc:
            logger.error("update_positions failed: %s", exc)
            try:
                self.conn.rollback()
            except Exception:
                pass

    # ── Search ────────────────────────────────────────────────────────────
    def search_items(self, query: str, tab: Optional[str] = None) -> List[ClipboardItem]:
        try:
            if tab:
                rows = self.conn.execute(
                    """SELECT * FROM items WHERE tab=? AND text_content LIKE ?
                       ORDER BY created_at DESC""",
                    (tab, f"%{query}%")
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT * FROM items WHERE text_content LIKE ?
                       ORDER BY created_at DESC""",
                    (f"%{query}%",)
                ).fetchall()
            return [self._row_to_item(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("search_items failed: %s", exc)
            return []

    def get_tabs(self) -> List[str]:
        try:
            rows = self.conn.execute(
                "SELECT DISTINCT tab FROM items ORDER BY tab"
            ).fetchall()
            tabs = [r[0] for r in rows]
            if "General" not in tabs:
                tabs.insert(0, "General")
            return tabs
        except sqlite3.Error as exc:
            logger.error("get_tabs failed: %s", exc)
            return ["General"]

    def item_exists(self, text: str, tab: str) -> bool:
        try:
            row = self.conn.execute(
                "SELECT id FROM items WHERE text_content=? AND tab=? LIMIT 1",
                (text, tab)
            ).fetchone()
            return row is not None
        except sqlite3.Error:
            return False

    # ── Settings ──────────────────────────────────────────────────────────
    def save_setting(self, key: str, value):
        val_str = json.dumps(value)
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, val_str)
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            logger.error("save_setting %s failed: %s", key, exc)

    def get_setting(self, key: str, default=None):
        try:
            row = self.conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            if row:
                return json.loads(row[0])
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            logger.error("get_setting %s failed: %s", key, exc)
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
            "language": settings.language,
            "blacklist": settings.blacklist,
            "hotkeys": settings.hotkeys,
            "window_x": settings.window_x,
            "window_y": settings.window_y,
            "window_width": settings.window_width,
            "window_height": settings.window_height,
            "paste_delay_ms": settings.paste_delay_ms,
            "max_items": settings.max_items,
            "paste_all_count": settings.paste_all_count,
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
        s.language = self.get_setting("language", "vi")
        s.blacklist = self.get_setting("blacklist", [])
        s.hotkeys = self.get_setting("hotkeys", {})
        s.window_x = self.get_setting("window_x", -1)
        s.window_y = self.get_setting("window_y", -1)
        s.window_width = self.get_setting("window_width", 420)
        s.window_height = self.get_setting("window_height", 680)
        s.paste_delay_ms = self.get_setting("paste_delay_ms", 500)
        s.max_items = self.get_setting("max_items", 200)
        s.paste_all_count = self.get_setting("paste_all_count", 0)
        return s

    # ── Tab rules ─────────────────────────────────────────────────────────
    def save_tab_rule(self, rule: TabRule) -> int:
        try:
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
        except sqlite3.Error as exc:
            logger.error("save_tab_rule failed: %s", exc)
            return -1

    def get_tab_rules(self) -> List[TabRule]:
        try:
            rows = self.conn.execute("SELECT * FROM tab_rules").fetchall()
            return [TabRule(id=r[0], app_pattern=r[1], tab_name=r[2], enabled=bool(r[3]))
                    for r in rows]
        except sqlite3.Error:
            return []

    def delete_tab_rule(self, rule_id: int):
        try:
            self.conn.execute("DELETE FROM tab_rules WHERE id=?", (rule_id,))
            self.conn.commit()
        except sqlite3.Error as exc:
            logger.error("delete_tab_rule failed: %s", exc)

    # ── Helpers ───────────────────────────────────────────────────────────
    def _delete_image_files(self, paths: List[str]):
        """Best-effort deletion of image files (1.7)."""
        for path in paths:
            if path:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError as exc:
                    logger.warning("Could not delete image %s: %s", path, exc)

    def _row_to_item(self, row) -> ClipboardItem:
        keys = row.keys()
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
            is_sensitive=bool(row["is_sensitive"]) if "is_sensitive" in keys else False,
            position=row["position"] if "position" in keys else None,
        )

    # ── Snippets (5.4) ────────────────────────────────────────────────────
    def add_snippet(self, snippet: Snippet) -> int:
        try:
            cur = self.conn.execute(
                "INSERT OR REPLACE INTO snippets (name, trigger, content, created_at) VALUES (?,?,?,?)",
                (snippet.name, snippet.trigger, snippet.content, snippet.created_at)
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.Error as exc:
            logger.error("add_snippet failed: %s", exc)
            return -1

    def get_snippets(self) -> List[Snippet]:
        try:
            rows = self.conn.execute("SELECT * FROM snippets ORDER BY name").fetchall()
            return [Snippet(id=r[0], name=r[1], trigger=r[2], content=r[3], created_at=r[4])
                    for r in rows]
        except sqlite3.Error:
            return []

    def delete_snippet(self, snippet_id: int):
        try:
            self.conn.execute("DELETE FROM snippets WHERE id=?", (snippet_id,))
            self.conn.commit()
        except sqlite3.Error as exc:
            logger.error("delete_snippet failed: %s", exc)

    def find_snippet_by_trigger(self, trigger: str) -> Optional[Snippet]:
        try:
            row = self.conn.execute(
                "SELECT * FROM snippets WHERE trigger=? LIMIT 1", (trigger,)
            ).fetchone()
            if row:
                return Snippet(id=row[0], name=row[1], trigger=row[2],
                               content=row[3], created_at=row[4])
        except sqlite3.Error:
            pass
        return None

    # ── Exclusions (5.6) ──────────────────────────────────────────────────
    def get_exclusions(self) -> List[AppExclusion]:
        try:
            rows = self.conn.execute("SELECT * FROM exclusions").fetchall()
            return [AppExclusion(id=r[0], process_name=r[1], enabled=bool(r[2]))
                    for r in rows]
        except sqlite3.Error:
            return []

    def add_exclusion(self, process_name: str) -> int:
        try:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO exclusions (process_name, enabled) VALUES (?,1)",
                (process_name,)
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.Error as exc:
            logger.error("add_exclusion failed: %s", exc)
            return -1

    def delete_exclusion(self, exclusion_id: int):
        try:
            self.conn.execute("DELETE FROM exclusions WHERE id=?", (exclusion_id,))
            self.conn.commit()
        except sqlite3.Error as exc:
            logger.error("delete_exclusion failed: %s", exc)

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
