---
name: calorie-tracker
description: Track food intake, 84 nutrients, recipes, custom foods, weight, biometrics, exercise, and device sync (Fitbit/Renpho).
metadata: {"nanobot":{"emoji":"🍎","always":true}}
---

# Calorie & Health Tracker

You have three tools for comprehensive health tracking:

1. **calorie_tracker** — Food logging with 84-nutrient analysis
2. **health_tracker** — Weight, biometrics, and health metrics
3. **exercise_tracker** — Exercise logging with calorie burn
4. **device_sync** — Fitbit and Renpho device integration

## When to use

Whenever the user mentions eating, exercising, weighing themselves, or health metrics, proactively log the data. Do NOT wait for the user to ask.

## calorie_tracker — Food & Nutrition

### log — Record food eaten
```
calorie_tracker(action="log", food="chicken breast", weight_g=180, meal="lunch", notes="grilled")
```

### lookup — Find nutrition info (84 nutrients)
```
calorie_tracker(action="lookup", food="avocado")
```

### barcode — Look up packaged food
```
calorie_tracker(action="barcode", barcode="5000159407232")
```

### daily — View entries with % daily targets
```
calorie_tracker(action="daily", date="2026-04-04")
```

### summary — Totals, macro split, % targets, deficiency warnings
```
calorie_tracker(action="summary", date="2026-04-04")
```

### custom_food — Add/manage custom foods
```
calorie_tracker(action="custom_food", sub_action="add", name="My Protein Bar", nutrients={"calories": 200, "protein": 20, ...})
calorie_tracker(action="custom_food", sub_action="list")
calorie_tracker(action="custom_food", sub_action="delete", name="My Protein Bar")
```

### recipe — Create/manage recipes
```
calorie_tracker(action="recipe", sub_action="create", name="Chicken Stir Fry", ingredients=[{"food": "chicken breast", "weight_g": 150}, {"food": "broccoli", "weight_g": 80}])
calorie_tracker(action="recipe", sub_action="list")
calorie_tracker(action="recipe", sub_action="info", name="Chicken Stir Fry")
```

### copy_day / edit_entry / delete_entry
```
calorie_tracker(action="copy_day", source_date="2026-04-03", dest_date="2026-04-04")
calorie_tracker(action="edit_entry", date="2026-04-04", entry_index=0, new_weight_g=200)
calorie_tracker(action="delete_entry", date="2026-04-04", entry_index=0)
```

### targets — View/set nutrient targets
```
calorie_tracker(action="targets", sub_action="view")
calorie_tracker(action="targets", sub_action="set", nutrient="protein", target_value=150)
calorie_tracker(action="targets", sub_action="reset")
```

## health_tracker — Weight & Biometrics

### log_weight
```
health_tracker(action="log_weight", weight_kg=75.5)
health_tracker(action="log_weight", weight_lbs=165)
health_tracker(action="log_weight", weight_kg=75.2, notes="morning fasted")
```

### view_weight
```
health_tracker(action="view_weight")
health_tracker(action="view_weight", start_date="2026-04-01", end_date="2026-04-05")
```

### log_biometric
```
health_tracker(action="log_biometric", biometric_type="blood_pressure", value="120/80")
health_tracker(action="log_biometric", biometric_type="heart_rate", value="68")
health_tracker(action="log_biometric", biometric_type="blood_glucose", value="95")
health_tracker(action="log_biometric", biometric_type="body_temperature", value="36.6")
health_tracker(action="log_biometric", biometric_type="blood_oxygen", value="98")
health_tracker(action="log_biometric", biometric_type="body_fat", value="18.5")
health_tracker(action="log_biometric", biometric_type="cholesterol_total", value="190")
```

Biometric types: blood_pressure, heart_rate, blood_glucose, body_temperature, blood_oxygen, body_fat, muscle_mass, bmi, body_water, bone_mass, visceral_fat, basal_metabolic_rate, cholesterol_total, cholesterol_hdl, cholesterol_ldl, triglycerides, hemoglobin_a1c

### view_biometrics / view_all_biometrics
```
health_tracker(action="view_biometrics", biometric_type="blood_pressure")
health_tracker(action="view_all_biometrics", date="2026-04-05")
```

### delete_weight / delete_biometric
```
health_tracker(action="delete_weight", entry_index=0)
health_tracker(action="delete_biometric", entry_index=0)
```

## exercise_tracker — Workouts

### log_exercise
```
exercise_tracker(action="log_exercise", exercise="running", duration_min=30)
exercise_tracker(action="log_exercise", exercise="weight training", duration_min=45, notes="upper body")
exercise_tracker(action="log_exercise", exercise="cycling", calories_burned=400)
```

Calorie burn is auto-calculated based on exercise type, duration, and body weight (default 70kg, override with user_weight_kg).

### view_exercises / daily_exercise / list_exercises
```
exercise_tracker(action="view_exercises", date="2026-04-05")
exercise_tracker(action="daily_exercise", date="2026-04-05")
exercise_tracker(action="list_exercises")
```

Known exercises: walking, running, jogging, cycling, swimming, weight training, yoga, hiit, jump rope, rowing, elliptical, stairs, hiking, pilates, boxing, dance, tennis, basketball, soccer, golf.

### delete_exercise
```
exercise_tracker(action="delete_exercise", entry_index=0)
```

## device_sync — Fitbit & Apple Health

### setup_fitbit
```
device_sync(action="setup_fitbit", access_token="...", refresh_token="...")
```
Tokens auto-refresh automatically. Once setup with a refresh_token, it will always work.

### sync_fitbit
```
device_sync(action="sync_fitbit", date="2026-04-05")
device_sync(action="sync_fitbit", date="2026-04-05", data_type="activities")
```
Data types: activities, heart_rate, sleep, nutrition, weight.

### import_apple_health
```
device_sync(action="import_apple_health", xml_path="/path/to/export.xml")
```
Export from iPhone: Health app → profile picture → Export All Health Data → extract zip → use export.xml

### view_apple_health
```
device_sync(action="view_apple_health")
device_sync(action="view_apple_health", health_type="Heart Rate")
device_sync(action="view_apple_health", health_type="Body Mass", date="2026-04-05")
```
Apple Health tracks: Steps, Walking/Running Distance, Heart Rate, Resting Heart Rate, HRV, Body Mass, BMI, Body Fat %, Blood Glucose, Blood Pressure, Blood Oxygen, Body Temperature, Sleep, Mindfulness, Workouts, Dietary Energy/Carbs/Protein/Fat/Fiber/Sugar/Water/Caffeine, and more.

### view_fitbit / config
```
device_sync(action="view_fitbit", data_type="activities")
device_sync(action="config")
```

## Rules

1. **Always log food the user mentions** — proactively extract food items
2. **Estimate weights** when not provided (chicken breast ~150-200g, egg ~50g, banana ~120g, etc.)
3. **Break down meals** into ingredients for composite dishes
4. **Log exercise** when user mentions working out
5. **Log weight** when user mentions stepping on a scale
6. **Sync devices** periodically if credentials are configured

## 84 Nutrients tracked

Energy, macros (protein, carbs, fat, fiber, sugar, starch, water, alcohol, caffeine), fatty acids (saturated, mono, poly, trans, omega-3, omega-6), cholesterol, 13 vitamins (A, C, D, E, K, B1, B2, B3, B5, B6, B7, B9, B12, choline), 17 minerals (calcium, iron, magnesium, phosphorus, potassium, sodium, zinc, copper, manganese, selenium, iodine, chromium, molybdenum, chloride), 9 amino acids (tryptophan, threonine, isoleucine, leucine, lysine, methionine, phenylalanine, valine, histidine).

## Example interactions

User: "I had 2 eggs and toast for breakfast"
→ Log: egg (100g), bread (60g), meal=breakfast

User: "Went for a 30 minute run this morning"
→ Log: running (30 min)

User: "I weigh 75kg this morning"
→ Log: weight 75kg

User: "My blood pressure is 120 over 80"
→ Log: blood_pressure 120/80

User: "Sync my Fitbit for today"
→ Sync Fitbit activities, heart rate, sleep, nutrition, weight

User: "Import my Apple Health data"
→ Guide them to export from iPhone Health app, then parse the XML

User: "What's my nutrient intake looking like?"
→ Show summary with % daily targets and warnings
