"""
Telegram Bot Dự Đoán BCR - Tự động phân tích và chọn bàn có cầu đẹp nhất bằng AI
Yêu cầu: Python 3.8+, pip install python-telegram-bot numpy
"""

import re
import json
import os
import numpy as np
from typing import List, Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==================== CẤU HÌNH ====================
TOKEN = "8988356466:AAH_1_Lx_JSrHI1KFRZCbXVULFRQFropCCM"
ADMIN_IDS = [5968572366]  # THAY BẰNG ID CỦA BẠN
DATA_FILE = "bcr_data.json"

# Cấu trúc dữ liệu
table_data: Dict[str, List[str]] = {}  # Lịch sử kết quả các bàn
table_stats: Dict[str, Dict] = {}  # Thống kê thắng thua

# ==================== KHỞI TẠO ====================
def load_data():
    global table_data, table_stats
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            table_data = data.get("tables", {})
            table_stats = data.get("stats", {})
    else:
        # Tạo 12 bàn mặc định C01-C12
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

# ==================== THUẬT TOÁN AI - ĐÁNH GIÁ CẦU ====================
def analyze_pattern(seq: List[str]) -> Dict:
    """Phân tích cầu và trả về dự đoán"""
    if len(seq) < 5:
        return {"prediction": None, "confidence": 0, "pattern": "Chưa đủ dữ liệu", "score": 0}
    
    last_3 = seq[-3:]
    # Cầu Bệt
    if last_3.count(last_3[0]) == 3:
        conf = 85 + (len(seq[-6:]) if len(seq) >= 6 else 0)  # Bệt càng dài càng tin
        return {"prediction": last_3[0], "confidence": min(98, conf), "pattern": f"Cầu Bệt {last_3[0]}", "score": 95}
    
    # Cầu 1-1
    if len(seq) >= 4 and seq[-4] == seq[-2] and seq[-3] == seq[-1] and seq[-4] != seq[-3]:
        return {"prediction": seq[-2], "confidence": 75, "pattern": "Cầu 1-1 (Đan)", "score": 85}
    
    # Cầu 2-2
    if len(seq) >= 6:
        last_6 = seq[-6:]
        if last_6[0] == last_6[1] and last_6[2] == last_6[3] and last_6[4] == last_6[5]:
            return {"prediction": last_6[4], "confidence": 80, "pattern": "Cầu 2-2", "score": 88}
    
    # Xu hướng
    recent = seq[-10:]
    banker_count = recent.count("B")
    player_count = recent.count("P")
    if banker_count > player_count + 2:
        return {"prediction": "P", "confidence": 65, "pattern": "Xu hướng bệt Banker, bắt đảo Player", "score": 70}
    if player_count > banker_count + 2:
        return {"prediction": "B", "confidence": 65, "pattern": "Xu hướng bệt Player, bắt đảo Banker", "score": 70}
    
    return {"prediction": None, "confidence": 30, "pattern": "Cầu lộn xộn", "score": 40}

def calculate_win_rate(seq: List[str], last_n: int = 20) -> Dict:
    """Tính tỷ lệ thắng"""
    if len(seq) < 3:
        return {"banker_win_rate": 33.3, "player_win_rate": 33.3, "tie_rate": 33.4, "total_bets": 0}
    recent = seq[-last_n:] if len(seq) >= last_n else seq
    total = len(recent)
    return {
        "banker_win_rate": round(recent.count("B") / total * 100, 1),
        "player_win_rate": round(recent.count("P") / total * 100, 1),
        "tie_rate": round(recent.count("T") / total * 100, 1),
        "total_bets": total
    }

def update_battle_stats(table: str, result: str):
    """Cập nhật tổng thắng thua"""
    if table not in table_stats:
        table_stats[table] = {"banker_total": 0, "player_total": 0, "banker_streak": 0, "player_streak": 0, "current_streak": 0, "last_result": None}
    stats = table_stats[table]
    if result == "B":
        stats["banker_total"] += 1
stats["current_streak"] = stats["current_streak"] + 1 if stats["last_result"] == "B" else 1
        stats["banker_streak"] = max(stats["banker_streak"], stats["current_streak"])
        stats["last_result"] = "B"
    elif result == "P":
        stats["player_total"] += 1
        stats["current_streak"] = stats["current_streak"] + 1 if stats["last_result"] == "P" else 1
        stats["player_streak"] = max(stats["player_streak"], stats["current_streak"])
        stats["last_result"] = "P"
    else:
        stats["current_streak"] = 0
        stats["last_result"] = "T"

# ==================== AI CHỌN BÀN ĐẸP NHẤT ====================
def calculate_table_beauty_score(table_name: str) -> Dict:
    """Tính điểm đẹp của bàn dựa trên nhiều yếu tố AI"""
    seq = table_data.get(table_name, [])
    if len(seq) < 5:
        return {"score": 0, "reason": "Chưa đủ dữ liệu", "prediction": None, "confidence": 0}
    
    pattern = analyze_pattern(seq)
    win_rate = calculate_win_rate(seq)
    
    # Các yếu tố tính điểm
    score = 0
    reasons = []
    
    # 1. Độ tin cậy của cầu (tối đa 40 điểm)
    if pattern["confidence"] >= 80:
        score += 40
        reasons.append(f"Cầu đẹp: {pattern['pattern']} (độ tin cậy {pattern['confidence']}%)")
    elif pattern["confidence"] >= 60:
        score += 25
        reasons.append(f"Cầu khá: {pattern['pattern']}")
    elif pattern["confidence"] >= 40:
        score += 10
        reasons.append(f"Cầu trung bình: {pattern['pattern']}")
    else:
        reasons.append("Cầu lộn xộn, khó bắt")
    
    # 2. Chênh lệch tỷ lệ thắng (tối đa 30 điểm)
    diff = abs(win_rate["banker_win_rate"] - win_rate["player_win_rate"])
    if diff > 20:
        score += 30
        reasons.append(f"Chênh lệch tỷ lệ lớn: {diff:.1f}%")
    elif diff > 10:
        score += 20
        reasons.append(f"Chênh lệch tỷ lệ trung bình: {diff:.1f}%")
    elif diff > 5:
        score += 10
    
    # 3. Độ dài chuỗi bệt gần đây (tối đa 20 điểm)
    recent = seq[-10:] if len(seq) >= 10 else seq
    max_streak = 1
    current = 1
    for i in range(1, len(recent)):
        if recent[i] == recent[i-1] and recent[i] != "T":
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 1
    if max_streak >= 4:
        score += 20
        reasons.append(f"Xuất hiện bệt {max_streak} ván")
    elif max_streak >= 3:
        score += 10
        reasons.append(f"Có bệt {max_streak} ván")
    
    # 4. Số ván gần đây không có Hòa (tối đa 10 điểm)
    tie_count = recent.count("T")
    if tie_count == 0:
        score += 10
        reasons.append("Không có Hòa trong 10 ván gần nhất")
    
    return {
        "score": min(100, score),
        "reason": " | ".join(reasons) if reasons else "Bàn bình thường",
        "prediction": pattern["prediction"],
        "confidence": pattern["confidence"],
        "pattern": pattern["pattern"]
    }

def find_best_table() -> Tuple[str, Dict]:
    """Tìm bàn có điểm đẹp nhất"""
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

# ==================== HIỂN THỊ ====================
def get_score_display(table: str) -> str:
    if table not in table_stats:
        return "🏦 Banker: 0 - 0 👤 Player"
    stats = table_stats[table]
    banker = stats["banker_total"]
    player = stats["player_total"]
    total = banker + player
    if total > 0:
        banker_percent = banker / total * 100
        bar_len = 20
        banker_bar = int(banker_percent / 100 * bar_len)
        bar = "█" * banker_bar + "░" * (bar_len - banker_bar)
    else:
        bar = "░░░░░░░░░░░░░░░░░░░░"
    return f"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃    🏦 BANKER vs PLAYER 👤     ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  {bar}  ┃
┃  🏦 {banker} điểm                    👤 {player} điểm  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛"""

def get_all_tables_summary() -> str:
    """Tóm tắt tất cả các bàn để hiển thị"""
    msg = "📊 TÌNH HÌNH CÁC BÀN HIỆN TẠI\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    scores = []
    for table_name in sorted(table_data.keys()):
        seq = table_data[table_name]
        analysis = calculate_table_beauty_score(table_name)
        scores.append((table_name, analysis["score"]))
        if len(seq) == 0:
            msg += f"┃ {table_name}: ⚪ Chưa có dữ liệu\n"
        else:
            recent_str = ''.join(seq[-5:]) if len(seq) >= 5 else ''.join(seq)
            msg += f"┃ {table_name}: {'⭐' * min(3, analysis['score']//30)} Điểm {analysis['score']} | {recent_str}\n"
    
    # Sắp xếp theo điểm và tìm bàn đẹp nhất
    scores.sort(key=lambda x: x[1], reverse=True)
    best = scores[0] if scores else ("C01", 0)
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏆 BÀN ĐẸP NHẤT: {best[0]} (Điểm {best[1]})\n"
    return msg

# ==================== XỬ LÝ KẾT QUẢ ====================
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
    win_rate = calculate_win_rate(seq)
    pattern = analyze_pattern(seq)
    if pattern["prediction"] == "B":
        return {"B": min(95, win_rate["banker_win_rate"] + 25), "P": max(5, win_rate["player_win_rate"] - 15), "T": max(0, win_rate["tie_rate"] - 5), "recommend": "B"}
    elif pattern["prediction"] == "P":
        return {"B": max(5, win_rate["banker_win_rate"] - 15), "P": min(95, win_rate["player_win_rate"] + 25), "T": max(0, win_rate["tie_rate"] - 5), "recommend": "P"}
    return {"B": win_rate["banker_win_rate"], "P": win_rate["player_win_rate"], "T": win_rate["tie_rate"], "recommend": "B" if win_rate["banker_win_rate"] > win_rate["player_win_rate"] else "P"}

# ==================== COMMANDS ====================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 TÌM BÀN ĐẸP NHẤT", callback_data="find_best")],
        [InlineKeyboardButton("📊 XEM TẤT CẢ BÀN", callback_data="all_tables")],
        [InlineKeyboardButton("📋 THỐNG KÊ", callback_data="stats")]
    ])
    await update.message.reply_text(
        f"🤖 BOT DỰ ĐOÁN BCR - AI CHỌN BÀN\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ TÍNH NĂNG:\n"
        f"• AI tự động phân tích 12 bàn C01-C12\n"
        f"• Tìm bàn có cầu đẹp nhất để đánh\n"
        f"• Hiển thị tỷ lệ thắng % từng cửa\n\n"
        f"CÁCH DÙNG:\n"
        f"1️⃣ Nhập kết quả: B, P, T (kèm tên bàn hoặc không)\n"
        f"   Ví dụ: C05 B hoặc chỉ B (sẽ ghi vào bàn đẹp nhất)\n"
        f"2️⃣ Bấm nút 'TÌM BÀN ĐẸP NHẤT' để AI chọn bàn\n"
        f"3️⃣ Xem tỷ số và dự đoán chi tiết\n\n"
        f"📋 Lệnh:\n/stats - Xem thống kê bàn đẹp nhất\n/reset - Xóa lịch sử bàn đẹp nhất\n/list - Xem tất cả bàn",
        reply_markup=keyboard
    )

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_all_tables_summary()
    await update.message.reply_text(msg)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    best_table, analysis = find_best_table()
    if best_table is None or len(table_data.get(best_table, [])) == 0:
        await update.message.reply_text("📭 Chưa có dữ liệu ở bất kỳ bàn nào. Hãy nhập kết quả B/P/T để bắt đầu.")
        return
    
    seq = table_data[best_table]
    win_percent = predict_win_percentage(seq)
    score_display = get_score_display(best_table)
msg = f"""
🎯 BÀN ĐẸP NHẤT HIỆN TẠI: {best_table}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 {analysis['pattern'] if analysis['pattern'] else 'Đang phân tích'}
🎯 Điểm AI: {analysis['score']}/100
💡 {analysis['reason']}

📊 TỶ LỆ THẮNG DỰ KIẾN:
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🏦 BANKER: {win_percent['B']}%  █{'█' * int(win_percent['B']/4)}{'░' * (25 - int(win_percent['B']/4))} ┃
┃ 👤 PLAYER:  {win_percent['P']}%  █{'█' * int(win_percent['P']/4)}{'░' * (25 - int(win_percent['P']/4))} ┃
┃ 🤝 HÒA:     {win_percent['T']}%  █{'█' * int(win_percent['T']/4)}{'░' * (25 - int(win_percent['T']/4))} ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛

💡 KHUYẾN NGHỊ: {'🏦 ĐẶT BANKER' if win_percent['recommend'] == 'B' else '👤 ĐẶT PLAYER' if win_percent['recommend'] == 'P' else '🤝 CÂN NHẮC HÒA'}
{score_display}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📜 Lịch sử gần đây: {''.join(seq[-10:]) if len(seq) >= 10 else ''.join(seq)}
"""
    await update.message.reply_text(msg)

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Chỉ admin mới có quyền reset.")
        return
    best_table, _ = find_best_table()
    if best_table and best_table in table_data:
        table_data[best_table] = []
        if best_table in table_stats:
            table_stats[best_table] = {"banker_total": 0, "player_total": 0, "banker_streak": 0, "player_streak": 0, "current_streak": 0, "last_result": None}
        save_data()
        await update.message.reply_text(f"🗑️ Đã xóa lịch sử bàn đẹp nhất {best_table}.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Xử lý nhập kết quả kèm tên bàn (VD: C05 B)
    match = re.match(r'([Cc](\d{2}))\s+([BPT])', text)
    if match:
        table_name = match.group(1).upper()
        result = match.group(3)
        if table_name not in table_data:
            await update.message.reply_text(f"❌ Bàn {table_name} không tồn tại. Các bàn hợp lệ: C01-C12")
            return
        # Ghi kết quả vào bàn cụ thể
        table_data[table_name].append(result)
        if len(table_data[table_name]) > 50:
            table_data[table_name].pop(0)
        update_battle_stats(table_name, result)
        save_data()
        
        # Phân tích bàn đó
        analysis = calculate_table_beauty_score(table_name)
        win_percent = predict_win_percentage(table_data[table_name])
        score_display = get_score_display(table_name)
        
        await update.message.reply_text(f"""
✅ Đã ghi nhận bàn {table_name}: {result}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 {analysis['pattern']}
🎯 Điểm đẹp: {analysis['score']}/100
{score_display}
📊 Dự đoán tiếp: {'🏦 BANKER' if win_percent['recommend'] == 'B' else '👤 PLAYER' if win_percent['recommend'] == 'P' else '🤝 HÒA'} ({max(win_percent['B'], win_percent['P'], win_percent['T'])}%)
""")
        return
    
    # Xử lý nhập kết quả thường (B, P, T) - ghi vào bàn đẹp nhất
    result = parse_result(text)
    if result:
        best_table, _ = find_best_table()
        if best_table is None:
            best_table = "C01"
        
        table_data[best_table].append(result)
        if len(table_data[best_table]) > 50:
            table_data[best_table].pop(0)
        update_battle_stats(best_table, result)
        save_data()
        
        # Tìm lại bàn đẹp nhất sau khi cập nhật
        new_best_table, new_analysis = find_best_table()
        win_percent = predict_win_percentage(table_data[new_best_table])
        score_display = get_score_display(new_best_table)
        
        await update.message.reply_text(f"""
✅ Đã ghi nhận {result} vào bàn đẹp nhất ({new_best_table})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 BÀN ĐẸP NHẤT HIỆN TẠI: {new_best_table}
🎯 Điểm AI: {new_analysis['score']}/100
💡 {new_analysis['reason']}
{score_display}
📊 Dự đoán tiếp: {'🏦 BANKER' if win_percent['recommend'] == 'B' else '👤 PLAYER' if win_percent['recommend'] == 'P' else '🤝 HÒA'}
🔮 Độ tin cậy: {new_analysis['confidence']}%
""")
    else:
await update.message.reply_text("❓ Nhập B, P, T hoặc 'C05 B' để ghi kết quả vào bàn cụ thể")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "find_best":
        best_table, analysis = find_best_table()
        if best_table is None or len(table_data.get(best_table, [])) == 0:
            await query.edit_message_text("📭 Chưa có dữ liệu. Hãy nhập kết quả B/P/T để bắt đầu phân tích.")
            return
        
        seq = table_data[best_table]
        win_percent = predict_win_percentage(seq)
        score_display = get_score_display(best_table)
        
        msg = f"""
🏆 BÀN ĐẸP NHẤT: {best_table}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Điểm AI: {analysis['score']}/100
📐 {analysis['pattern']}
💡 {analysis['reason']}

📊 TỶ LỆ THẮNG:
🏦 BANKER: {win_percent['B']}%  👤 PLAYER: {win_percent['P']}%  🤝 HÒA: {win_percent['T']}%

💡 KHUYẾN NGHỊ: {'🏦 ĐẶT BANKER' if win_percent['recommend'] == 'B' else '👤 ĐẶT PLAYER'}
{score_display}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📜 {''.join(seq[-15:]) if len(seq) >= 15 else ''.join(seq)}
"""
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 TÌM LẠI", callback_data="find_best")]])
        await query.edit_message_text(msg, reply_markup=keyboard)
    
    elif query.data == "all_tables":
        msg = get_all_tables_summary()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏆 TÌM BÀN ĐẸP NHẤT", callback_data="find_best")]])
        await query.edit_message_text(msg, reply_markup=keyboard)
    
    elif query.data == "stats":
        await cmd_stats(update, context)

# ==================== KHỞI CHẠY ====================
def main():
    load_data()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("Bot AI đang chạy - Tự động chọn bàn có cầu đẹp nhất...")
    app.run_polling()

if name == "__main__":
    main()