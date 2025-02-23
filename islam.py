import logging
import random
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from apscheduler.jobstores.base import JobLookupError
from ayarlar import BOT_TOKEN, WORDS

# Logging yapılandırması
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Oyun ve oyuncu bilgilerini saklamak için kullanılan sözlükler
games = {}
players = {}
job_references = {}
daily_scores = {}
weekly_scores = {}
daily_wins = {}
weekly_wins = {}

# /start komutu ile oyunu başlatan fonksiyon
async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in games:
        games[chat_id] = {
            "players": [],
            "word": "",
            "shuffled_word": "",
            "current_word_index": 0,
            "hints_given": 0,
            "scores": {},
            "game_active": True
        }

    # Günlük ve haftalık skorları sıfırlama
    games[chat_id]["scores"] = {}
    daily_scores[chat_id] = {}
    weekly_scores[chat_id] = {}
    daily_wins[chat_id] = {}
    weekly_wins[chat_id] = {}
    games[chat_id]["game_active"] = True

    # Oyuna katılmak için buton oluşturma
    keyboard = [[InlineKeyboardButton("✅ OYUNA 🩵 KATIL ✅", callback_data='join_game')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Oyuna katılma mesajını gönderme
    message = await context.bot.send_message(chat_id, text='•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n🤗 Telegramdaki İlk ve Tek..\n🕌 İslami Kelime Bulma Oyunuyum\n\n🔖 Size Birbirinden Farklı 10 Kelime Soracağım\nOyuna Katılmak İsterseniz\n👇🏻 Aşağıdaki Butona Tıklayınız.. 👇🏻\n\n•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•', reply_markup=reply_markup)    
    

    # 10 saniye sonra oyunu başlatma ve mesajı silme
    context.job_queue.run_once(start_game, 10, data=chat_id)
    context.job_queue.run_once(delete_message, 10, data={"chat_id": chat_id, "message_id": message.message_id})


# Mesajı silen fonksiyon
async def delete_message(context: CallbackContext) -> None:
    job_data = context.job.data
    await context.bot.delete_message(job_data["chat_id"], job_data["message_id"])

# Oyuna katılma butonuna basıldığında çalıştırılan fonksiyon
async def join_game(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    user_name = query.from_user.first_name


# Oyunun başlamasını kontrol eden fonksiyon
async def check_start_game(context: CallbackContext) -> None:
    chat_id = context.job.data
    game = games[chat_id]

    if len(game["players"]) == 0:
        await context.bot.send_message(chat_id, text=(
            "------------------------\n"
            "10 saniye boyunca hiç kimse oyuna başlamak istemedi,\n"
            "bu sebeple oyuna BAŞLAMIYORUM...\n\n"
            "oyuna başlamak istersiniz\n"
            ">>> /start <<< komutuna tıklayınız\n"
            "-----------------------"
        ))
    else:
        await start_game(context)
 




    # Oyuncuyu oyuna ekleme ve puanını sıfırlama
    if user_id not in games[chat_id]["players"]:
        games[chat_id]["players"].append(user_id)
        games[chat_id]["scores"][user_id] = 0
        players[user_id] = user_name
        if user_id not in daily_scores[chat_id]:
            daily_scores[chat_id][user_id] = 0
        if user_id not in weekly_scores[chat_id]:
            weekly_scores[chat_id][user_id] = 0
        if user_id not in daily_wins[chat_id]:
            daily_wins[chat_id][user_id] = 0
        if user_id not in weekly_wins[chat_id]:
            weekly_wins[chat_id][user_id] = 0
        await query.answer(text="Oyuna katıldınız!", show_alert=True)
    else:
        await query.answer(text="Zaten oyundasınız!", show_alert=True)

# Oyunu başlatan fonksiyon
async def start_game(context: CallbackContext) -> None:
    chat_id = context.job.data
    game = games[chat_id]
    
    # Rastgele bir kelime seçme ve harflerini karıştırma
    game["word"] = random.choice(WORDS)
    game["shuffled_word"] = ''.join(random.sample(game["word"], len(game["word"])))
    game["current_word_index"] = 0
    game["hints_given"] = 0

    participant_count = len(game["players"])
    await context.bot.send_message(chat_id, text=(
        "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
        f"🤗 Oyuna 👉🏻 {participant_count} 👈🏻 Kişi Katıldı\n\n"
        "⏳ 3 Saniye İçinde Başlıyoruz....\n\n"
        "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
    ))
    time.sleep(3)
    await ask_word(context)

# Kelimeyi soran fonksiyon
async def ask_word(context: CallbackContext) -> None:
    chat_id = context.job.data
    game = games[chat_id]

    if not game["game_active"]:
        return

    # Önceki işler varsa kaldırma
    if chat_id in job_references:
        for job in job_references[chat_id]:
            try:
                job.schedule_removal()
            except JobLookupError:
                continue
        job_references[chat_id] = []

    # Yeni kelimeyi seçme ve karıştırma
    game["current_word_index"] += 1
    if game["current_word_index"] > 10:
        await end_game(context)
        return

    game["word"] = random.choice(WORDS)
    game["shuffled_word"] = ''.join(random.sample(game["word"], len(game["word"])))
    game["hints_given"] = 0
    game["hint_indices"] = list(range(len(game["word"])))
    random.shuffle(game["hint_indices"])

    word = game["shuffled_word"]
    reply_text = (
        "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
        f"✍🏻 {game['current_word_index']}. KELİME SORUNUZ..\n\n"
        "🤔 Kelimeyi Tahmin Edin...\n\n"
        f"🔍 Harfler :  👉🏻 {' '.join(word)} 👈🏻\n\n"
        f"✍🏻 Kelime   :  👉🏻 {' '.join('_' for _ in word)} 👈🏻\n\n"
        "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
    )
    await context.bot.send_message(chat_id, text=reply_text)
    
    # İpucu ve kontrol işleri için zamanlayıcıları ayarlama
    job_references[chat_id] = [
        context.job_queue.run_once(give_hint, 10, data=chat_id),
        context.job_queue.run_once(check_word, 100, data=chat_id)  # Süreyi 100 saniyeye çıkardık
    ]

# İpucu veren fonksiyon
async def give_hint(context: CallbackContext) -> None:
    chat_id = context.job.data
    game = games[chat_id]

    if not game["game_active"]:
        return

    if game["hints_given"] < len(game["word"]):
        # Kalan harflerin indekslerini bulma
        remaining_indices = game["hint_indices"][game["hints_given"]:]
        if remaining_indices:
            random_index = remaining_indices[0]
            hint = game["word"][random_index]
            game["hints_given"] += 1
            display_word = list('_' * len(game["word"]))
            for i in game["hint_indices"][:game["hints_given"]]:
                display_word[i] = game["word"][i]
            remaining_time = 100 - (game["hints_given"] * 10)
            reply_text = (
                "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
                f"{game['hints_given']}. 💡 İpucu:  👉🏻 {hint} 👈🏻 Harfinin Doğru Yeri..\n\n"
                f"😅 Kelime    :  👉🏻 {' '.join(display_word)} 👈🏻\n\n"
                f"⏳ Kalan Süreniz << {remaining_time} Saniye >>\n\n"
                "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
            )
            await context.bot.send_message(chat_id, text=reply_text)
        
        if game["hints_given"] < len(game["word"]):
            job_references[chat_id].append(context.job_queue.run_once(give_hint, 10, data=chat_id))
    else:
        # Tüm ipuçları verildiğinde ve kimse doğru cevabı bulamadığında tüm oyunculardan 3 puan eksiltme
        word = game["word"]
        await context.bot.send_message(chat_id, text=(
            "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
            "Bu Kadar İpucuna Rağmen\n"
            "Kimse Doğru Kelimeyi Yazmadı\n"
            "Bu Sebeple Tüm Oyunculardan\n"
            "<< 3 >> Puan Eksiltiyorum\n\n"
            f"👀 Aranan Kelime...\n🏷 👉🏻👉🏻 {word} 👈🏻👈🏻 idi..\n\n"
            "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
        ))
        for player in game["players"]:
            game["scores"][player] -= 3
        job_references[chat_id].append(context.job_queue.run_once(ask_word, 3, data=chat_id))

# Kelimenin doğru olup olmadığını kontrol eden fonksiyon
async def check_word(context: CallbackContext) -> None:
    chat_id = context.job.data
    game = games[chat_id]

    if not game["game_active"]:
        return

    word = game["word"]
    
    await context.bot.send_message(chat_id, text=(
    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
    "Kimse Belirtilen Süre İçinde\n"
    "Doğru Kelimeyi Bulamadı\n\n"
    f"Doğru Kelime.. 👉🏻👉🏻 {word} 👈🏻👈🏻 olacaktı..\n\n"
    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
    ))
    
    job_references[chat_id].append(context.job_queue.run_once(ask_word, 3, data=chat_id))

# Oyunu bitiren fonksiyon
async def end_game(context: CallbackContext) -> None:
    chat_id = context.job.data
    game = games[chat_id]

    if chat_id in job_references:
        for job in job_references[chat_id]:
            try:
                job.schedule_removal()
            except JobLookupError:
                continue
        job_references[chat_id] = []

    scores = game["scores"]
    score_list = "\n".join(f"{players[player]}: {score}" for player, score in scores.items())
    winner = max(scores, key=scores.get)
    winner_name = players[winner]

    # Günlük ve haftalık skor tablosunu güncelleme
    daily_scores[chat_id][winner] += scores[winner]
    weekly_scores[chat_id][winner] += scores[winner]
    daily_wins[chat_id][winner] += 1
    weekly_wins[chat_id][winner] += 1

    game["game_active"] = False
    
    await context.bot.send_message(chat_id, text=(
    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
    "Oyun Bitti...\n\n"
    f"Alınan Puanlar..:\n{score_list}\n\nBu Turu Kazanan...\n🤗 {winner_name} "
    "Kendisini Tebrik Ediyoruz...\n\n"
    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
    )) 
    
    
    # Yeni oyun başlatmak için mesaj gönderme
    await context.bot.send_message(chat_id, text=(
        "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
        "😎 Yeni Bir Oyuna Başlamak İçin,\n"
        "☺️ Aşağıdaki Komuta Tıklayın...\n\n"
        "✅ ✅ ✅ /start ✅ ✅ ✅\n\n"
        "♻️ Yeni Kelime Tavsiyesi yada\n‼️ Hata Bildirimi Yapmak İsterseniz\n\n"
        "👨🏻‍💻 @iletisimROBOT aracılığı ile sahibime ulaşabilirsiniz\n\n"
        "┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
    ))

# Tekrar oyun başlatma fonksiyonu
async def restart_game(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id

    await query.message.delete()
    await start(update.callback_query, context)

# Gelen mesajları işleyen fonksiyon
async def handle_message(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    message_text = update.message.text
    
    if chat_id in games:
        if user_id in games[chat_id]["players"]:
            game = games[chat_id]
            word = game["word"]
            
            if message_text.lower() == word.lower():
                correct_letters = sum(1 for a, b in zip(message_text, word) if a.lower() == b.lower())
                game["scores"][user_id] += correct_letters
                await context.bot.send_message(chat_id, text=(
                        "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
                        f"Tebrikler...\n🥰 {players[user_id]} Kelimeyi Buldu..!\n"
                        f"✅ {correct_letters} Puan Kazandı!\n\n"
                        "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
                        ))
                daily_scores[chat_id][user_id] += correct_letters
                weekly_scores[chat_id][user_id] += correct_letters
                if chat_id in job_references:
                    for job in job_references[chat_id]:
                        try:
                            job.schedule_removal()
                        except JobLookupError:
                            continue
                job_references[chat_id] = []
                job_references[chat_id].append(context.job_queue.run_once(ask_word, 3, data=chat_id))
        else:
            await context.bot.send_message(chat_id, text=(
                "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
                "‼️ Kardeşim Sen Oyunda Değilsin\n"
                "🖐🏻 Lütfen Yeni Oyun Başlayana Kadar Bekle\n\n"
                "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
            ))

# Soruyu pas geçme fonksiyonu
async def skip_question(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id in games:
        if games[chat_id]["game_active"]:
            if user_id in games[chat_id]["players"]:
                game = games[chat_id]
                if user_id in game["scores"]:
                    game["scores"][user_id] -= 1
                else:
                    game["scores"][user_id] = -1
                word = game["word"]
                user_name = players[user_id]
                await context.bot.send_message(chat_id, text=(
                    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
                    f"⭕️ Soruyu Pas Geçen ({user_name}),\n"
                    "⛔️ Kendisinden - 1 - Puan Siliyorum\n\n"
                    f"🔎 Aranan Kelime..\n👉🏻👉🏻 {word} 👈🏻👈🏻 idi..\n\n"
                    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
                ))
                if chat_id in job_references:
                    for job in job_references[chat_id]:
                        try:
                            job.schedule_removal()
                        except JobLookupError:
                            continue
                job_references[chat_id] = []
                job_references[chat_id].append(context.job_queue.run_once(ask_word, 3, data=chat_id))
            else:
                await context.bot.send_message(chat_id, text=(
                    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
                    "‼️ Kardeşim Sen Oyunda Değilsin\n"
                    "🖐🏻 Lütfen Yeni Oyun Başlayana Kadar Bekle\n\n"
                    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
                ))
        else:
            await context.bot.send_message(chat_id, text=(
                    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
                    "‼️ Oyun Bitti.. -atla- Komutu işe yaramaz\n\n"
                    "😎 Yeni Oyuna Başlamak İstersen,\n"
                    "☺️ Aşağıdaki Komuta Tıklamalısın...\n\n"
                    "✅ ✅ ✅ /start ✅ ✅ ✅\n\n"
                    "♻️ Yeni Kelime Tavsiyesi yada\n‼️ Hata Bildirimi Yapmak İstersen\n\n"
                    "👨🏻‍💻 @iletisimROBOT aracılığı ile sahibime ulaşabilirsin\n\n"
                    "┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
                   
                ))

# Oyunu bitirme komutu
async def end_game_command(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id in games:
        if user_id in games[chat_id]["players"]:
            context.job_queue.run_once(end_game, 0, data=chat_id)
        else:
            await context.bot.send_message(chat_id, text=(
                    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•\n\n"
                    "‼️ Kardeşim Sen Oyunda Değilsin\n"
                    "🖐🏻 Lütfen Yeni Oyun Başlayana Kadar Bekle\n\n"
                    "•┈••✦❥❀❁ 🤍 ❁❥❀✦••┈•"
            ))

# Ana fonksiyon
def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Komut ve mesaj işleyicilerini ekleme
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(join_game, pattern='join_game'))
    application.add_handler(CallbackQueryHandler(restart_game, pattern='restart_game'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("atla", skip_question))
    application.add_handler(CommandHandler("bitir", end_game_command))
    
    # Bot'u çalıştırma
    application.run_polling()

if __name__ == '__main__':
    main()