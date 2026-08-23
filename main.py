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

# База активных сессий игроков
players = {}

# === КОНФИГУРАЦИЯ ЛОКАЦИЙ ===
LOCATIONS = {
    "forest": {"name": "🌲 Заколдованный Лес", "difficulty": 1},
    "cave": {"name": "🦇 Тёмная Пещера", "difficulty": 2},
    "dungeon": {"name": "🏰 Забытое Подземелье", "difficulty": 3},
    "castle": {"name": "🔥 Замок Владыки", "difficulty": 4}
}

# === КОНФИГУРАЦИЯ КЛАССОВ (ВСЕ ОТКРЫТЫ) ===
CLASSES = {
    "warrior": {
        "name": "Воин ⚔️", 
        "hp": 120, "max_hp": 120, 
        "res_name": "Ярость", "res": 0, "max_res": 100,
        "desc": "Механика: НАКОПЛЕНИЕ. Накапливает Ярость в бою для мощных ударов.",
        "skills": {
            "slash": {"name": "⚔️ Рубящий удар (10 Ярости)", "cost": 10, "dmg": (20, 28), "gain": 5},
            "shout": {"name": "📣 Боевой клич (+25 Ярости)", "cost": 0, "heal": 15, "gain": 25},
            "execute": {"name": "🩸 Казнь (50 Ярости)", "cost": 50, "dmg": (40, 60), "gain": 0}
        }
    },
    "tank": {
        "name": "Танк 🛡️", 
        "hp": 160, "max_hp": 160, 
        "res_name": "Стойкость", "res": 50, "max_res": 50,
        "desc": "Механика: БЛОК. Высокий запас HP и возможность глухой обороны.",
        "skills": {
            "bash": {"name": "🛡️ Удар щитом (5 Стойкости)", "cost": 5, "dmg": (12, 18)},
            "block": {"name": "🧱 Глухая оборона (Блок атк.)", "cost": 15, "block_next": True, "heal": 20},
            "taunt": {"name": "📣 Провокация (10 Стойкости)", "cost": 10, "dmg": (8, 14)}
        }
    },
    "mage": {
        "name": "Маг 🔮", 
        "hp": 80, "max_hp": 80, 
        "res_name": "Мана", "res": 100, "max_res": 100,
        "desc": "Механика: МАГИЧЕСКИЙ ЩИТ. Урон сначала вычитается из Маны, а затем из HP.",
        "skills": {
            "fireball": {"name": "🔥 Фаербол (20 Маны)", "cost": 20, "dmg": (30, 42)},
            "mana_shield": {"name": "🛡️ Восст. Щита (+35 Маны)", "cost": 0, "heal_mana": 35},
            "blink": {"name": "✨ Телепорт (10 Маны)", "cost": 10, "dmg": (15, 25)}
        }
    },
    "archer": {
        "name": "Стрелок 🏹", 
        "hp": 90, "max_hp": 90, 
        "res_name": "Фокус", "res": 30, "max_res": 30,
        "desc": "Механика: ПРИЦЕЛИВАНИЕ. Подготавливает мощный выстрел огромного урона.",
        "skills": {
            "shot": {"name": "🏹 Быстрый выстрел (5 Фокуса)", "cost": 5, "dmg": (18, 24)},
            "aim": {"name": "🎯 Прицеливание (Готовит удар)", "cost": 0, "prep_move": True},
            "powershot": {"name": "💥 Мощный выстрел (15 Фокуса)", "cost": 15, "dmg": (45, 65), "needs_prep": True}
        }
    },
    "femboy": {
        "name": "Фембой ✨", 
        "hp": 75, "max_hp": 75, 
        "res_name": "Обаяние", "res": 50, "max_res": 50,
        "desc": "Механика: ХАРИЗМА. Непредсказуемый урон и возможность заставить врага пропустить ход.",
        "skills": {
            "wink": {"name": "😉 Подмигивание (5 Обаяния)", "cost": 5, "dmg_random": (8, 48)},
            "hug": {"name": "🫂 Обнимашки (Лечит обоих)", "cost": 0, "heal": 25, "heal_enemy": 10},
            "distract": {"name": "👗 Отвлечение (Враг пропустит ход)", "cost": 20, "enemy_skip_turn": True}
        }
    }
}

MONSTERS = [
    {"name": "Лесной Слайм 🟢", "hp": 30, "max_hp": 30, "dmg": (4, 8)},
    {"name": "Гоблин-Застрельщик 👺", "hp": 40, "max_hp": 40, "dmg": (7, 12)},
    {"name": "Пещерный Паук 🕷️", "hp": 55, "max_hp": 55, "dmg": (10, 16)},
    {"name": "Скелет-Воин 💀", "hp": 70, "max_hp": 70, "dmg": (12, 20)},
    {"name": "Огр-Разрушитель 👹", "hp": 110, "max_hp": 110, "dmg": (15, 25)}
]

# === ТЕКСТОВЫЙ ИНТЕРФЕЙС HUD ===
def generate_hud(player: dict):
    cls_data = CLASSES[player["class_key"]]
    loc_data = LOCATIONS[player["location"]]
    
    text = f"📍 **Локация:** {loc_data['name']} (Комната {player['room_num']})\n"
    text += f"👤 **Герой:** {cls_data['name']} | 🏆 Убито: {player['kills']}\n"
    
    if player["class_key"] == "mage":
        text += f"❤️ HP: {player['hp']}/{player['max_hp']} (+🔮 Щит: {player['res']})\n"
    else:
        text += f"❤️ HP: {player['hp']}/{player['max_hp']}\n"
        
    text += f"⚡ {cls_data['res_name']}: {player['res']}/{cls_data['max_res']}\n"
    text += "───────────────\n"
    
    if player["enemy"]:
        e = player["enemy"]
        text += f"👹 **Враг:** {e['name']}\n❤️ HP Врага: {e['hp']}/{e['max_hp']}\n"
        text += "───────────────\n"
        
    if player["last_log"]:
        text += f"💬 *{player['last_log']}*\n"
        
    return text

# === ХЕНДЛЕРЫ МЕНЮ И СТАРТА ===
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await show_main_menu(message)

async def show_main_menu(message_or_cb):
    text = "🏰 **ГЛАВНОЕ МЕНЮ РПГ ИГРЫ**\n\nВсе классы разблокированы! Выберите своего героя:"
    builder = InlineKeyboardBuilder()
    
    for key, data in CLASSES.items():
        builder.button(text=f"✅ {data['name']}", callback_data=f"select_{key}")
    builder.adjust(1)
    
    msg = message_or_cb if isinstance(message_or_cb, types.Message) else message_or_cb.message
    try:
        await msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception:
        await msg.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("select_"))
async def select_class(callback: types.CallbackQuery):
    cls_key = callback.data.split("_")[1]
    cls_data = CLASSES[cls_key]
    
    text = f"👤 **КЛАСС: {cls_data['name']}**\n\n"
    text += f"📜 {cls_data['desc']}\n\n"
    text += f"❤️ Старт HP: {cls_data['hp']}\n"
    text += f"⚡ {cls_data['res_name']}: {cls_data['res']}\n\n"
    text += "Начать забег с этого героя?"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⚔️ Начать путешествие", callback_data=f"startwith_{cls_key}")
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await show_main_menu(callback)

@dp.callback_query(F.data.startswith("startwith_"))
async def start_game(callback: types.CallbackQuery):
    cls_key = callback.data.split("_")[1]
    cls_data = CLASSES[cls_key]
    user_id = callback.from_user.id
    
    players[user_id] = {
        "class_key": cls_key,
        "hp": cls_data["hp"], "max_hp": cls_data["max_hp"],
        "res": cls_data["res"], "max_res": cls_data["max_res"],
        "kills": 0,
        "room_num": 1,
        "location": "forest",
        "last_log": "Вы вступили на тропу приключений.",
        "enemy": None,
        "tank_blocking": False,
        "prepared_move": False
    }
    
    await render_room(callback)

# === ЛОГИКА ПЕРЕМЕЩЕНИЯ ПО КОМНАТАМ ===
async def render_room(message_or_cb):
    user_id = message_or_cb.from_user.id
    player = players[user_id]
    
    text = generate_hud(player)
    builder = InlineKeyboardBuilder()
    
    if player["enemy"]:
        cls_data = CLASSES[player["class_key"]]
        if not player["prepared_move"]:
            for sk_id, sk in cls_data["skills"].items():
                if sk.get("needs_prep"): continue
                builder.button(text=sk['name'], callback_data=f"use_{sk_id}")
        else:
            builder.button(text=cls_data["skills"]["powershot"]["name"], callback_data="use_powershot")

        builder.button(text="⏳ Пропустить ход (+15 Маны)", callback_data="skip_turn")
        builder.button(text="⏸️ Пауза / Меню", callback_data="back_to_menu")
    else:
        builder.button(text="🚪 Идти в следующую комнату", callback_data="next_room")
        builder.button(text="🗺️ Сменить локацию", callback_data="change_loc")
        builder.button(text="⏸️ Пауза / Меню", callback_data="back_to_menu")
        
    builder.adjust(1)
    msg = message_or_cb if isinstance(message_or_cb, types.Message) else message_or_cb.message
    try:
        await msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception:
        await msg.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "next_room")
async def next_room(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player: return
    
    player["room_num"] += 1
    event = random.choice(["monster", "monster", "chest", "heal"])
    
    if event == "monster":
        m_data = random.choice(MONSTERS).copy()
        player["enemy"] = m_data
        player["last_log"] = f"🚪 Вы вошли в комнату {player['room_num']} и встретили: {m_data['name']}!"
    elif event == "chest":
        res_add = 20
        player["res"] = min(player["max_res"], player["res"] + res_add)
        player["last_log"] = f"📦 Вы нашли сундук! Восстановлено +{res_add} к ресурсам."
    else:
        heal_add = 25
        player["hp"] = min(player["max_hp"], player["hp"] + heal_add)
        player["last_log"] = f"💖 Вы нашли целебный родник! Восстановлено +{heal_add} HP."
        
    await render_room(callback)

@dp.callback_query(F.data == "change_loc")
async def change_location_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    for loc_key, loc_data in LOCATIONS.items():
        builder.button(text=loc_data["name"], callback_data=f"setloc_{loc_key}")
    builder.button(text="⬅️ Назад", callback_data="render_current_room")
    builder.adjust(1)
    
    await callback.message.edit_text("🗺️ **ВЫБЕРИТЕ ЛОКАЦИЮ ДЛЯ ПЕРЕХОДА:**", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("setloc_"))
async def set_location(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player: return
    
    loc_key = callback.data.split("_")[1]
    player["location"] = loc_key
    player["room_num"] = 1
    player["last_log"] = f"🗺️ Вы перешли в локацию {LOCATIONS[loc_key]['name']}."
    await render_room(callback)

@dp.callback_query(F.data == "render_current_room")
async def render_current_room(callback: types.CallbackQuery):
    await render_room(callback)

# === КНОПКА «ПРОПУСТИТЬ ХОД» (+15 МАНЫ) ===
@dp.callback_query(F.data == "skip_turn")
async def process_skip_turn(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player or not player["enemy"]: return
    
    enemy = player["enemy"]
    cls_data = CLASSES[player["class_key"]]
    
    mana_gain = 15
    player["res"] = min(player["max_res"], player["res"] + mana_gain)
    log = [f"⏳ Вы пропустили ход и восстановили +{mana_gain} {cls_data['res_name']}."]

    if not player["tank_blocking"]:
        enemy_dmg = random.randint(enemy["dmg"][0], enemy["dmg"][1])
        if player["class_key"] == "mage":
            mana_dmg = min(player["res"], enemy_dmg)
            player["res"] -= mana_dmg
            actual_dmg = enemy_dmg - mana_dmg
            player["hp"] -= actual_dmg
            log.append(f"💥 Враг атаковал: -{mana_dmg} Маны и -{actual_dmg} HP.")
        else:
            player["hp"] -= enemy_dmg
            log.append(f"💥 Враг воспользовался моментом и ударил на {enemy_dmg} урона.")
    else:
        log.append("🧱 Удар врага был заблокирован!")
        player["tank_blocking"] = False

    if player["hp"] <= 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 В меню", callback_data="back_to_menu")
        await callback.message.edit_text("☠️ **ВЫ ПОГИБЛИ...**\nПопробуйте начать заново.", reply_markup=builder.as_markup(), parse_mode="Markdown")
        del players[user_id]
        return

    player["last_log"] = "\n".join(log)
    await render_room(callback)

# === ОБРАБОТКА НАВЫКОВ ===
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
    
    skip_enemy_turn = skill.get("enemy_skip_turn", False)
    
    if player["res"] < skill["cost"]:
        await callback.answer(f"Не хватает {cls_data['res_name']}!", show_alert=True)
        return
    player["res"] -= skill["cost"]
    
    damage = 0
    if "dmg" in skill: damage = random.randint(*skill["dmg"])
    if "dmg_random" in skill: damage = random.randint(*skill["dmg_random"])
    
    if skill_id == "powershot": player["prepared_move"] = False
    
    if damage > 0:
        enemy["hp"] -= damage
        log.append(f"⚔️ {skill['name']}: нанесён урон {damage}.")
        if "gain" in skill: player["res"] = min(player["max_res"], player["res"] + skill["gain"])

    if "heal" in skill:
        player["hp"] = min(player["max_hp"], player["hp"] + skill["heal"])
        log.append(f"🩸 Исцеление +{skill['heal']} HP.")
        if "heal_enemy" in skill: enemy["hp"] = min(enemy["max_hp"], enemy["hp"] + skill["heal_enemy"])

    if "block_next" in skill:
        player["tank_blocking"] = True
        log.append("🧱 Вы встали в блок!")

    if "heal_mana" in skill:
        player["res"] = min(cls_data["max_res"], player["res"] + skill["heal_mana"])
        log.append(f"🔮 Мана восстановлена (+{skill['heal_mana']}).")

    if "prep_move" in skill:
        player["prepared_move"] = True
        log.append("🎯 Вы начали прицеливание!")

    if enemy["hp"] <= 0:
        player["kills"] += 1
        player["enemy"] = None
        player["last_log"] = f"🎉 Враг {enemy['name']} повержен!"
        await render_room(callback)
        return

    if not player["tank_blocking"] and not skip_enemy_turn:
        enemy_dmg = random.randint(*enemy["dmg"])
        if player["class_key"] == "mage":
            mana_dmg = min(player["res"], enemy_dmg)
            player["res"] -= mana_dmg
            actual_dmg = enemy_dmg - mana_dmg
            player["hp"] -= actual_dmg
            log.append(f"💥 Враг нанес урон: -{mana_dmg} Маны и -{actual_dmg} HP.")
        else:
            player["hp"] -= enemy_dmg
            log.append(f"💥 Враг нанёс {enemy_dmg} урона.")
    elif player["tank_blocking"]:
        log.append("🧱 Удар врага успешно заблокирован!")
        player["tank_blocking"] = False

    if player["hp"] <= 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Главное меню", callback_data="back_to_menu")
        await callback.message.edit_text("☠️ **ВЫ ПОГИБЛИ В БОЮ...**", reply_markup=builder.as_markup(), parse_mode="Markdown")
        del players[user_id]
        return

    player["last_log"] = "\n".join(log)
    await render_room(callback)

# Фейковый веб-сервер для удовлетворения требований Render
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# Главный запуск
async def main():
    print("Бот RPG запущен!")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
