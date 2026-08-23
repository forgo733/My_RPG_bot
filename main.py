import asyncio
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === ТОКЕН БОТА ===
TELEGRAM_TOKEN = "8778603732:AAHGLy3BsklI6302GJUZgZiyBYyy85TutFE"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# База игроков и их разблокированных классов
players = {}
unlocked_classes = {}  # user_id: set("warrior", "tank", ...)

# === КОНФИГУРАЦИЯ КЛАССОВ И МЕХАНИК ===
CLASSES = {
    "warrior": {
        "name": "Воин ⚔️", 
        "hp": 120, "max_hp": 120, 
        "res_name": "Ярость", "res": 100, "max_res": 100,
        "unlocked": True,
        "desc": "Механика: НАКОПЛЕНИЕ. Ярость копится при атаке/получении урона. Тратится на суперудары.",
        "skills": {
            "slash": {"name": "⚔️ Рубящий удар (10 Ярости)", "cost": 10, "dmg": (20, 28), "gain": 5},
            "shout": {"name": "📣 Боевой клич (Без ст., +25 Ярости)", "cost": 0, "heal": 15, "gain": 25},
            "execute": {"name": "🩸 Казнь (Всего 50 Ярости)", "cost": 50, "dmg": (40, 60), "gain": 0}
        }
    },
    "tank": {
        "name": "Танк 🛡️", 
        "hp": 160, "max_hp": 160, 
        "res_name": "Стойкость", "res": 50, "max_res": 50,
        "unlocked": True,
        "desc": "Механика: БЛОК. Может гарантированно заблокировать следующую атаку врага.",
        "skills": {
            "bash": {"name": "🛡️ Удар щитом", "cost": 5, "dmg": (10, 15)},
            "block": {"name": "🧱 Глухая оборона (Блок атк., +Heal)", "cost": 15, "block_next": True, "heal": 20},
            "taunt": {"name": "📣 Провокация (Враг слабее)", "cost": 10, "dmg": (5, 10)}
        }
    },
    "mage": {
        "name": "Маг 🔮", 
        "hp": 80, "max_hp": 80, 
        "res_name": "Мана", "res": 100, "max_res": 100,
        "unlocked": False,
        "unlock_cond": "Победить 10 монстров в одном забеге.",
        "desc": "Механика: МАГИЧЕСКИЙ ЩИТ. Урон сначала тратит Ману, затем HP.",
        "skills": {
            "fireball": {"name": "🔥 Фаербол (15 Маны)", "cost": 15, "dmg": (25, 35)},
            "mana_shield": {"name": "🛡️ Восст. Щита (Без ст.)", "cost": 0, "heal_mana": 30},
            "blink": {"name": "✨ Телепорт (10 Маны)", "cost": 10, "dmg": (15, 20)}
        }
    },
    "archer": {
        "name": "Стрелок 🏹", 
        "hp": 90, "max_hp": 90, 
        "res_name": "Фокус", "res": 30, "max_res": 30,
        "unlocked": False,
        "unlock_cond": "Открыть 5 сундуков с артефактами.",
        "desc": "Механика: ЗАРЯДКА. Сначала готовит выстрел (теряет ход), затем наносит огромный урон.",
        "skills": {
            "shot": {"name": "🏹 Быстрый выстрел", "cost": 5, "dmg": (18, 24)},
            "aim": {"name": "🎯 Прицеливание (Потеря хода)", "cost": 0, "prep_move": True},
            "powershot": {"name": "💥 Мощный выстрел (Тр. Прицел.)", "cost": 15, "dmg": (40, 55), "needs_prep": True}
        }
    },
    "femboy": {
        "name": "Фембой ✨", 
        "hp": 70, "max_hp": 70, 
        "res_name": "Обаяние", "res": 50, "max_res": 50,
        "unlocked": False,
        "unlock_cond": "🔄 Переродиться 3 раза (сбросить игру после победы над Боссом 5).",
        "desc": "Механика: УДАЧА И ХАРИЗМА. Атаки непредсказуемы, отвлекают врагов и лечат.",
        "skills": {
            "wink": {"name": "😉 Подмигивание (Рандом урона)", "cost": 5, "dmg_random": (5, 45)},
            "hug": {"name": "🫂 Обнимашки (Без ст., Исцел.)", "cost": 0, "heal": 25, "heal_enemy": 10},
            "distract": {"name": "👗 Отвлечение (Враг пропустит ход)", "cost": 20, "enemy_skip_turn": True}
        }
    }
}

EASY_MONSTERS = [
    {"id": "spider", "name": "Пещерный Паук", "hp": 25, "max_hp": 25, "dmg": (5, 8)},
    {"id": "goblin", "name": "Гоблин-Застрельщик", "hp": 30, "max_hp": 30, "dmg": (6, 10)}
]

def get_monster_attack():
    return random.randint(7, 12)

def get_user_unlocked_classes(user_id: int):
    if user_id not in unlocked_classes:
        unlocked_classes[user_id] = {"warrior", "tank"}
    return unlocked_classes[user_id]

# --- ГЕНЕРАТОР ТЕКСТОВОГО HUD ---
def generate_battle_text_hud(player: dict):
    enemy = player["enemy"]
    cls_data = CLASSES[player["class_key"]]
    
    text = f"⚔️ **БОЙ С: {enemy['name']}**\n"
    text += f"❤️ Враг: {enemy['hp']}/{enemy['max_hp']} HP\n"
    text += "────────────────────────\n"
    text += f"👤 **Вы: {cls_data['name']}** (Убито: {player['kills']})\n"
    
    if player["class_key"] == "mage":
        text += f"❤️ HP: {player['hp']}/{player['max_hp']} (+🔮 Мана-Щит: {player['res']})\n"
    else:
        text += f"❤️ HP: {player['hp']}/{player['max_hp']}\n"
    
    text += f"⚡ {cls_data['res_name']}: {player['res']}/{cls_data['max_res']}\n"
    
    if player["prepared_move"]:
        text += f"🎯 **ПОДГОТОВЛЕН МОЩНЫЙ ВЫСТРЕЛ!**\n"
        
    text += "────────────────────────\n"
    if player["last_log"]:
        text += f"💬 *{player['last_log']}*\n"
    
    return text

# --- ХЕНДЛЕРЫ КОМАНД ---
@dp.message(CommandStart())
async def start_game(message: types.Message):
    await show_main_menu(message)

async def show_main_menu(message_or_cb):
    user_id = message_or_cb.from_user.id
    unlocked = get_user_unlocked_classes(user_id)
    
    text = "🏰 **ГЛАВНОЕ МЕНЮ РПГ ИГРЫ**\n\nВыберите доступного героя или посмотрите условия разблокировки:"
    
    builder = InlineKeyboardBuilder()
    for key, data in CLASSES.items():
        if key in unlocked:
            builder.button(text=f"✅ {data['name']}", callback_data=f"select_{key}")

    builder.button(text="🔒 Заблокированные персонажи", callback_data="show_locked")
    builder.adjust(1)
    
    msg = message_or_cb if isinstance(message_or_cb, types.Message) else message_or_cb.message
    try:
        await msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception:
        await msg.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "show_locked")
async def show_locked_chars(callback: types.CallbackQuery):
    unlocked = get_user_unlocked_classes(callback.from_user.id)
    
    text = "🔒 **ЗАБЛОКИРОВАННЫЕ ПЕРСОНАЖИ**\n\nВыполните условия, чтобы открыть их:\n\n"
    
    for key, data in CLASSES.items():
        if key not in unlocked:
            text += f"❓ **{data['name']}**\n"
            text += f"📜 {data['desc']}\n"
            text += f"🗝️ **Как открыть:** {data['unlock_cond']}\n\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await show_main_menu(callback)

@dp.callback_query(F.data.startswith("select_"))
async def select_class_confirm(callback: types.CallbackQuery):
    cls_key = callback.data.split("_")[1]
    cls_data = CLASSES[cls_key]
    
    text = f"👤 **ВЫБОР КЛАССА: {cls_data['name']}**\n\n"
    text += f"📜 {cls_data['desc']}\n\n"
    text += f"❤️ Старт HP: {cls_data['hp']}\n"
    text += f"⚡ {cls_data['res_name']}: {cls_data['res']}\n\n"
    text += "Начать игру за этого героя?"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, в путь!", callback_data=f"startwith_{cls_key}")
    builder.button(text="⬅️ Назад к меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("startwith_"))
async def start_game_with_class(callback: types.CallbackQuery):
    cls_key = callback.data.split("_")[1]
    cls_data = CLASSES[cls_key]
    user_id = callback.from_user.id
    
    players[user_id] = {
        "class_key": cls_key,
        "hp": cls_data["hp"], "max_hp": cls_data["max_hp"],
        "res": cls_data["res"], "max_res": cls_data["max_res"],
        "kills": 0,
        "last_log": "Вы вошли в подземелье.",
        "enemy": None,
        "tank_blocking": False,
        "prepared_move": False,
    }
    
    await start_fight(callback)

# --- БОЕВАЯ СИСТЕМА ---
async def start_fight(message_or_cb):
    user_id = message_or_cb.from_user.id
    player = players[user_id]
    
    player["enemy"] = random.choice(EASY_MONSTERS).copy()
    player["last_log"] = f"Вам встретился {player['enemy']['name']}!"
    
    await render_battle(message_or_cb, player)

async def render_battle(message_or_cb, player: dict):
    text = generate_battle_text_hud(player)
    cls_data = CLASSES[player["class_key"]]
    
    builder = InlineKeyboardBuilder()
    
    if not player["prepared_move"]:
        for sk_id, sk in cls_data["skills"].items():
            if sk.get("needs_prep") and not player["prepared_move"]: continue
            if sk.get("prep_move") and player["prepared_move"]: continue
            builder.button(text=sk['name'], callback_data=f"use_{sk_id}")
    else:
        builder.button(text=cls_data["skills"]["powershot"]["name"], callback_data="use_powershot")

    # ДОБАВЛЕНЫ КНОПКИ "ПРОПУСТИТЬ ХОД" И "СДААТЬСЯ"
    builder.button(text="⏳ Пропустить ход", callback_data="skip_turn")
    builder.button(text="💤 Сдаться", callback_data="back_to_menu")
    builder.adjust(1)
    
    msg = message_or_cb if isinstance(message_or_cb, types.Message) else message_or_cb.message
    try:
        await msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception:
        await msg.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# === ОБРАБОТКА НАЖАТИЯ КНОПКИ "ПРОПУСТИТЬ ХОД" ===
@dp.callback_query(F.data == "skip_turn")
async def process_skip_turn(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player or not player["enemy"]: return
    
    enemy = player["enemy"]
    log = ["⏳ Вы пропустили ход."]

    # --- ХОД ВРАГА (Враг бьёт, если не было блока) ---
    if not player["tank_blocking"]:
        enemy_dmg = get_monster_attack()
        
        if player["class_key"] == "mage":
            mana_dmg = min(player["res"], enemy_dmg)
            player["res"] -= mana_dmg
            actual_dmg = enemy_dmg - mana_dmg
            player["hp"] -= actual_dmg
            log.append(f"💥 Враг воспользовался моментом и атаковал: -{mana_dmg} Маны и -{actual_dmg} HP.")
        else:
            player["hp"] -= enemy_dmg
            log.append(f"💥 Враг воспользовался моментом и атаковал на {enemy_dmg} урона.")
            if player["class_key"] == "warrior": 
                player["res"] = min(player["max_res"], player["res"] + (enemy_dmg // 2))

    else:
        log.append("🧱🧱 ВРАГ АТАКОВАЛ, НО УДАР ЗАБЛОКИРОВАН!")
        player["tank_blocking"] = False

    # ПРОВЕРКА ПОРАЖЕНИЯ
    if player["hp"] <= 0:
        player["last_log"] = "☠️ Вы погибли..."
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 В меню", callback_data="back_to_menu")
        await callback.message.edit_text("☠️ **ВЫ ПОГИБЛИ...**\nМонстры оказались сильнее.", reply_markup=builder.as_markup(), parse_mode="Markdown")
        del players[user_id]
        return

    player["last_log"] = "\n".join(log)
    await render_battle(callback, player)

# === ОБРАБОТКА ИСПОЛЬЗОВАНИЯ НАВЫКА ===
@dp.callback_query(F.data.startswith("use_"))
async def use_skill(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player or not player["enemy"]: return
        
    skill_id = callback.data.split("_")[1]
    cls_data = CLASSES[player["class_key"]]
    skill = cls_data["skills"][skill_id]
    enemy = player["enemy"]
    log = []
    
    # Запоминаем, заставляет ли навык врагапропустить ход
    skip_enemy_turn = skill.get("enemy_skip_turn", False)
    
    # ПРОВЕРКА РЕСУРСА
    if player["class_key"] in ["mage", "tank", "femboy"]:
        if player["res"] < skill["cost"]:
            await callback.answer(f"Не хватает {cls_data['res_name']}!", show_alert=True)
            return
        player["res"] -= skill["cost"]
        log.append(f"🌀 Использовано: {skill['name']}.")
    
    # --- ХОД ИГРОКА ---
    damage = 0
    
    if player["class_key"] == "warrior":
        if player["res"] < skill["cost"]:
            await callback.answer("Не хватает Ярости!", show_alert=True)
            return
        player["res"] -= skill["cost"]
        log.append(f"🩸 {skill['name']}! Ярость -{skill['cost']}.")

    if "dmg" in skill:
        damage = random.randint(*skill["dmg"])
    
    if "dmg_random" in skill:
        damage = random.randint(*skill["dmg_random"])
        log.append(f"✨ Рандом сработал на уроне: {damage}!")

    if skill_id == "powershot":
        player["prepared_move"] = False
        
    if damage > 0:
        enemy["hp"] -= damage
        log.append(f"⚔️ Вы нанесли {damage} урона.")
        if player["class_key"] == "warrior":
            if "gain" in skill: player["res"] = min(player["max_res"], player["res"] + skill["gain"])

    if "heal" in skill:
        player["hp"] = min(player["max_hp"], player["hp"] + skill["heal"])
        log.append(f"🩸 Исцеление +{skill['heal']} HP.")
        if "heal_enemy" in skill: 
            enemy["hp"] = min(enemy["max_hp"], enemy["hp"] + skill["heal_enemy"])
            log.append(f"🥺 Но враг тоже исцелился (+{skill['heal_enemy']}).")

    if "block_next" in skill:
        player["tank_blocking"] = True
        log.append("🧱 Вы встали в глухую оборону!")

    if "heal_mana" in skill:
        player["res"] = min(cls_data["max_res"], player["res"] + skill["heal_mana"])
        log.append(f"🔮 Мана восстановлена (+{skill['heal_mana']}). Щит окреп.")

    if "prep_move" in skill:
        player["prepared_move"] = True
        log.append("🎯 Вы начали прицеливаться. Враг ходит.")
        enemy_dmg = get_monster_attack()
        player["hp"] -= enemy_dmg
        log.append(f"💥 {enemy['name']} атаковал на {enemy_dmg} урона, пока вы целились!")
        
        player["last_log"] = "\n".join(log)
        await render_battle(callback, player)
        return

    if skip_enemy_turn:
        log.append("💫 **Враг отвлечён и пропускает свой ход!**")

    # ПРОВЕРКА ПОБЕДЫ
    if enemy["hp"] <= 0:
        player["kills"] += 1
        del player["enemy"]
        player["last_log"] = f"🎉 ПОБЕДА над {enemy['name']}!"
        
        if player["kills"] >= 10:
            unlocked = get_user_unlocked_classes(user_id)
            if "mage" not in unlocked:
                unlocked.add("mage")
                player["last_log"] += "\n🔑 РАЗБЛОКИРОВАН КЛАСС: Маг 🔮!"
        
        await start_fight(callback)
        return

    # --- ХОД ВРАГА ---
    # Враг не ходит, если сработал дебафф/навык пропуск хода или стои́т блок
    if not player["tank_blocking"] and not skip_enemy_turn:
        enemy_dmg = get_monster_attack()
        
        if player["class_key"] == "mage":
            mana_dmg = min(player["res"], enemy_dmg)
            player["res"] -= mana_dmg
            actual_dmg = enemy_dmg - mana_dmg
            player["hp"] -= actual_dmg
            log.append(f"💥 Враг атаковал: -{mana_dmg} Маны (Щит) и -{actual_dmg} HP.")
        else:
            player["hp"] -= enemy_dmg
            log.append(f"💥 Враг атаковал на {enemy_dmg} урона.")
            if player["class_key"] == "warrior": 
                player["res"] = min(player["max_res"], player["res"] + (enemy_dmg // 2))

    elif player["tank_blocking"]:
        log.append("🧱🧱 УДАР ВРАГА ЗАБЛОКИРОВАН!")
        player["tank_blocking"] = False

    # ПРОВЕРКА ПОРАЖЕНИЯ
    if player["hp"] <= 0:
        player["last_log"] = "☠️ Вы погибли..."
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 В меню", callback_data="back_to_menu")
        await callback.message.edit_text("☠️ **ВЫ ПОГИБЛИ...**\nМонстры оказались сильнее.", reply_markup=builder.as_markup(), parse_mode="Markdown")
        del players[user_id]
        return

    # Конец хода
    player["last_log"] = "\n".join(log)
    await render_battle(callback, player)

# Запуск бота
async def main():
    print("Бот РПГ запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
