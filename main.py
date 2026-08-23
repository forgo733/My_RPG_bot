import asyncio
import random
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# === ТОКЕН БОТА ===
TELEGRAM_TOKEN = "8778603732:AAHGLy3BsklI6302GJUZgZiyBYyy85TutFE"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

players = {}

# === 13 УНИКАЛЬНЫХ ПРЕДМЕТОВ (7 Активных + 6 Пассивных) ===
ITEMS = {
    # --- АКТИВНЫЕ ПРЕДМЕТЫ (с кнопкой и перезарядкой) ---
    "item_1": {"name": "🧪 Зелье Огня", "type": "active", "cd": 2, "desc": "Наносит 40 урона врагу."},
    "item_2": {"name": "💖 Эликсир Жизни", "type": "active", "cd": 3, "desc": "Восстанавливает 50 HP."},
    "item_3": {"name": "🔋 Сфера Энергии", "type": "active", "cd": 3, "desc": "Восстанавливает +40 к ресурсам/мане."},
    "item_4": {"name": "🛡️ Амулет Защиты", "type": "active", "cd": 4, "desc": "Блокирует следующий урон."},
    "item_5": {"name": "⚡ Молния в Банке", "type": "active", "cd": 4, "desc": "Наносит 70 урона врагу."},
    "item_6": {"name": "🌀 Песочные Часы", "type": "active", "cd": 4, "desc": "Замораживает врага на 1 ход."},
    "item_7": {"name": "💣 Взрывная Бомба", "type": "active", "cd": 3, "desc": "50 урона врагу и -15 HP вам."},

    # --- ПАССИВНЫЕ ПРЕДМЕТЫ (авто-ап характеристик без кнопок) ---
    "item_8": {"name": "⚔️ Меч Рубителя", "type": "passive", "bonus_dmg": 10, "desc": "+10 к урону всех навыков."},
    "item_9": {"name": "🩸 Кольцо Бессмертия", "type": "passive", "bonus_hp": 40, "desc": "+40 к максимальному HP."},
    "item_10": {"name": "🔮 Гримуар Магии", "type": "passive", "bonus_res": 30, "desc": "+30 к максимальному запасу Ресурсов/Маны."},
    "item_11": {"name": "🛡️ Тяжёлый Нагрудник", "type": "passive", "bonus_hp": 60, "desc": "+60 к максимальному HP."},
    "item_12": {"name": "🗡️ Точильный Камень", "type": "passive", "bonus_dmg": 15, "desc": "+15 к урону всех навыков."},
    "item_13": {"name": "👑 Корона Владыки", "type": "passive", "bonus_all": True, "desc": "+25 HP, +20 Ресурсов и +8 Урона."}
}

MONSTERS = [
    {"name": "Лесной Слайм 🟢", "hp": 40, "max_hp": 40, "dmg": (5, 10), "image": "https://raw.githubusercontent.com/Tencent/Inference-engine/master/docs/images/slime.png"},
    {"name": "Пещерный Гоблин 👺", "hp": 60, "max_hp": 60, "dmg": (8, 14), "image": "https://img.freepik.com/free-vector/goblin-character-concept_23-2148492025.jpg"},
    {"name": "Скелет-Воин 💀", "hp": 80, "max_hp": 80, "dmg": (12, 18), "image": "https://img.freepik.com/free-vector/skeleton-warrior-character_23-2148486028.jpg"},
    {"name": "Дикий Огр 👹", "hp": 100, "max_hp": 100, "dmg": (15, 22), "image": "https://img.freepik.com/free-vector/demon-monster-character-concept_23-2148488050.jpg"}
]

BOSS = {
    "name": "🔥 ДЕМОНИЧЕСКИЙ БОСС ☠️", "hp": 220, "max_hp": 220, "dmg": (22, 35),
    "image": "https://img.freepik.com/free-vector/demon-monster-character-concept_23-2148488050.jpg"
}

CLASSES = {
    "warrior": {"name": "Воин ⚔️", "hp": 130, "max_hp": 130, "res_name": "Ярость", "max_res": 100, "skills": {"slash": {"name": "⚔️ Рубящий (10 Яр)", "cost": 10, "dmg": (22, 30)}, "shout": {"name": "📣 Клич (+25 Яр)", "cost": 0, "heal": 15, "gain": 25}, "execute": {"name": "🩸 Казнь (50 Яр)", "cost": 50, "dmg": (50, 70)}}},
    "tank": {"name": "Танк 🛡️", "hp": 170, "max_hp": 170, "res_name": "Стойкость", "max_res": 50, "skills": {"bash": {"name": "🛡️ Удар щитом (5 Ст)", "cost": 5, "dmg": (14, 20)}, "block": {"name": "🧱 Блок (15 Ст)", "cost": 15, "block_next": True, "heal": 20}, "taunt": {"name": "📣 Провокация (10 Ст)", "cost": 10, "dmg": (10, 16)}}},
    "mage": {"name": "Маг 🔮", "hp": 90, "max_hp": 90, "res_name": "Мана", "max_res": 100, "skills": {"fireball": {"name": "🔥 Фаербол (20 Ман)", "cost": 20, "dmg": (35, 48)}, "mana_shield": {"name": "🛡️ Щит (+35 Ман)", "cost": 0, "heal_mana": 35}, "blink": {"name": "✨ Телепорт (10 Ман)", "cost": 10, "dmg": (18, 28)}}},
    "archer": {"name": "Стрелок 🏹", "hp": 100, "max_hp": 100, "res_name": "Фокус", "max_res": 30, "skills": {"shot": {"name": "🏹 Выстрел (5 Фок)", "cost": 5, "dmg": (20, 26)}, "aim": {"name": "🎯 Прицел", "cost": 0, "prep_move": True}, "powershot": {"name": "💥 Мощный выстрел (15 Фок)", "cost": 15, "dmg": (55, 80), "needs_prep": True}}},
    "femboy": {"name": "Фембой ✨", "hp": 85, "max_hp": 85, "res_name": "Обаяние", "max_res": 50, "skills": {"wink": {"name": "😉 Подмигивание (5 Об)", "cost": 5, "dmg_random": (10, 50)}, "hug": {"name": "🫂 Обнимашки", "cost": 0, "heal": 25}, "distract": {"name": "👗 Отвлечение (20 Об)", "cost": 20, "enemy_skip_turn": True}}}
}

def generate_hud(player: dict):
    cls_data = CLASSES[player["class_key"]]
    text = f"🚪 **Комната №{player['room']}** | 🏆 Убито: {player['kills']}\n"
    text += f"👤 **Герой:** {cls_data['name']}\n"
    
    if player["class_key"] == "mage":
        text += f"❤️ HP: {player['hp']}/{player['max_hp']} (+🔮 Щит: {player['res']})\n"
    else:
        text += f"❤️ HP: {player['hp']}/{player['max_hp']}\n"
        
    text += f"⚡ {cls_data['res_name']}: {player['res']}/{cls_data['max_res']}\n"
    if player["bonus_dmg"] > 0:
        text += f"⚔️ Бонус урона: +{player['bonus_dmg']}\n"
    text += "───────────────\n"
    
    if player["enemy"]:
        e = player["enemy"]
        is_boss = " (БОСС)" if e.get("is_boss") else ""
        text += f"👹 **Враг:** {e['name']}{is_boss}\n❤️ HP Врага: {e['hp']}/{e['max_hp']}\n"
        text += "───────────────\n"
        
    if player["last_log"]:
        text += f"💬 *{player['last_log']}*\n"
        
    return text

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await show_main_menu(message)

async def show_main_menu(message_or_cb):
    text = "🏰 **ГЛАВНОЕ МЕНЮ РПГ ИГРЫ**\n\nВыберите класс героя:"
    builder = InlineKeyboardBuilder()
    for key, data in CLASSES.items():
        builder.button(text=f"✅ {data['name']}", callback_data=f"select_{key}")
    builder.adjust(1)
    
    msg = message_or_cb if isinstance(message_or_cb, types.Message) else message_or_cb.message
    try: await msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception: await msg.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("select_"))
async def select_class(callback: types.CallbackQuery):
    await callback.answer()
    cls_key = callback.data.split("_")[1]
    cls_data = CLASSES[cls_key]
    
    text = f"👤 **КЛАСС: {cls_data['name']}**\n\n❤️ HP: {cls_data['hp']}\n⚡ {cls_data['res_name']}: {cls_data['max_res']}/{cls_data['max_res']} (МАКСИМУМ)\n\nНачать забег?"
    builder = InlineKeyboardBuilder()
    builder.button(text="⚔️ Начать забег", callback_data=f"startwith_{cls_key}")
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.answer()
    await show_main_menu(callback)

@dp.callback_query(F.data.startswith("startwith_"))
async def start_game(callback: types.CallbackQuery):
    await callback.answer()
    cls_key = callback.data.split("_")[1]
    cls_data = CLASSES[cls_key]
    user_id = callback.from_user.id
    
    m_data = random.choice(MONSTERS).copy()
    players[user_id] = {
        "class_key": cls_key,
        "hp": cls_data["hp"], "max_hp": cls_data["hp"],
        "res": cls_data["max_res"], "max_res": cls_data["max_res"],
        "bonus_dmg": 0,
        "room": 1, "kills": 0,
        "inventory": [],  
        "item_cooldowns": {},  
        "last_log": "Вы вошли в подземелье!",
        "enemy": m_data,
        "tank_blocking": False, "prepared_move": False
    }
    
    await render_room(callback, send_photo=True)

async def render_room(callback: types.CallbackQuery, send_photo: bool = False):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player: return

    text = generate_hud(player)
    builder = InlineKeyboardBuilder()
    
    if player["enemy"]:
        cls_data = CLASSES[player["class_key"]]
        
        # 1. Навыки
        if not player["prepared_move"]:
            for sk_id, sk in cls_data["skills"].items():
                if sk.get("needs_prep"): continue
                builder.button(text=sk['name'], callback_data=f"use_{sk_id}")
        else:
            builder.button(text=cls_data["skills"]["powershot"]["name"], callback_data="use_powershot")

        # 2. Только АКТИВНЫЕ предметы показываются на кнопках
        for item_id in player["inventory"]:
            item_info = ITEMS[item_id]
            if item_info["type"] == "active":
                cd = player["item_cooldowns"].get(item_id, 0)
                if cd == 0:
                    builder.button(text=f"🎒 (Предмет) {item_info['name']}", callback_data=f"item_{item_id}")
                else:
                    builder.button(text=f"⏳ (Предмет) {item_info['name']} ({cd} х.)", callback_data=f"itemcd_{item_id}")

        # 3. Кнопка пропуска хода с восстановлением маны
        res_label = "Маны" if player["class_key"] == "mage" else cls_data["res_name"]
        builder.button(text=f"⏳ Пропустить ход (+15 {res_label})", callback_data="skip_turn")
        builder.button(text="⏸️ В меню", callback_data="back_to_menu")
    else:
        builder.button(text="🚪 В следующую комнату", callback_data="next_room")
        builder.button(text="⏸️ В меню", callback_data="back_to_menu")
        
    builder.adjust(1)

    if send_photo and player["enemy"]:
        try: await callback.message.delete()
        except Exception: pass
        await callback.message.answer_photo(photo=player["enemy"]["image"], caption=text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        try: await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
            try: await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
            except Exception: await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "next_room")
async def next_room(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player: return
    
    player["room"] += 1
    
    for k in list(player["item_cooldowns"].keys()):
        if player["item_cooldowns"][k] > 0: player["item_cooldowns"][k] -= 1
            
    if player["kills"] > 0 and player["kills"] % 5 == 0:
        boss_data = BOSS.copy()
        boss_data["is_boss"] = True
        player["enemy"] = boss_data
        player["last_log"] = f"⚠️ ВНИМАНИЕ! Появился МОЩНЫЙ БОСС!"
    else:
        m_data = random.choice(MONSTERS).copy()
        player["enemy"] = m_data
        player["last_log"] = f"🚪 Вы вошли в комнату {player['room']}!"
        
    await render_room(callback, send_photo=True)

# ИСПОЛЬЗОВАНИЕ АКТИВНОГО ПРЕДМЕТА
@dp.callback_query(F.data.startswith("item_"))
async def use_item(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player or not player["enemy"]: return
    
    item_id = callback.data.split("_")[1] + "_" + callback.data.split("_")[2]
    item = ITEMS[item_id]
    enemy = player["enemy"]
    cls_data = CLASSES[player["class_key"]]
    
    await callback.answer(f"Использовано: {item['name']}")
    player["item_cooldowns"][item_id] = item["cd"]
    log = [f"🎒 Активирован предмет {item['name']}!"]
    
    if item_id == "item_1": enemy["hp"] -= 40; log.append("💥 Нанесено 40 урона!")
    elif item_id == "item_2": player["hp"] = min(player["max_hp"], player["hp"] + 50); log.append("💖 +50 HP!")
    elif item_id == "item_3": player["res"] = min(player["max_res"], player["res"] + 40); log.append(f"🔋 +40 к {cls_data['res_name']}!")
    elif item_id == "item_4": player["tank_blocking"] = True; log.append("🛡️ Полный блок атак!")
    elif item_id == "item_5": enemy["hp"] -= 70; log.append("⚡ Молния ударила на 70 урона!")
    elif item_id == "item_6": player["enemy_skipped"] = True; log.append("🌀 Враг заморожен!")
    elif item_id == "item_7": enemy["hp"] -= 50; player["hp"] -= 15; log.append("💣 Взрыв: 50 урона (-15 HP вам)!")

    if enemy["hp"] <= 0:
        await handle_enemy_death(callback, player, enemy)
        return

    player["last_log"] = "\n".join(log)
    await render_room(callback)

@dp.callback_query(F.data.startswith("itemcd_"))
async def item_on_cd(callback: types.CallbackQuery):
    await callback.answer("⏳ Предмет еще перезаряжается!", show_alert=True)

# ПОБЕДА И ВЫПАДЕНИЕ ПРЕДМЕТОВ (ВКЛЮЧАЯ ПАССИВКИ)
async def handle_enemy_death(callback, player, enemy):
    player["kills"] += 1
    player["enemy"] = None
    
    if enemy.get("is_boss"):
        available_items = [k for k in ITEMS.keys() if k not in player["inventory"]]
        if available_items:
            new_item_id = random.choice(available_items)
            item = ITEMS[new_item_id]
            player["inventory"].append(new_item_id)
            
            # Если выпала ПАССИВКА — сразу применяем бафф
            if item["type"] == "passive":
                if "bonus_hp" in item:
                    player["max_hp"] += item["bonus_hp"]
                    player["hp"] += item["bonus_hp"]
                if "bonus_res" in item:
                    player["max_res"] += item["bonus_res"]
                    player["res"] += item["bonus_res"]
                if "bonus_dmg" in item:
                    player["bonus_dmg"] += item["bonus_dmg"]
                if item.get("bonus_all"):
                    player["max_hp"] += 25; player["hp"] += 25
                    player["max_res"] += 20; player["res"] += 20
                    player["bonus_dmg"] += 8
                    
                player["last_log"] = f"🎉 БОСС ПОВЕРЖЕН!\n✨ Получена ПАССИВКА: {item['name']}\n📜 ({item['desc']})"
            else:
                player["last_log"] = f"🎉 БОСС ПОВЕРЖЕН!\n🎒 Получен АКТИВНЫЙ предмет: {item['name']}!"
        else:
            player["last_log"] = "🎉 БОСС ПОВЕРЖЕН! (Собрана вся коллекция артефактов)"
    else:
        player["last_log"] = f"🎉 Враг {enemy['name']} повержен!"
        
    await render_room(callback)

# ПРОПУСК ХОДА
@dp.callback_query(F.data == "skip_turn")
async def process_skip_turn(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player or not player["enemy"]: return
    
    for k in list(player["item_cooldowns"].keys()):
        if player["item_cooldowns"][k] > 0: player["item_cooldowns"][k] -= 1

    cls_data = CLASSES[player["class_key"]]
    res_label = "Маны" if player["class_key"] == "mage" else cls_data["res_name"]
    
    player["res"] = min(player["max_res"], player["res"] + 15)
    log = [f"⏳ Вы пропустили ход и восстановили +15 {res_label}."]
    enemy = player["enemy"]

    if not player["tank_blocking"] and not player.get("enemy_skipped"):
        enemy_dmg = random.randint(enemy["dmg"][0], enemy["dmg"][1])
        player["hp"] -= enemy_dmg
        log.append(f"💥 Враг ударил на {enemy_dmg} урона.")
    else:
        log.append("🧱 Удар заблокирован или пропущен!")
        player["tank_blocking"] = False
        player["enemy_skipped"] = False

    if player["hp"] <= 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 В меню", callback_data="back_to_menu")
        await callback.message.answer("☠️ **ВЫ ПОГИБЛИ В БОЮ...**", reply_markup=builder.as_markup(), parse_mode="Markdown")
        del players[user_id]
        return

    player["last_log"] = "\n".join(log)
    await render_room(callback)

# ИСПОЛЬЗОВАНИЕ НАВЫКОВ
@dp.callback_query(F.data.startswith("use_"))
async def use_skill(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player or not player["enemy"]: 
        await callback.answer()
        return
        
    skill_id = callback.data.split("_")[1]
    cls_data = CLASSES[player["class_key"]]
    skill = cls_data["skills"][skill_id]
    
    if player["res"] < skill["cost"]:
        await callback.answer(f"Не хватает ресурсов!", show_alert=True)
        return
        
    await callback.answer()
    player["res"] -= skill["cost"]
    
    for k in list(player["item_cooldowns"].keys()):
        if player["item_cooldowns"][k] > 0: player["item_cooldowns"][k] -= 1

    enemy = player["enemy"]
    log = []
    
    damage = random.randint(*skill["dmg"]) if "dmg" in skill else 0
    if "dmg_random" in skill: damage = random.randint(*skill["dmg_random"])
    
    # ПРИМЕНЕНИЕ ПАССИВНОГО БОНУСА К УРОНУ
    if damage > 0:
        damage += player["bonus_dmg"]
        enemy["hp"] -= damage
        log.append(f"⚔️ {skill['name']}: нанесён урон {damage}.")
        if "gain" in skill: player["res"] = min(player["max_res"], player["res"] + skill["gain"])

    if "heal" in skill:
        player["hp"] = min(player["max_hp"], player["hp"] + skill["heal"])
        log.append(f"🩸 Лечение +{skill['heal']} HP.")

    if enemy["hp"] <= 0:
        await handle_enemy_death(callback, player, enemy)
        return

    if not player["tank_blocking"] and not skill.get("enemy_skip_turn"):
        enemy_dmg = random.randint(*enemy["dmg"])
        player["hp"] -= enemy_dmg
        log.append(f"💥 Враг ответил: -{enemy_dmg} HP.")
    else:
        log.append("🧱 Удар заблокирован!")
        player["tank_blocking"] = False

    if player["hp"] <= 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Главное меню", callback_data="back_to_menu")
        await callback.message.answer("☠️ **ВЫ ПОГИБЛИ В БОЮ...**", reply_markup=builder.as_markup(), parse_mode="Markdown")
        del players[user_id]
        return

    player["last_log"] = "\n".join(log)
    await render_room(callback)

# Фейковый веб-сервер Render
async def handle_ping(request): return web.Response(text="Bot is running!")
async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    print("Бот RPG запущен!")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
