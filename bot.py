"""
Telegram Bot Dự Đoán BCR - AI chọn bàn đẹp nhất
"""

import re
import json
import os
from typing import List, Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "8988356466:AAH_1_Lx_JSrHI1KFRZCbXVULFRQFropCCM"
ADMIN_IDS = [123456789]  # THAY BẰNG ID CỦA BẠN
DATA_FILE = "bcr_data.json"

table_data: Dict[str, List[str]] = {}
table_stats: Dict[str, Dict] = {}

def load_data():
    global table_data, table_stats
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            table_data = data.get("tables", {})
            table_stats = data.get("stats", {})
    else:
        table_data = {f"C{i:02d}": [] for i in range(1, 13)}
        table_stats = {}
        for i in range(1, 13):
            table_stats[f"C{i:02d}"] = {
                "banker_total": 0, "player_total": 0,
                "banker_streak": 0, "player_streak": 0,
                "current_streak": 0, "last_result": None
            }

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({"tables": table_data, "stats": table_stats}, f, ensure_ascii=False, indent=2)

def analyze_pattern(seq: List[str]) -> Dict:
    if len(seq) < 5:
        return {"prediction": None, "confidence": 0, "pattern": "Chua du du lieu", "score": 0}
    last_3 = seq[-3:]
    if last_3.count(last_3[0]) == 3:
        return {"prediction": last_3[0], "confidence": 85, "pattern": f"Cau Bet {last_3[0]}", "score": 95}
    if len(seq) >= 4 and seq[-4] == seq[-2] and seq[-3] == seq[-1] and seq[-4] != seq[-3]:
        return {"prediction": seq[-2], "confidence": 75, "pattern": "Cau 1-1", "score": 85}
    if len(seq) >= 6:
        last_6 = seq[-6:]
        if last_6[0] == last_6[1] and last_6[2] == last_6[3] and last_6[4] == last_6[5]:
            return {"prediction": last_6[4], "confidence": 80, "pattern": "Cau 2-2", "score": 88}
    recent = seq[-10:]
    banker_count = recent.count("B")
    player_count = recent.count("P")
    if banker_count > player_count + 2:
        return {"prediction": "P", "confidence": 65, "pattern": "Bat dao Player", "score": 70}
    if player_count > banker_count + 2:
        return {"prediction": "B", "confidence": 65, "pattern": "Bat dao Banker", "score": 70}
    return {"prediction": None, "confidence": 30, "pattern": "Cau lon xon", "score": 40}

def update_battle_stats(table: str, result: str):
    if table not in table_stats:
        table_stats[table] = {"banker_total": 0, "player_total": 0, "banker_streak": 0, "player_streak": 0, "current_streak": 0, "last_result": None}
    stats = table_stats[table]
    if result == "B":
        stats["banker_total"] += 1
        stats["current_streak"] = stats["current_streak"] + 1 if stats["last_result"] == "B" else 1
        if stats["current_streak"] > stats["banker_streak"]:
            stats["banker_streak"] = stats["current_streak"]
        stats["last_result"] = "B"
    elif result == "P":
        stats["player_total"] += 1
        stats["current_streak"] = stats["current_streak"] + 1 if stats["last_result"] == "P" else 1
        if stats["current_streak"] > stats["player_streak"]:
            stats["player_streak"] = stats["current_streak"]
        stats["last_result"] = "P"
    else:
        stats["current_streak"] = 0
        stats["last_result"] = "T"

def calculate_table_beauty_score(table_name: str) -> Dict:
    seq = table_data.get(table_name, [])
    if len(seq) < 5:
        return {"score": 0, "reason": "Chua du du lieu", "prediction": None, "confidence": 0}
    pattern = analyze_pattern(seq)
    score = pattern["score"]
    reasons = [pattern["pattern"]]
    return {"score": min(100, score), "reason": " | ".join(reasons), "prediction": pattern["prediction"], "confidence": pattern["confidence"], "pattern": pattern["pattern"]}

def find_best_table() -> Tuple[str, Dict]:
    best_table = None
    best_score = -1
best_analysis = None
    for table_name in table_data.keys():
        analysis = calculate_table_beauty_score(table_name)
        if analysis["score"] > best_score:
            best_score = analysis["score"]
            best_table = table_name
            best_analysis = analysis
    return best_table, best_analysis

def parse_result(text: str) -> Optional[str]:
    text = text.upper().strip()
    if "/" in text or "BOT" in text:
        return None
    if re.search(r'\b([BPT])\b', text):
        return re.search(r'\b([BPT])\b', text).group(1)
    if "BANKER" in text or "NHÀ CÁI" in text:
        return "B"
    if "PLAYER" in text or "NHÀ CON" in text:
        return "P"
    if "TIE" in text or "HÒA" in text:
        return "T"
    return None

def predict_win_percentage(seq: List[str]) -> Dict:
    if len(seq) < 5:
        return {"B": 33.3, "P": 33.3, "T": 33.4, "recommend": None}
    recent = seq[-20:] if len(seq) >= 20 else seq
    total = len(recent)
    b = recent.count("B") / total * 100
    p = recent.count("P") / total * 100
    t = recent.count("T") / total * 100
    pattern = analyze_pattern(seq)
    if pattern["prediction"] == "B":
        b = min(95, b + 25)
        p = max(5, p - 15)
    elif pattern["prediction"] == "P":
        p = min(95, p + 25)
        b = max(5, b - 15)
    total_new = b + p + t
    return {"B": round(b / total_new * 100, 1), "P": round(p / total_new * 100, 1), "T": round(t / total_new * 100, 1), "recommend": pattern["prediction"] if pattern["prediction"] else ("B" if b > p else "P")}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot dang chay! Gui B, P, T de ghi ket qua.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = parse_result(update.message.text)
    if result:
        best_table, _ = find_best_table()
        if best_table is None:
            best_table = "C01"
        table_data[best_table].append(result)
        if len(table_data[best_table]) > 50:
            table_data[best_table].pop(0)
        update_battle_stats(best_table, result)
        save_data()
        await update.message.reply_text(f"Da ghi nhan {result} vao ban {best_table}")
    else:
        await update.message.reply_text("Nhap B, P, T hoac Banker/Player/Tie")

def main():
    load_data()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot AI dang chay...")
    app.run_polling()

if name == "__main__":
    main()
