import os
import pytest
from src.database.meal_db import MealDatabase


@pytest.fixture
def db(tmp_path):
    return MealDatabase(db_path=tmp_path / "test.db")


def test_create_user(db):
    user_id = db.get_or_create_user(telegram_id="test_123", name="Test")
    assert user_id == 1

    # Same telegram_id returns same user
    same_id = db.get_or_create_user(telegram_id="test_123")
    assert same_id == 1


def test_log_and_retrieve_meal(db):
    user_id = db.get_or_create_user(telegram_id="test_456", name="Test")

    db.log_meal(user_id, {
        "total_calories": 500,
        "total_protein_g": 25,
        "total_carbs_g": 40,
        "total_fat_g": 30,
        "foods": [{"name": "Burger"}],
        "meal_description": "Test burger",
    }, meal_type="lunch")

    summary = db.get_daily_summary(user_id)
    assert summary["meal_count"] == 1
    assert summary["total_calories"] == 500
    assert summary["total_protein_g"] == 25


def test_separate_users(db):
    user1 = db.get_or_create_user(telegram_id="aaa", name="User1")
    user2 = db.get_or_create_user(telegram_id="bbb", name="User2")

    db.log_meal(user1, {"total_calories": 500, "total_protein_g": 0, "total_carbs_g": 0, "total_fat_g": 0, "foods": [], "meal_description": "meal1"})
    db.log_meal(user2, {"total_calories": 300, "total_protein_g": 0, "total_carbs_g": 0, "total_fat_g": 0, "foods": [], "meal_description": "meal2"})

    s1 = db.get_daily_summary(user1)
    s2 = db.get_daily_summary(user2)

    assert s1["total_calories"] == 500
    assert s2["total_calories"] == 300