# patch.py
import os

def replace_function(filename, func_name, new_func_code):
    if not os.path.exists(filename):
        print(f"❌ Файл {filename} не найден!")
        return

    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    if f"def {func_name}" not in content and f"async def {func_name}" not in content:
        print(f"⚠️ Функция {func_name} не найдена в {filename}.")
        return

    start_idx = content.find(f"async def {func_name}")
    if start_idx == -1:
        start_idx = content.find(f"def {func_name}")

    next_def = content.find("def ", start_idx + 10)
    
    if next_def == -1:
        new_content = content[:start_idx] + new_func_code + "\n"
    else:
        new_content = content[:start_idx] + new_func_code + "\n\n" + content[next_def:]

    with open(filename, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"✅ Успешно заменена функция {func_name} в {filename}!")

if __name__ == "__main__":
    # 1. Заменяем activate_check_link
    new_activate = '''@router.message(F.text.startswith("/start check_"))
async def activate_check_link(msg: Message, state: FSMContext):
    cid = msg.text.split("check_", 1)[1].strip()
    try:
        res = await activate_check(cid, msg.from_user.id)
        await msg.answer(f"✅ <b>Вы успешно активировали чек на {res['per_activation']} {res['asset']}!</b>", parse_mode="HTML")
        
        inline_id = await get_check_message(cid)
        if inline_id:
            chat_id, message_id = map(int, inline_id.split(":"))
            await msg.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"✅ <b>Чек на {res['per_activation']} {res['asset']} активирован</b>",
                parse_mode="HTML",
                reply_markup=None
            )
    except CheckError as e:
        if e.code == "bad_password":
            await state.update_data(cid=cid)
            await state.set_state(CheckFSM.waiting_activate_pass)
            await msg.answer("🔒 Этот чек защищён паролем. Введите пароль:")
        elif e.code == "own_check":
            await msg.answer("❌ Вы не можете активировать свой собственный чек.")
        elif e.code == "exhausted":
            await msg.answer("❌ Этот чек уже активирован.")
        elif e.code == "already_activated":
            await msg.answer("❌ Вы уже активировали этот чек.")
        else:
            await msg.answer(f"❌ Ошибка: {e.code}")'''
    
    replace_function("more.py", "activate_check_link", new_activate)

    # 2. Заменяем process_activate_pass
    new_pass = '''@router.message(CheckFSM.waiting_activate_pass)
async def process_activate_pass(msg: Message, state: FSMContext):
    data = await state.get_data()
    cid = data["cid"]
    try:
        res = await activate_check(cid, msg.from_user.id, msg.text)
        await msg.answer(f"✅ <b>Вы успешно активировали чек на {res['per_activation']} {res['asset']}!</b>", parse_mode="HTML")
        await state.clear()
    except CheckError as e:
        if e.code == "bad_password":
            await msg.answer("❌ Неверный пароль. Попробуйте снова.")
        else:
            await msg.answer(f"❌ Ошибка: {e.code}")
            await state.clear()'''
    
    replace_function("more.py", "process_activate_pass", new_pass)