import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from src.config import DB_PATH, DAILY_CALORIE_TARGET, DAILY_PROTEIN_TARGET, DAILY_CARBS_TARGET, DAILY_FAT_TARGET
from src.utils.logger import get_logger
from src.utils.exception import DatabaseError, UserNotFoundError

log = get_logger(__name__)


class MealDatabase:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or DB_PATH)
        log.debug("MealDatabase using path: %s", self.db_path)
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            raise DatabaseError(f"Cannot open database at {self.db_path}: {e}") from e
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE,
                name TEXT,
                calorie_target INTEGER DEFAULT 2200,
                protein_target INTEGER DEFAULT 150,
                carbs_target INTEGER DEFAULT 250,
                fat_target INTEGER DEFAULT 70,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                meal_type TEXT,
                image_path TEXT,
                foods TEXT NOT NULL,
                total_calories INTEGER,
                total_protein_g INTEGER,
                total_carbs_g INTEGER,
                total_fat_g INTEGER,
                meal_description TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()
        conn.close()

    def get_or_create_user(self, telegram_id=None, name=None):
        conn = sqlite3.connect(self.db_path)

        if telegram_id:
            cursor = conn.execute(
                "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = cursor.fetchone()
            if row:
                conn.close()
                return row[0]

        now = datetime.now().isoformat()
        cursor = conn.execute(
            """INSERT INTO users (telegram_id, name, calorie_target, protein_target,
                                  carbs_target, fat_target, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                telegram_id,
                name or "User",
                DAILY_CALORIE_TARGET,
                DAILY_PROTEIN_TARGET,
                DAILY_CARBS_TARGET,
                DAILY_FAT_TARGET,
                now,
            ),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        log.info("Created new user id=%s telegram_id=%s", user_id, telegram_id)
        return user_id

    def get_user_targets(self, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT calorie_target, protein_target, carbs_target, fat_target, name
               FROM users WHERE id = ?""",
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise UserNotFoundError(f"No user found with id={user_id}")
        return {
            "calorie_target": row[0],
            "protein_target": row[1],
            "carbs_target": row[2],
            "fat_target": row[3],
            "name": row[4],
        }

    def update_user_targets(self, user_id, calories=None, protein=None, carbs=None, fat=None):
        conn = sqlite3.connect(self.db_path)
        targets = self.get_user_targets(user_id)
        conn.execute(
            """UPDATE users SET calorie_target=?, protein_target=?, carbs_target=?, fat_target=?
               WHERE id=?""",
            (
                calories or targets["calorie_target"],
                protein or targets["protein_target"],
                carbs or targets["carbs_target"],
                fat or targets["fat_target"],
                user_id,
            ),
        )
        conn.commit()
        conn.close()

    def log_meal(self, user_id, analysis, meal_type=None, image_path=None):
        conn = sqlite3.connect(self.db_path)
        now = datetime.now()
        conn.execute(
            """INSERT INTO meals 
            (user_id, timestamp, date, meal_type, image_path, foods, 
             total_calories, total_protein_g, total_carbs_g, total_fat_g, meal_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                now.isoformat(),
                now.strftime("%Y-%m-%d"),
                meal_type,
                str(image_path) if image_path else None,
                json.dumps(analysis.get("foods", [])),
                analysis.get("total_calories", 0),
                analysis.get("total_protein_g", 0),
                analysis.get("total_carbs_g", 0),
                analysis.get("total_fat_g", 0),
                analysis.get("meal_description", ""),
            ),
        )
        conn.commit()
        conn.close()
        log.info("Meal logged: user=%s type=%s cal=%s", user_id, meal_type, analysis.get("total_calories", 0))
        return {"status": "logged", "calories": analysis.get("total_calories", 0)}

    def get_daily_summary(self, user_id, target_date=None):
        if target_date is None:
            target_date = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT total_calories, total_protein_g, total_carbs_g, total_fat_g,
                      meal_description, meal_type, timestamp
               FROM meals WHERE user_id = ? AND date = ? ORDER BY timestamp""",
            (user_id, target_date),
        )
        meals = cursor.fetchall()
        conn.close()

        if not meals:
            return {
                "date": target_date,
                "meals": [],
                "total_calories": 0,
                "total_protein_g": 0,
                "total_carbs_g": 0,
                "total_fat_g": 0,
                "meal_count": 0,
            }

        total_cal = sum(m[0] for m in meals)
        total_pro = sum(m[1] for m in meals)
        total_carb = sum(m[2] for m in meals)
        total_fat = sum(m[3] for m in meals)

        meal_list = []
        for m in meals:
            meal_list.append({
                "calories": m[0],
                "protein_g": m[1],
                "carbs_g": m[2],
                "fat_g": m[3],
                "description": m[4],
                "meal_type": m[5],
                "time": m[6],
            })

        return {
            "date": target_date,
            "meals": meal_list,
            "total_calories": total_cal,
            "total_protein_g": total_pro,
            "total_carbs_g": total_carb,
            "total_fat_g": total_fat,
            "meal_count": len(meals),
        }

    def get_weekly_history(self, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT date, 
                      SUM(total_calories), SUM(total_protein_g),
                      SUM(total_carbs_g), SUM(total_fat_g),
                      COUNT(*)
               FROM meals 
               WHERE user_id = ? AND date >= date('now', '-7 days')
               GROUP BY date ORDER BY date""",
            (user_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        history = []
        for r in rows:
            history.append({
                "date": r[0],
                "total_calories": r[1],
                "total_protein_g": r[2],
                "total_carbs_g": r[3],
                "total_fat_g": r[4],
                "meal_count": r[5],
            })

        return history