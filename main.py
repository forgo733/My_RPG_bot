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

# === КОНФИГУРАЦИЯ ЭТАЖЕЙ И МОНСТРОВ ===
FLOORS = {
    1: {
        "name": "🌲 1 Этаж: Заколдованный Лес",
        "monster": {
            "name": "Лесной Слайм 🟢",
            "hp": 45, "max_hp": 45, "dmg": (5, 10),
            "image": "https://raw.githubusercontent.com/Tencent/Inference-engine/master/docs/images/slime.png"  # Картинка слайма
        }
    },
    2: {
        "name": "🦇 2 Этаж: Тёмная Пещера",
        "monster": {
            "name": "Пещерный Гоблин 👺",
            "hp": 75, "max_hp": 75, "dmg": (9, 15),
            "image": "https://img.freepik.com/free-vector/goblin-character-concept_23-2148492025.jpg"
        }
    },
    3: {
        "name": "🏰 3 Этаж: Забытое Подземелье",
        "monster": {
            "name": "Скелет-Рыцарь 💀",
            "hp": 110, "max_hp": 110, "dmg": (14, 22),
            "image": "https://img.freepik.com/free-vector/skeleton-warrior-character_23-2148486028.jpg"
        }
    },
    4: {
        "name": "🔥 4 Этаж: Замок Владыки (Финальный Босс)",
        "monster": {
            "name": "Огненный Демон 👹",
            "hp": 170, "max_hp": 170, "dmg": (20, 30),
            "image": "https://img.freepik.com/free-vector/demon-monster-character-concept_23-2148488050.jpg"
        }
    }
}

# === КОНФИГУРАЦИЯ КЛАССОВ ===
CLASSES = {
    "warrior": {
        "name": "Воин ⚔️", 
        "hp": 120, "max_hp": 120, 
        "res_name": "Ярость", "max_res": 100,
        "desc": "Механика: НАКОПЛЕНИЕ. Мощные рубящие удары за Ярость.",
        "skills": {
            "slash": {"name": "⚔️ Рубящий удар (10 Ярости)", "cost": 10, "dmg": (22, 30), "gain": 5},
            "shout": {"name": "📣 Боевой клич (+25 Ярости)", "cost": 0, "heal": 15, "gain": 25},
            "execute": {"name": "🩸 Казнь (50 Ярости)", "cost": 50, "dmg": (45, 65), "gain": 0}
        }
    },
    "tank": {
        "name": "Танк 🛡️", 
        "hp": 160, "max_hp": 160, 
        "res_name": "Стойкость", "max_res": 50,
        "desc": "Механика: БЛОК. Огромное HP и непробиваемый блок.",
        "skills": {
            "bash": {"name": "🛡️ Удар щитом (5 Стойкости)", "cost": 5, "dmg": (14, 20)},
            "block": {"name": "🧱 Глухая оборона (Блок атк.)", "cost": 15, "block_next": True, "heal": 20},
            "taunt": {"name": "📣 Провокация (10 Стойкости)", "cost": 10, "dmg": (10, 16)}
        }
    },
    "mage": {
        "name": "Маг 🔮", 
        "hp": 85, "max_hp": 85, 
        "res_name": "Мана", "max_res": 100,
        "desc": "Механика: МАГИЧЕСКИЙ ЩИТ. Урон сначала вычитается из Маны.",
        "skills": {
            "fireball": {"name": "🔥 Фаербол (20 Маны)", "cost": 20, "dmg": (32, 45)},
            "mana_shield": {"name": "🛡️ Восст. Щита (+35 Маны)", "cost": 0, "heal_mana": 35},
            "blink": {"name": "✨ Телепорт (10 Маны)", "cost": 10, "dmg": (18, 28)}
        }
    },
    "archer": {
        "name": "Стрелок 🏹", 
        "hp": 95, "max_hp": 95, 
        "res_name": "Фокус", "max_res": 30,
        "desc": "Механика: ПРИЦЕЛИВАНИЕ. Подготовка критического выстрела.",
        "skills": {
            "shot": {"name": "🏹 Быстрый выстрел (5 Фокуса)", "cost": 5, "dmg": (20, 26)},
            "aim": {"name": "🎯 Прицеливание (Готовит удар)", "cost": 0, "prep_move": True},
            "powershot": {"name": "💥 Мощный выстрел (15 Фокуса)", "cost": 15, "dmg": (50, 75), "needs_prep": True}
        }
    },
    "femboy": {
        "name": "Фембой ✨", 
        "hp": 80, "max_hp": 80, 
        "res_name": "Обаяние", "max_res": 50,
        "desc": "Механика: ХАРИЗМА. Пропуск хода врага и случайный урон.",
        "skills": {
            "wink": {"name": "😉 Подмигивание (5 Обаяния)", "cost": 5, "dmg_random": (10, 50)},
            "hug": {"name": "🫂 Обнимашки (Лечит обоих)", "cost": 0, "heal": 25, "heal_enemy": 10},
            "distract": {"name": "👗 Отвлечение (Враг пропустит ход)", "cost": 20, "enemy_skip_turn": True}
        }
    }
}

# === ТЕКСТОВЫЙ ИНТЕРФЕЙС ===
def generate_hud(player: dict):
    cls_data = CLASSES[player["class_key"]]
    floor_data = FLOORS[player["floor"]]
    
    text = f"🏰 **{floor_data['name']}**\n"
    text += f"👤 **Герой:** {cls_data['name']}\n"
    
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
    text = "🏰 **ГЛАВНОЕ МЕНЮ РПГ ИГРЫ**\n\nВыберите вашего героя (все ресурсы будут задеплоены на максимум!):"
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
    await callback.answer()
    cls_key = callback.data.split("_")[1]
    cls_data = CLASSES[cls_key]
    
    text = f"👤 **КЛАСС: {cls_data['name']}**\n\n"
    text += f"📜 {cls_data['desc']}\n\n"
    text += f"❤️ HP: {cls_data['hp']}\n"
    text += f"⚡ Старт {cls_data['res_name']}: **{cls_data['max_res']}/{cls_data['max_res']} (МАКСИМУМ)**\n\n"
    text += "Начать прохождение Башни?"
    
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
    
    # Ресурс выставляется РАВНЫМ МАКСИМУМУ на старте
    players[user_id] = {
        "class_key": cls_key,
        "hp": cls_data["hp"], "max_hp": cls_data["max_hp"],
        "res": cls_data["max_res"], "max_res": cls_data["max_res"],
        "floor": 1,
        "last_log": "Вы вошли на 1-й этаж башни!",
        "enemy": FLOORS[1]["monster"].copy(),
        "tank_blocking": False,
        "prepared_move": False
    }
    
    await render_room(callback, send_photo=True)

# === ОТОБРАЖЕНИЕ ИНТЕРФЕЙСА И КАРТИНКИ ===
async def render_room(callback: types.CallbackQuery, send_photo: bool = False):
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player: return

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

        builder.button(text="⏳ Пропустить ход (+15 ресурсов)", callback_data="skip_turn")
        builder.button(text="⏸️ Главное меню", callback_data="back_to_menu")
    else:
        # Если монстр повержен
        if player["floor"] < 4:
            builder.button(text="🚪 Подняться на следующий этаж", callback_data="next_floor")
        else:
            builder.button(text="👑 Вы прошли всю Башню! (Заново)", callback_data="back_to_menu")
        builder.button(text="⏸️ Главное меню", callback_data="back_to_menu")
        
    builder.adjust(1)

    # Если нужно отправить новое фото с монстром
    if send_photo and player["enemy"]:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=player["enemy"]["image"],
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    else:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
            try:
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
            except Exception:
                await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# === ПЕРЕХОД НА СЛЕДУЮЩИЙ ЭТАЖ ===
@dp.callback_query(F.data == "next_floor")
async def next_floor(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player: return
    
    player["floor"] += 1
    player["enemy"] = FLOORS[player["floor"]]["monster"].copy()
    player["last_log"] = f"🚪 Вы поднялись на {player['floor']}-й этаж!"
    
    await render_room(callback, send_photo=True)

# === ПРОПУСК ХОДА ===
@dp.callback_query(F.data == "skip_turn")
async def process_skip_turn(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    player = players.get(user_id)
    if not player or not player["enemy"]: return
    
    enemy = player["enemy"]
    cls_data = CLASSES[player["class_key"]]
    
    player["res"] = min(player["max_res"], player["res"] + 15)
    log = [f"⏳ Вы пропустили ход (+15 к {cls_data['res_name']})."]

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
            log.append(f"💥 Враг ударил на {enemy_dmg} урона.")
    else:
        log.append("🧱 Удар заблокирован!")
        player["tank_blocking"] = False

    if player["hp"] <= 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 В меню", callback_data="back_to_menu")
        await callback.message.answer("☠️ **ВЫ ПОГИБЛИ НА ЭТАЖЕ...**\nПопробуйте заново!", reply_markup=builder.as_markup(), parse_mode="Markdown")
        del players[user_id]
        return

    player["last_log"] = "\n".join(log)
    await render_room(callback)

# === ОБРАБОТКА НАВЫКОВ И БОЯ ===
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
        await callback.answer(f"Не хватает {cls_data['res_name']}!", show_alert=True)
        return
        
    await callback.answer()
    player["res"] -= skill["cost"]
    
    enemy = player["enemy"]
    log = []
    skip_enemy_turn = skill.get("enemy_skip_turn", False)
    
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
        log.append("🧱 Вы встали в глухую оборону!")

    if "heal_mana" in skill:
        player["res"] = min(cls_data["max_res"], player["res"] + skill["heal_mana"])
        log.append(f"🔮 Мана восстановлена (+{skill['heal_mana']}).")

    if "prep_move" in skill:
        player["prepared_move"] = True
        log.append("🎯 Вы начали прицеливание!")

    # Враг повержен
    if enemy["hp"] <= 0:
        player["enemy"] = None
        if player["floor"] < 4:
            player["last_log"] = f"🎉 Враг {enemy['name']} повержен! Открыт путь на {player['floor'] + 1}-й этаж!"
        else:
            player["last_log"] = "🏆 ПОБЕДА! Вы одолели Владыку и полностью прошли Башню!"
        await render_room(callback)
        return

    # Ответный урон от монстра
    if not player["tank_blocking"] and not skip_enemy_turn:
        enemy_dmg = random.randint(*enemy["dmg"])
        if player["class_key"] == "mage":
            mana_dmg = min(player["res"], enemy_dmg)
            player["res"] -= mana_dmg
            actual_dmg = enemy_dmg - mana_dmg
            player["hp"] -= actual_dmg
            log.append(f"💥 Враг ответил: -{mana_dmg} Щита и -{actual_dmg} HP.")
        else:
            player["hp"] -= enemy_dmg
            log.append(f"💥 Враг нанёс {enemy_dmg} урона.")
    elif player["tank_blocking"]:
        log.append("🧱 Удар врага был заблокирован!")
        player["tank_blocking"] = False

    if player["hp"] <= 0:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Главное меню", callback_data="back_to_menu")
        await callback.message.answer("☠️ **ВЫ ПОГИБЛИ В БОЮ...**", reply_markup=builder.as_markup(), parse_mode="Markdown")
        del players[user_id]
        return

    player["last_log"] = "\n".join(log)
    await render_room(callback)

# Фейковый сервер Render
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
    print("Бот RPG с картинками и этажами запущен!")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
