import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from src.config import DB_PATH


class MealDatabase:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or DB_PATH)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                meal_type TEXT,
                image_path TEXT,
                foods TEXT NOT NULL,
                total_calories INTEGER,
                total_protein_g INTEGER,
                total_carbs_g INTEGER,
                total_fat_g INTEGER,
                meal_description TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_meal(self, analysis, meal_type=None, image_path=None):
        conn = sqlite3.connect(self.db_path)
        now = datetime.now()
        conn.execute(
            """INSERT INTO meals 
            (timestamp, date, meal_type, image_path, foods, 
             total_calories, total_protein_g, total_carbs_g, total_fat_g, meal_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
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
        return {"status": "logged", "calories": analysis.get("total_calories", 0)}

    def get_daily_summary(self, target_date=None):
        if target_date is None:
            target_date = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT total_calories, total_protein_g, total_carbs_g, total_fat_g,
                      meal_description, meal_type, timestamp
               FROM meals WHERE date = ? ORDER BY timestamp""",
            (target_date,),
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

    def get_weekly_history(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT date, 
                      SUM(total_calories), SUM(total_protein_g),
                      SUM(total_carbs_g), SUM(total_fat_g),
                      COUNT(*)
               FROM meals 
               WHERE date >= date('now', '-7 days')
               GROUP BY date ORDER BY date""",
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