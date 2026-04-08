"""Calorie tracker tool for logging food intake and calculating comprehensive nutrition."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from nanobot.agent.tools.base import Tool


USDA_NUTRIENT_MAP = {
    1008: "calories",
    1003: "protein",
    1005: "carbohydrate",
    1004: "fat",
    1079: "fiber",
    2000: "sugar",
    1009: "starch",
    1051: "water",
    1018: "alcohol",
    262: "caffeine",
    1258: "saturated_fat",
    1292: "monounsaturated_fat",
    1293: "polyunsaturated_fat",
    1257: "trans_fat",
    1272: "omega_3",
    1273: "omega_6",
    1213: "cholesterol",
    1106: "vitamin_a",
    1162: "vitamin_c",
    1114: "vitamin_d",
    1159: "vitamin_e",
    1225: "vitamin_k",
    1165: "thiamin",
    1166: "riboflavin",
    1175: "niacin",
    1177: "vitamin_b5",
    1176: "vitamin_b6",
    1178: "biotin",
    1187: "folate",
    1174: "vitamin_b12",
    1180: "choline",
    1087: "calcium",
    1089: "iron",
    1090: "magnesium",
    1091: "phosphorus",
    1092: "potassium",
    1093: "sodium",
    1095: "zinc",
    1098: "copper",
    1101: "manganese",
    1103: "selenium",
    1100: "iodine",
    1096: "chromium",
    1102: "molybdenum",
    1111: "chloride",
    1210: "tryptophan",
    1211: "threonine",
    1212: "isoleucine",
    1213: "leucine",
    1214: "lysine",
    1215: "methionine",
    1217: "phenylalanine",
    1219: "valine",
    1221: "histidine",
}


NUTRIENT_DISPLAY = {
    "calories": {"name": "Calories", "unit": "kcal", "cat": "energy", "precision": 0},
    "protein": {"name": "Protein", "unit": "g", "cat": "macro", "precision": 1},
    "carbohydrate": {"name": "Carbohydrate", "unit": "g", "cat": "macro", "precision": 1},
    "fat": {"name": "Fat", "unit": "g", "cat": "macro", "precision": 1},
    "fiber": {"name": "Fiber", "unit": "g", "cat": "macro", "precision": 1},
    "sugar": {"name": "Sugars", "unit": "g", "cat": "macro", "precision": 1},
    "starch": {"name": "Starch", "unit": "g", "cat": "macro", "precision": 1},
    "water": {"name": "Water", "unit": "g", "cat": "macro", "precision": 1},
    "alcohol": {"name": "Alcohol", "unit": "g", "cat": "macro", "precision": 1},
    "caffeine": {"name": "Caffeine", "unit": "mg", "cat": "other", "precision": 1},
    "saturated_fat": {"name": "Saturated Fat", "unit": "g", "cat": "fatty_acid", "precision": 1},
    "monounsaturated_fat": {
        "name": "Monounsaturated Fat",
        "unit": "g",
        "cat": "fatty_acid",
        "precision": 1,
    },
    "polyunsaturated_fat": {
        "name": "Polyunsaturated Fat",
        "unit": "g",
        "cat": "fatty_acid",
        "precision": 1,
    },
    "trans_fat": {"name": "Trans Fat", "unit": "g", "cat": "fatty_acid", "precision": 1},
    "omega_3": {"name": "Omega-3", "unit": "g", "cat": "fatty_acid", "precision": 2},
    "omega_6": {"name": "Omega-6", "unit": "g", "cat": "fatty_acid", "precision": 2},
    "cholesterol": {"name": "Cholesterol", "unit": "mg", "cat": "other", "precision": 0},
    "vitamin_a": {"name": "Vitamin A", "unit": "mcg", "cat": "vitamin", "precision": 0},
    "vitamin_c": {"name": "Vitamin C", "unit": "mg", "cat": "vitamin", "precision": 1},
    "vitamin_d": {"name": "Vitamin D", "unit": "mcg", "cat": "vitamin", "precision": 1},
    "vitamin_e": {"name": "Vitamin E", "unit": "mg", "cat": "vitamin", "precision": 1},
    "vitamin_k": {"name": "Vitamin K", "unit": "mcg", "cat": "vitamin", "precision": 1},
    "thiamin": {"name": "Thiamin (B1)", "unit": "mg", "cat": "vitamin", "precision": 2},
    "riboflavin": {"name": "Riboflavin (B2)", "unit": "mg", "cat": "vitamin", "precision": 2},
    "niacin": {"name": "Niacin (B3)", "unit": "mg", "cat": "vitamin", "precision": 2},
    "vitamin_b5": {"name": "Pantothenic Acid (B5)", "unit": "mg", "cat": "vitamin", "precision": 2},
    "vitamin_b6": {"name": "Vitamin B6", "unit": "mg", "cat": "vitamin", "precision": 2},
    "biotin": {"name": "Biotin (B7)", "unit": "mcg", "cat": "vitamin", "precision": 1},
    "folate": {"name": "Folate (B9)", "unit": "mcg", "cat": "vitamin", "precision": 0},
    "vitamin_b12": {"name": "Vitamin B12", "unit": "mcg", "cat": "vitamin", "precision": 2},
    "choline": {"name": "Choline", "unit": "mg", "cat": "vitamin", "precision": 1},
    "calcium": {"name": "Calcium", "unit": "mg", "cat": "mineral", "precision": 0},
    "iron": {"name": "Iron", "unit": "mg", "cat": "mineral", "precision": 1},
    "magnesium": {"name": "Magnesium", "unit": "mg", "cat": "mineral", "precision": 0},
    "phosphorus": {"name": "Phosphorus", "unit": "mg", "cat": "mineral", "precision": 0},
    "potassium": {"name": "Potassium", "unit": "mg", "cat": "mineral", "precision": 0},
    "sodium": {"name": "Sodium", "unit": "mg", "cat": "mineral", "precision": 0},
    "zinc": {"name": "Zinc", "unit": "mg", "cat": "mineral", "precision": 1},
    "copper": {"name": "Copper", "unit": "mg", "cat": "mineral", "precision": 2},
    "manganese": {"name": "Manganese", "unit": "mg", "cat": "mineral", "precision": 2},
    "selenium": {"name": "Selenium", "unit": "mcg", "cat": "mineral", "precision": 1},
    "iodine": {"name": "Iodine", "unit": "mcg", "cat": "mineral", "precision": 1},
    "chromium": {"name": "Chromium", "unit": "mcg", "cat": "mineral", "precision": 1},
    "molybdenum": {"name": "Molybdenum", "unit": "mcg", "cat": "mineral", "precision": 1},
    "chloride": {"name": "Chloride", "unit": "mg", "cat": "mineral", "precision": 0},
    "tryptophan": {"name": "Tryptophan", "unit": "g", "cat": "amino_acid", "precision": 2},
    "threonine": {"name": "Threonine", "unit": "g", "cat": "amino_acid", "precision": 2},
    "isoleucine": {"name": "Isoleucine", "unit": "g", "cat": "amino_acid", "precision": 2},
    "leucine": {"name": "Leucine", "unit": "g", "cat": "amino_acid", "precision": 2},
    "lysine": {"name": "Lysine", "unit": "g", "cat": "amino_acid", "precision": 2},
    "methionine": {"name": "Methionine", "unit": "g", "cat": "amino_acid", "precision": 2},
    "phenylalanine": {"name": "Phenylalanine", "unit": "g", "cat": "amino_acid", "precision": 2},
    "valine": {"name": "Valine", "unit": "g", "cat": "amino_acid", "precision": 2},
    "histidine": {"name": "Histidine", "unit": "g", "cat": "amino_acid", "precision": 2},
}

NUTRIENT_KEYS = list(NUTRIENT_DISPLAY.keys())


class CalorieTrackerTool(Tool):
    """Tool to log food intake, calculate comprehensive nutrition, view daily logs, manage recipes and custom foods."""

    def __init__(self, workspace: Path | None = None, timezone: str = "UTC"):
        self._workspace = workspace or Path.cwd()
        self._tz = timezone
        self._log_dir = self._workspace / "calorie_logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(__file__).parent / "calorie_database.json"
        self._usda_db_path = Path(__file__).parent.parent.parent / "food_data_generic.db"
        self._targets_path = Path(__file__).parent / "nutrient_targets.json"
        self._custom_foods_path = self._workspace / "custom_foods.json"
        self._recipes_path = self._workspace / "recipes.json"
        self._database = self._load_database()
        self._usda_conn = self._connect_usda_db()
        self._targets = self._load_targets()
        self._custom_foods = self._load_custom_foods()
        self._recipes = self._load_recipes()

    def _now(self) -> datetime:
        try:
            return datetime.now(tz=ZoneInfo(self._tz))
        except Exception:
            return datetime.now().astimezone()

    def _today_str(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def _load_database(self) -> dict:
        try:
            if self._db_path.exists():
                return json.loads(self._db_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"foods": {}}

    def _connect_usda_db(self) -> sqlite3.Connection | None:
        try:
            if self._usda_db_path.exists():
                return sqlite3.connect(str(self._usda_db_path))
        except Exception:
            pass
        return None

    def _find_usda_food(self, query: str) -> dict | None:
        if not self._usda_conn:
            return None
        query_lower = query.lower().strip()
        cur = self._usda_conn.cursor()
        cur.execute(
            "SELECT fdc_id, description, data_type FROM usda_food WHERE LOWER(description) LIKE ? LIMIT 20",
            (f"%{query_lower}%",),
        )
        rows = cur.fetchall()
        for fdc_id, description, data_type in rows:
            if query_lower in description.lower() or description.lower() in query_lower:
                return self._get_usda_nutrients(fdc_id, description)
        if rows:
            return self._get_usda_nutrients(rows[0][0], rows[0][1])
        return None

    def _get_usda_nutrients(self, fdc_id: int, description: str) -> dict:
        result = {"name": description, "usda": True}
        cur = self._usda_conn.cursor()
        cur.execute(
            "SELECT nutrient_id, amount FROM usda_food_nutrient WHERE fdc_id = ?",
            (fdc_id,),
        )
        for nutrient_id, amount in cur.fetchall():
            key = USDA_NUTRIENT_MAP.get(nutrient_id)
            if key:
                result[f"{key}_per_100g"] = amount
        return result

    def _load_targets(self) -> dict:
        try:
            if self._targets_path.exists():
                return json.loads(self._targets_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"targets": {}}

    def _load_custom_foods(self) -> dict:
        try:
            if self._custom_foods_path.exists():
                return json.loads(self._custom_foods_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"foods": {}}

    def _save_custom_foods(self) -> None:
        self._custom_foods_path.write_text(
            json.dumps(self._custom_foods, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _load_recipes(self) -> dict:
        try:
            if self._recipes_path.exists():
                return json.loads(self._recipes_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"recipes": {}}

    def _save_recipes(self) -> None:
        self._recipes_path.write_text(
            json.dumps(self._recipes, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _get_log_path(self, date: str | None = None) -> Path:
        if date is None:
            date = self._today_str()
        return self._log_dir / f"{date}.json"

    def _load_log(self, date: str | None = None) -> list[dict]:
        path = self._get_log_path(date)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_log(self, entries: list[dict], date: str | None = None) -> None:
        path = self._get_log_path(date)
        path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    def _find_food(self, query: str) -> dict | None:
        query_lower = query.lower().strip()
        for source in [self._database.get("foods", {}), self._custom_foods.get("foods", {})]:
            if query_lower in source:
                return {"name": query_lower, **source[query_lower]}
            for food_name, food_data in source.items():
                if query_lower == food_name:
                    return {"name": food_name, **food_data}
            for food_name, food_data in source.items():
                aliases = food_data.get("aliases", [])
                for alias in aliases:
                    if query_lower == alias.lower():
                        return {"name": food_name, **food_data}
            for food_name, food_data in source.items():
                if query_lower in food_name.lower() or food_name.lower() in query_lower:
                    return {"name": food_name, **food_data}
            for food_name, food_data in source.items():
                aliases = food_data.get("aliases", [])
                for alias in aliases:
                    if query_lower in alias.lower() or alias.lower() in query_lower:
                        return {"name": food_name, **food_data}
        usda_food = self._find_usda_food(query)
        if usda_food:
            return usda_food
        return None

    def _find_recipe(self, query: str) -> dict | None:
        query_lower = query.lower().strip()
        recipes = self._recipes.get("recipes", {})
        if query_lower in recipes:
            return {"name": query_lower, **recipes[query_lower]}
        for rname, rdata in recipes.items():
            if query_lower == rname or query_lower in rname.lower():
                return {"name": rname, **rdata}
        return None

    def _calc_nutrition(self, food: dict, weight_g: float) -> dict:
        ratio = weight_g / 100.0
        result = {}
        for key in NUTRIENT_KEYS:
            db_key = f"{key}_per_100g"
            val = food.get(db_key, 0) * ratio
            prec = NUTRIENT_DISPLAY[key]["precision"]
            if prec == 0:
                result[key] = round(val)
            else:
                result[key] = round(val, prec)
        return result

    def _calc_recipe_nutrition(self, recipe: dict) -> dict:
        total = {key: 0 for key in NUTRIENT_KEYS}
        for ingredient in recipe.get("ingredients", []):
            food_name = ingredient.get("food", "")
            weight = ingredient.get("weight_g", 0)
            food_data = self._find_food(food_name)
            if food_data:
                nutr = self._calc_nutrition(food_data, weight)
                for key in NUTRIENT_KEYS:
                    total[key] += nutr.get(key, 0)
        for key in NUTRIENT_KEYS:
            prec = NUTRIENT_DISPLAY[key]["precision"]
            if prec == 0:
                total[key] = round(total[key])
            else:
                total[key] = round(total[key], prec)
        return total

    def _get_target(self, nutrient: str) -> float | None:
        targets = self._targets.get("targets", {})
        user_targets = self._workspace / "nutrient_user_targets.json"
        if user_targets.exists():
            try:
                user_data = json.loads(user_targets.read_text(encoding="utf-8"))
                if nutrient in user_data.get("targets", {}):
                    return user_data["targets"][nutrient]
            except Exception:
                pass
        if nutrient in targets:
            return targets[nutrient].get("default_target")
        return None

    def _is_upper_limit(self, nutrient: str) -> bool:
        targets = self._targets.get("targets", {})
        if nutrient in targets:
            return targets[nutrient].get("upper_limit", False)
        return False

    @property
    def name(self) -> str:
        return "calorie_tracker"

    @property
    def description(self) -> str:
        return (
            "Track food intake with comprehensive nutrition calculation (84 nutrients). "
            "Actions: log, lookup, daily, summary, barcode, custom_food (add/list/delete), "
            "recipe (create/list/delete/info), copy_day, edit_entry, delete_entry, targets (view/set)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "log",
                        "lookup",
                        "daily",
                        "summary",
                        "barcode",
                        "custom_food",
                        "recipe",
                        "copy_day",
                        "edit_entry",
                        "delete_entry",
                        "targets",
                    ],
                    "description": "Action to perform",
                },
                "food": {"type": "string", "description": "Name of the food item"},
                "weight_g": {"type": "number", "description": "Weight in grams"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "meal": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner", "snack"],
                    "description": "Meal type",
                },
                "notes": {"type": "string", "description": "Additional notes"},
                "barcode": {"type": "string", "description": "Barcode number for lookup"},
                "sub_action": {
                    "type": "string",
                    "description": "Sub-action for custom_food, recipe, or targets",
                },
                "name": {"type": "string", "description": "Name for custom food or recipe"},
                "ingredients": {
                    "type": "array",
                    "description": "Recipe ingredients: [{food, weight_g}]",
                },
                "servings": {"type": "number", "description": "Number of servings in recipe"},
                "entry_index": {"type": "integer", "description": "Index of entry to edit/delete"},
                "new_food": {"type": "string", "description": "New food name when renaming"},
                "new_weight_g": {"type": "number", "description": "New weight when editing"},
                "new_meal": {"type": "string", "description": "New meal type when editing"},
                "nutrient": {"type": "string", "description": "Nutrient key for target setting"},
                "target_value": {"type": "number", "description": "New target value"},
                "nutrients": {
                    "type": "object",
                    "description": "Nutrient values per 100g for custom food",
                },
                "aliases": {"type": "array", "description": "Alternative names for custom food"},
                "source_date": {"type": "string", "description": "Date to copy entries from"},
                "dest_date": {"type": "string", "description": "Date to copy entries to"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        food: str | None = None,
        weight_g: float | None = None,
        date: str | None = None,
        meal: str | None = None,
        notes: str | None = None,
        barcode: str | None = None,
        sub_action: str | None = None,
        name: str | None = None,
        ingredients: list[dict] | None = None,
        servings: float | None = None,
        entry_index: int | None = None,
        new_food: str | None = None,
        new_weight_g: float | None = None,
        new_meal: str | None = None,
        nutrient: str | None = None,
        target_value: float | None = None,
        nutrients: dict | None = None,
        aliases: list[str] | None = None,
        source_date: str | None = None,
        dest_date: str | None = None,
        **kwargs: Any,
    ) -> str:
        if action == "log":
            return self._log_food(food, weight_g, date, meal, notes)
        elif action == "lookup":
            return self._lookup_food(food)
        elif action == "daily":
            return self._view_daily(date)
        elif action == "summary":
            return self._view_summary(date)
        elif action == "barcode":
            return await self._lookup_barcode(barcode)
        elif action == "custom_food":
            return self._manage_custom_food(sub_action, name, nutrients, aliases)
        elif action == "recipe":
            return self._manage_recipe(sub_action, name, ingredients, servings, food)
        elif action == "copy_day":
            return self._copy_day(source_date, dest_date)
        elif action == "edit_entry":
            return self._edit_entry(date, entry_index, new_food, new_weight_g, new_meal, notes)
        elif action == "delete_entry":
            return self._delete_entry(date, entry_index)
        elif action == "targets":
            return self._manage_targets(sub_action, nutrient, target_value)
        return f"Unknown action: {action}."

    def _log_food(
        self,
        food: str | None,
        weight_g: float | None,
        date: str | None,
        meal: str | None,
        notes: str | None,
    ) -> str:
        if not food:
            return "Error: food name is required."

        recipe_data = self._find_recipe(food)
        if recipe_data and weight_g is None:
            nutr = self._calc_recipe_nutrition(recipe_data)
            now = self._now()
            total_weight = sum(ing.get("weight_g", 0) for ing in recipe_data.get("ingredients", []))
            entry = {
                "time": now.strftime("%H:%M"),
                "timestamp": now.isoformat(),
                "food": f"recipe: {recipe_data['name']}",
                "weight_g": total_weight,
                "meal": meal or "unspecified",
                "notes": notes or "",
                "is_recipe": True,
                **nutr,
            }
            log = self._load_log(date)
            log.append(entry)
            self._save_log(log, date)
            lines = [
                f"Logged recipe: {recipe_data['name']} ({len(recipe_data.get('ingredients', []))} ingredients) at {entry['time']}"
            ]
            lines.append(f"  Total weight: {total_weight}g | Calories: {nutr['calories']} kcal")
            lines.append(
                f"  Protein: {nutr['protein']}g | Carbs: {nutr['carbohydrate']}g | Fat: {nutr['fat']}g"
            )
            lines.append(f"  Fiber: {nutr['fiber']}g | Sugar: {nutr['sugar']}g")
            if meal:
                lines.append(f"  Meal: {meal}")
            daily_total = self._calc_daily_total(log)
            lines.append(f"\nDaily total so far: {daily_total['calories']} kcal")
            return "\n".join(lines)

        if weight_g is None:
            return "Error: weight_g is required. Provide the weight in grams."
        if weight_g <= 0:
            return "Error: weight must be a positive number."

        food_data = self._find_food(food)
        if food_data is None:
            return (
                f"Food '{food}' not found. "
                f"Available: {', '.join(list(self._database.get('foods', {}).keys())[:15])}..."
            )

        nutrition = self._calc_nutrition(food_data, weight_g)
        now = self._now()
        entry = {
            "time": now.strftime("%H:%M"),
            "timestamp": now.isoformat(),
            "food": food_data["name"],
            "weight_g": weight_g,
            "meal": meal or "unspecified",
            "notes": notes or "",
            **nutrition,
        }

        log = self._load_log(date)
        log.append(entry)
        self._save_log(log, date)

        display_date = date or now.strftime("%Y-%m-%d")
        lines = [
            f"Logged: {entry['food']} ({weight_g}g) at {entry['time']}",
            f"  Calories: {nutrition['calories']} kcal | Protein: {nutrition['protein']}g | Carbs: {nutrition['carbohydrate']}g | Fat: {nutrition['fat']}g",
            f"  Fiber: {nutrition['fiber']}g | Sugar: {nutrition['sugar']}g | Sat Fat: {nutrition['saturated_fat']}g",
        ]
        if meal:
            lines.append(f"  Meal: {meal}")
        if notes:
            lines.append(f"  Notes: {notes}")
        lines.append(f"  Date: {display_date}")

        daily_total = self._calc_daily_total(log)
        lines.append(
            f"\nDaily total so far: {daily_total['calories']} kcal | P: {daily_total['protein']}g | C: {daily_total['carbohydrate']}g | F: {daily_total['fat']}g"
        )

        return "\n".join(lines)

    def _lookup_food(self, food: str | None) -> str:
        if not food:
            return "Error: food name is required."

        food_data = self._find_food(food)
        if food_data is None:
            return f"Food '{food}' not found."

        lines = [f"Food: {food_data['name']} (per 100g)", ""]
        lines.append(f"  Calories: {food_data.get('calories_per_100g', 0)} kcal")
        lines.append(f"  Protein: {food_data.get('protein_per_100g', 0)}g")
        lines.append(f"  Carbohydrate: {food_data.get('carbohydrate_per_100g', 0)}g")
        lines.append(f"    Fiber: {food_data.get('fiber_per_100g', 0)}g")
        lines.append(f"    Sugars: {food_data.get('sugar_per_100g', 0)}g")
        lines.append(f"  Fat: {food_data.get('fat_per_100g', 0)}g")
        lines.append(f"    Saturated: {food_data.get('saturated_fat_per_100g', 0)}g")
        lines.append(f"    Monounsaturated: {food_data.get('monounsaturated_fat_per_100g', 0)}g")
        lines.append(f"    Polyunsaturated: {food_data.get('polyunsaturated_fat_per_100g', 0)}g")
        lines.append(f"    Omega-3: {food_data.get('omega_3_per_100g', 0)}g")
        lines.append(f"    Omega-6: {food_data.get('omega_6_per_100g', 0)}g")
        lines.append(f"  Cholesterol: {food_data.get('cholesterol_per_100g', 0)}mg")
        lines.append("")
        lines.append("  Vitamins:")
        for key in [
            "vitamin_a",
            "vitamin_c",
            "vitamin_d",
            "vitamin_e",
            "vitamin_k",
            "thiamin",
            "riboflavin",
            "niacin",
            "vitamin_b5",
            "vitamin_b6",
            "biotin",
            "folate",
            "vitamin_b12",
            "choline",
        ]:
            info = NUTRIENT_DISPLAY[key]
            val = food_data.get(f"{key}_per_100g", 0)
            if val > 0:
                lines.append(f"    {info['name']}: {val}{info['unit']}")
        lines.append("")
        lines.append("  Minerals:")
        for key in [
            "calcium",
            "iron",
            "magnesium",
            "phosphorus",
            "potassium",
            "sodium",
            "zinc",
            "copper",
            "manganese",
            "selenium",
            "iodine",
        ]:
            info = NUTRIENT_DISPLAY[key]
            val = food_data.get(f"{key}_per_100g", 0)
            if val > 0:
                lines.append(f"    {info['name']}: {val}{info['unit']}")
        lines.append("")
        lines.append("  Amino Acids:")
        for key in [
            "tryptophan",
            "threonine",
            "isoleucine",
            "leucine",
            "lysine",
            "methionine",
            "phenylalanine",
            "valine",
            "histidine",
        ]:
            info = NUTRIENT_DISPLAY[key]
            val = food_data.get(f"{key}_per_100g", 0)
            if val > 0:
                lines.append(f"    {info['name']}: {val}{info['unit']}")

        if "per_unit_calories" in food_data:
            lines.append(
                f"\n  Per unit: ~{food_data['per_unit_calories']} kcal ({food_data.get('per_unit_weight_g', '?')}g)"
            )
        aliases = food_data.get("aliases", [])
        if aliases:
            lines.append(f"  Also known as: {', '.join(aliases)}")

        return "\n".join(lines)

    def _view_daily(self, date: str | None) -> str:
        log = self._load_log(date)
        if not log:
            display_date = date or self._today_str()
            return f"No food logged for {display_date}."

        display_date = log[0].get("timestamp", date or self._today_str())[:10]
        lines = [f"Food log for {display_date}:", ""]

        for i, entry in enumerate(log):
            line = f"  [{i}] [{entry.get('time', '?')}] {entry['food']} ({entry['weight_g']}g) - {entry['calories']} kcal"
            if entry.get("meal") and entry["meal"] != "unspecified":
                line += f" [{entry['meal']}]"
            lines.append(line)

        total = self._calc_daily_total(log)
        lines.append("")
        lines.append(
            f"TOTAL: {total['calories']} kcal | P: {total['protein']}g | C: {total['carbohydrate']}g | F: {total['fat']}g"
        )
        lines.append(
            f"  Fiber: {total['fiber']}g | Sugar: {total['sugar']}g | Sat Fat: {total['saturated_fat']}g"
        )

        pct_lines = self._format_pct_targets(total)
        if pct_lines:
            lines.append("")
            lines.append("% Daily Targets:")
            lines.extend(pct_lines)

        warnings = self._check_deficiencies(total)
        if warnings:
            lines.append("")
            lines.append("Low nutrients:")
            lines.extend(f"  WARNING: {w}" for w in warnings)

        return "\n".join(lines)

    def _view_summary(self, date: str | None) -> str:
        log = self._load_log(date)
        if not log:
            display_date = date or self._today_str()
            return f"No food logged for {display_date}."

        display_date = log[0].get("timestamp", date or self._today_str())[:10]
        total = self._calc_daily_total(log)

        meal_totals: dict[str, dict] = {}
        for entry in log:
            m = entry.get("meal", "unspecified")
            if m not in meal_totals:
                meal_totals[m] = {key: 0 for key in NUTRIENT_KEYS}
            for key in NUTRIENT_KEYS:
                meal_totals[m][key] += entry.get(key, 0)

        lines = [f"Daily summary for {display_date}:", ""]

        for meal_name in ["breakfast", "lunch", "dinner", "snack", "unspecified"]:
            if meal_name in meal_totals:
                mt = meal_totals[meal_name]
                label = meal_name if meal_name != "unspecified" else "other"
                lines.append(
                    f"  {label}: {round(mt['calories'])} kcal | "
                    f"P: {round(mt['protein'], 1)}g | C: {round(mt['carbohydrate'], 1)}g | F: {round(mt['fat'], 1)}g"
                )

        lines.append("")
        lines.append(
            f"GRAND TOTAL: {total['calories']} kcal | P: {total['protein']}g | C: {total['carbohydrate']}g | F: {total['fat']}g"
        )
        lines.append(
            f"  Fiber: {total['fiber']}g | Sugar: {total['sugar']}g | Sat Fat: {total['saturated_fat']}g"
        )

        cal_from_protein = total["protein"] * 4
        cal_from_carbs = total["carbohydrate"] * 4
        cal_from_fat = total["fat"] * 9
        total_macro_cal = cal_from_protein + cal_from_carbs + cal_from_fat
        if total_macro_cal > 0:
            lines.append("")
            lines.append(
                f"Macro split: Protein {round(cal_from_protein / total_macro_cal * 100)}% | Carbs {round(cal_from_carbs / total_macro_cal * 100)}% | Fat {round(cal_from_fat / total_macro_cal * 100)}%"
            )

        pct_lines = self._format_pct_targets(total)
        if pct_lines:
            lines.append("")
            lines.append("% Daily Targets:")
            lines.extend(pct_lines)

        warnings = self._check_deficiencies(total)
        if warnings:
            lines.append("")
            lines.append("Below target:")
            lines.extend(f"  {w}" for w in warnings)

        return "\n".join(lines)

    async def _lookup_barcode(self, barcode: str | None) -> str:
        if not barcode:
            return "Error: barcode number is required."

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json",
                    headers={"User-Agent": "nanobot-calorie-tracker/1.0"},
                )
                if resp.status_code != 200:
                    return f"Barcode lookup failed (HTTP {resp.status_code})."

                data = resp.json()
                if data.get("status") != 1:
                    return f"Product not found for barcode {barcode}."

                product = data.get("product", {})
                name = product.get("product_name", "Unknown")
                nutriments = product.get("nutriments", {})

                lines = [f"Product: {name}", f"  Barcode: {barcode}", ""]
                lines.append(f"  Per 100g:")
                lines.append(f"    Calories: {nutriments.get('energy-kcal_100g', 0)} kcal")
                lines.append(f"    Protein: {nutriments.get('proteins_100g', 0)}g")
                lines.append(f"    Carbs: {nutriments.get('carbohydrates_100g', 0)}g")
                lines.append(f"    Fat: {nutriments.get('fat_100g', 0)}g")
                lines.append(f"    Fiber: {nutriments.get('fiber_100g', 0)}g")
                lines.append(f"    Sugar: {nutriments.get('sugars_100g', 0)}g")
                lines.append(f"    Salt: {nutriments.get('salt_100g', 0)}g")

                brands = product.get("brands", "")
                if brands:
                    lines.append(f"  Brand: {brands}")

                categories = product.get("categories", "")
                if categories:
                    lines.append(f"  Categories: {categories}")

                lines.append("")
                lines.append(
                    f"To log this food, use: calorie_tracker(action='log', food='{name}', weight_g=<grams>)"
                )
                return "\n".join(lines)

            except httpx.TimeoutException:
                return "Barcode lookup timed out."
            except Exception as e:
                return f"Barcode lookup error: {e}"

    def _manage_custom_food(
        self,
        sub_action: str | None,
        name: str | None,
        nutrients: dict | None,
        aliases: list[str] | None,
    ) -> str:
        if sub_action == "add":
            if not name:
                return "Error: name is required to add a custom food."
            if not nutrients:
                return "Error: nutrients dict is required. Provide per-100g values like {calories: 100, protein: 10, ...}"

            key = name.lower().strip()
            food_entry = {}
            for nkey in NUTRIENT_KEYS:
                db_key = f"{nkey}_per_100g"
                food_entry[db_key] = nutrients.get(nkey, nutrients.get(db_key, 0))
            if aliases:
                food_entry["aliases"] = aliases
            food_entry["custom"] = True

            self._custom_foods.setdefault("foods", {})[key] = food_entry
            self._save_custom_foods()
            return f"Custom food '{name}' added successfully."

        elif sub_action == "list":
            foods = self._custom_foods.get("foods", {})
            if not foods:
                return "No custom foods saved."
            lines = ["Custom foods:"]
            for fname, fdata in foods.items():
                lines.append(f"  {fname} - {fdata.get('calories_per_100g', 0)} kcal/100g")
            return "\n".join(lines)

        elif sub_action == "delete":
            if not name:
                return "Error: name is required to delete a custom food."
            key = name.lower().strip()
            if key in self._custom_foods.get("foods", {}):
                del self._custom_foods["foods"][key]
                self._save_custom_foods()
                return f"Custom food '{name}' deleted."
            return f"Custom food '{name}' not found."

        return "Error: sub_action required: add, list, or delete."

    def _manage_recipe(
        self,
        sub_action: str | None,
        name: str | None,
        ingredients: list[dict] | None,
        servings: float | None,
        food: str | None,
    ) -> str:
        if sub_action == "create":
            if not name:
                return "Error: name is required to create a recipe."
            if not ingredients:
                return "Error: ingredients list is required. Format: [{food: 'chicken breast', weight_g: 200}, ...]"

            recipe = {
                "ingredients": ingredients,
                "servings": servings or 1,
                "created": self._now().isoformat(),
            }
            nutr = self._calc_recipe_nutrition(recipe)
            recipe["nutrition_per_recipe"] = nutr

            self._recipes.setdefault("recipes", {})[name.lower().strip()] = recipe
            self._save_recipes()
            lines = [f"Recipe '{name}' created with {len(ingredients)} ingredients:"]
            for ing in ingredients:
                lines.append(f"  {ing['food']}: {ing['weight_g']}g")
            lines.append(
                f"\nTotal: {nutr['calories']} kcal | P: {nutr['protein']}g | C: {nutr['carbohydrate']}g | F: {nutr['fat']}g"
            )
            if servings and servings > 1:
                per_serving = {k: round(v / servings, 1) for k, v in nutr.items()}
                lines.append(f"Per serving ({servings}): {per_serving['calories']} kcal")
            return "\n".join(lines)

        elif sub_action == "list":
            recipes = self._recipes.get("recipes", {})
            if not recipes:
                return "No recipes saved."
            lines = ["Recipes:"]
            for rname, rdata in recipes.items():
                ings = rdata.get("ingredients", [])
                nutr = rdata.get("nutrition_per_recipe", {})
                lines.append(
                    f"  {rname} - {len(ings)} ingredients, {nutr.get('calories', '?')} kcal"
                )
            return "\n".join(lines)

        elif sub_action == "delete":
            if not name:
                return "Error: name is required to delete a recipe."
            key = name.lower().strip()
            if key in self._recipes.get("recipes", {}):
                del self._recipes["recipes"][key]
                self._save_recipes()
                return f"Recipe '{name}' deleted."
            return f"Recipe '{name}' not found."

        elif sub_action == "info":
            if not name:
                return "Error: name is required."
            recipe = self._find_recipe(name)
            if not recipe:
                return f"Recipe '{name}' not found."
            lines = [f"Recipe: {recipe['name']}", f"  Servings: {recipe.get('servings', 1)}", ""]
            lines.append("  Ingredients:")
            for ing in recipe.get("ingredients", []):
                lines.append(f"    {ing['food']}: {ing['weight_g']}g")
            nutr = recipe.get("nutrition_per_recipe", {})
            lines.append(
                f"\n  Total: {nutr.get('calories', '?')} kcal | P: {nutr.get('protein', '?')}g | C: {nutr.get('carbohydrate', '?')}g | F: {nutr.get('fat', '?')}g"
            )
            return "\n".join(lines)

        return "Error: sub_action required: create, list, delete, or info."

    def _copy_day(self, source_date: str | None, dest_date: str | None) -> str:
        if not source_date:
            return "Error: source_date is required (YYYY-MM-DD format)."
        if not dest_date:
            return "Error: dest_date is required (YYYY-MM-DD format)."

        source_log = self._load_log(source_date)
        if not source_log:
            return f"No entries found for {source_date}."

        now = self._now()
        new_log = []
        for entry in source_log:
            new_entry = dict(entry)
            new_entry["timestamp"] = now.isoformat()
            new_entry["time"] = now.strftime("%H:%M")
            new_entry["copied_from"] = source_date
            new_log.append(new_entry)

        self._save_log(new_log, dest_date)
        return f"Copied {len(new_log)} entries from {source_date} to {dest_date}."

    def _edit_entry(
        self,
        date: str | None,
        entry_index: int | None,
        new_food: str | None,
        new_weight_g: float | None,
        new_meal: str | None,
        notes: str | None,
    ) -> str:
        if entry_index is None:
            return "Error: entry_index is required."

        log = self._load_log(date)
        if not log:
            return f"No entries for {date or 'today'}."
        if entry_index < 0 or entry_index >= len(log):
            return f"Invalid index {entry_index}. Valid range: 0-{len(log) - 1}."

        entry = log[entry_index]
        if new_food:
            food_data = self._find_food(new_food)
            if food_data:
                entry["food"] = food_data["name"]
                entry["weight_g"] = new_weight_g or entry["weight_g"]
                nutr = self._calc_nutrition(food_data, entry["weight_g"])
                entry.update(nutr)
            else:
                return f"Food '{new_food}' not found."
        if new_weight_g is not None and not new_food:
            entry["weight_g"] = new_weight_g
            food_data = self._find_food(entry["food"])
            if food_data:
                nutr = self._calc_nutrition(food_data, new_weight_g)
                entry.update(nutr)
        if new_meal:
            entry["meal"] = new_meal
        if notes is not None:
            entry["notes"] = notes

        log[entry_index] = entry
        self._save_log(log, date)
        return f"Entry {entry_index} updated: {entry['food']} ({entry['weight_g']}g) - {entry['calories']} kcal."

    def _delete_entry(self, date: str | None, entry_index: int | None) -> str:
        if entry_index is None:
            return "Error: entry_index is required."

        log = self._load_log(date)
        if not log:
            return f"No entries for {date or 'today'}."
        if entry_index < 0 or entry_index >= len(log):
            return f"Invalid index {entry_index}. Valid range: 0-{len(log) - 1}."

        deleted = log.pop(entry_index)
        self._save_log(log, date)
        return f"Deleted: {deleted['food']} ({deleted['weight_g']}g) - {deleted['calories']} kcal."

    def _manage_targets(
        self,
        sub_action: str | None,
        nutrient: str | None,
        target_value: float | None,
    ) -> str:
        if sub_action == "view":
            targets = self._targets.get("targets", {})
            user_targets_path = self._workspace / "nutrient_user_targets.json"
            user_targets = {}
            if user_targets_path.exists():
                try:
                    user_targets = json.loads(user_targets_path.read_text(encoding="utf-8")).get(
                        "targets", {}
                    )
                except Exception:
                    pass

            lines = ["Nutrient targets:", ""]
            for key, info in NUTRIENT_DISPLAY.items():
                target = user_targets.get(key)
                if target is None:
                    target = targets.get(key, {}).get("default_target")
                if target is not None:
                    suffix = " (custom)" if key in user_targets else ""
                    lines.append(f"  {info['name']}: {target}{info['unit']}{suffix}")
            return "\n".join(lines)

        elif sub_action == "set":
            if not nutrient:
                return "Error: nutrient key is required."
            if target_value is None:
                return "Error: target_value is required."

            nutrient_key = nutrient.lower().strip()
            if nutrient_key not in NUTRIENT_DISPLAY:
                return f"Unknown nutrient: {nutrient}. Valid: {', '.join(NUTRIENT_DISPLAY.keys())}"

            user_targets_path = self._workspace / "nutrient_user_targets.json"
            user_data = {}
            if user_targets_path.exists():
                try:
                    user_data = json.loads(user_targets_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            user_data.setdefault("targets", {})[nutrient_key] = target_value
            user_targets_path.write_text(json.dumps(user_data, indent=2), encoding="utf-8")
            info = NUTRIENT_DISPLAY[nutrient_key]
            return f"Target for {info['name']} set to {target_value}{info['unit']}."

        elif sub_action == "reset":
            if nutrient:
                nutrient_key = nutrient.lower().strip()
                user_targets_path = self._workspace / "nutrient_user_targets.json"
                if user_targets_path.exists():
                    try:
                        user_data = json.loads(user_targets_path.read_text(encoding="utf-8"))
                        if nutrient_key in user_data.get("targets", {}):
                            del user_data["targets"][nutrient_key]
                            user_targets_path.write_text(
                                json.dumps(user_data, indent=2), encoding="utf-8"
                            )
                            return f"Reset {nutrient_key} to default target."
                    except Exception:
                        pass
                return f"No custom target for {nutrient_key}."
            else:
                user_targets_path = self._workspace / "nutrient_user_targets.json"
                if user_targets_path.exists():
                    user_targets_path.unlink()
                return "All custom targets reset to defaults."

        return "Error: sub_action required: view, set, or reset."

    def _calc_daily_total(self, log: list[dict]) -> dict:
        total = {key: 0 for key in NUTRIENT_KEYS}
        for entry in log:
            for key in NUTRIENT_KEYS:
                total[key] += entry.get(key, 0)
        for key in NUTRIENT_KEYS:
            prec = NUTRIENT_DISPLAY[key]["precision"]
            if prec == 0:
                total[key] = round(total[key])
            else:
                total[key] = round(total[key], prec)
        return total

    def _format_pct_targets(self, total: dict) -> list[str]:
        lines = []
        for key in NUTRIENT_KEYS:
            target = self._get_target(key)
            if target and target > 0:
                pct = round(total[key] / target * 100)
                info = NUTRIENT_DISPLAY[key]
                lines.append(
                    f"  {info['name']}: {pct}% ({total[key]}{info['unit']}/{target}{info['unit']})"
                )
        return lines

    def _check_deficiencies(self, total: dict) -> list[str]:
        warnings = []
        for key in NUTRIENT_KEYS:
            target = self._get_target(key)
            if target and target > 0:
                pct = total[key] / target * 100
                info = NUTRIENT_DISPLAY[key]
                if self._is_upper_limit(key):
                    if pct > 100:
                        warnings.append(
                            f"{info['name']}: {round(pct)}% of limit ({total[key]}{info['unit']}/{target}{info['unit']})"
                        )
                else:
                    if pct < 50:
                        warnings.append(
                            f"{info['name']}: only {round(pct)}% of target ({total[key]}{info['unit']}/{target}{info['unit']})"
                        )
        return warnings
