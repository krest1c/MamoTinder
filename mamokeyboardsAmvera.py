# mamokeyboards.py
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                           InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.utils.keyboard import InlineKeyboardBuilder
register = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅зарегистрироваться✅", callback_data="registerTrue")],
])

# Основное меню для выбора типа пользователя
main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="✏️Мой профиль")],
    [KeyboardButton(text="🧐Инфо"), KeyboardButton(text="🎁 Паки")],
    [KeyboardButton(text="📣Репорт")]
], resize_keyboard=True, input_field_placeholder="☝️выбери один из вариантов")

# Главное меню для игрока
main_player = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Искать клубы")],
    [KeyboardButton(text="✏️Мой профиль")],
    [KeyboardButton(text="🧐Инфо"), KeyboardButton(text="🎁 Паки")],
    [KeyboardButton(text="📣Репорт")],
    
], resize_keyboard=True, input_field_placeholder="☝️выбери один из вариантов")

# Главное меню для владельца клуба
main_owner = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔎 Поиск игроков")],
    [KeyboardButton(text="✏️Мой профиль")],
    [KeyboardButton(text="🧐Инфо"), KeyboardButton(text="🎁 Паки")],
    [KeyboardButton(text="📣Репорт")],
    
], resize_keyboard=True, input_field_placeholder="☝️выбери один из вариантов")

# Выбор типа пользователя при регистрации
user_type_selection = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="👤 Я ищу клуб"), KeyboardButton(text="👑 Я ищу игроков")],
], resize_keyboard=True, input_field_placeholder="Выберите вашу роль")



# Клавиатура подтверждения анкеты
anketa_succes = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅", callback_data="agree"), 
     InlineKeyboardButton(text="❌", callback_data="disagree")]
])
main_general = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧐Инфо")],
        [KeyboardButton(text="📣Репорт")],
        [KeyboardButton(text="🎁 Паки")]
    ],
    resize_keyboard=True
)
# Клавиатура для лайка/дизлайка анкет (для овнера)
# Клавиатура для лайка/дизлайка анкет (для овнера) - ОТДЕЛЬНЫЕ кнопки


# Клавиатура подтверждения смены роли
# Клавиатура подтверждения смены роли (ИЗМЕНИТЬ ЭТУ)
confirm_change_role_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="✅ Да, сменить роль"), KeyboardButton(text="❌ Нет, оставить текущую")],  # Изменили текст
    [KeyboardButton(text="⬅️ Назад")]
], resize_keyboard=True, input_field_placeholder="Подтвердите смену роли")

# Клавиатура подтверждения удаления анкеты (ИЗМЕНИТЬ ЭТУ)
confirm_delete_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="✅ Да, удалить анкету"), KeyboardButton(text="❌ Нет, сохранить анкету")],  # Изменили текст
    [KeyboardButton(text="⬅️ Назад")]
], resize_keyboard=True, input_field_placeholder="Подтвердите удаление")

# Меню профиля для игрока (с кнопкой создания анкеты)
vibor_for_player = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="📨 Входящие")],
        [KeyboardButton(text="📝 Создать анкету"), KeyboardButton(text="🗑️ Удалить анкету")],
        [KeyboardButton(text="🔎 Фильтр"), KeyboardButton(text="⚠️ Сменить роль")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Для владельца
vibor_for_owner = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="📨 Входящие")],
        [KeyboardButton(text="📝 Создать анкету"), KeyboardButton(text="🗑️ Удалить анкету")],
        [KeyboardButton(text="🔎 Фильтр"), KeyboardButton(text="⚠️ Сменить роль")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)


# Общее меню профиля (если тип не определен)
vibor_for_user = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="👤 Я ищу клуб"), KeyboardButton(text="👑 Я ищу игроков")],
    [KeyboardButton(text="⬅️ Назад")]
], resize_keyboard=True, input_field_placeholder="Выберите вашу роль")

podpiska_na_tgk_roma = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Подписаться на ТГК", url="https://t.me/romamamoball")],
    [InlineKeyboardButton(text="Подписаться на ТГК", url="https://t.me/mamoballtinder")],
])

dat_uz_usera_or_no = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👍 Связаться с клубом", callback_data="agree_uz")],
    [InlineKeyboardButton(text="❌ Отклонить", callback_data="disagree_uz")]
])

# Клавиатура для связи с игроком (для владельца клуба)
contact_player_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📞 Связаться с игроком", callback_data="contact_player")],
    [InlineKeyboardButton(text="❌ Отклонить заявку", callback_data="reject_player")]
])

anketa_succes = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅", callback_data="agree"), 
     InlineKeyboardButton(text="❌", callback_data="disagree")]
])
otmena = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="❌ Отмена")],
], resize_keyboard=True, input_field_placeholder="Заполнение анкеты")

# Простая клавиатура отмены (без других кнопок)
simple_otmena = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="❌ Отмена")],
], resize_keyboard=True, input_field_placeholder="Нажмите для отмены")


report_cancel = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="❌ Отменить обращение")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

contact_player_keyboard_owner = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📞 Связаться с игроком", callback_data="contact_player_yes")],
    [InlineKeyboardButton(text="❌ Отклонить", callback_data="contact_player_no")]
])

# Клавиатура для игрока (когда клуб хочет связаться)
contact_club_keyboard_player = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📞 Связаться с клубом", callback_data="contact_club_yes")],
    [InlineKeyboardButton(text="❌ Отклонить", callback_data="contact_club_no")]
])


sdelat_or_no_rassilka = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="✅ Сделать рассылку")],
    [KeyboardButton(text="❌ Не делать рассылку")],
                                ], resize_keyboard=True)

ban_or_no = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅Забанить", callback_data="banyes")],
    [InlineKeyboardButton(text="❌Отменить выдачу бана", callback_data="banno")],
    ])


anketa_like_dislike_owner = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="👍 Пригласить в клуб"), KeyboardButton(text="👎 Пропустить игрока")],
    [KeyboardButton(text="📧 Пригласить с сообщением")],
    [KeyboardButton(text="❌ Стоп просмотр игроков")]
], resize_keyboard=True, input_field_placeholder="Оцените игрока")

# Клавиатура для лайка/дизлайка клубов (для игрока) - ОБНОВЛЕННАЯ
anketa_like_dislike_player = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="👍 Отправить заявку"), KeyboardButton(text="👎 Пропустить клуб")],
    [KeyboardButton(text="📧 Отправить заявку с сообщением")],
    [KeyboardButton(text="❌ Стоп просмотр клубов")]
], resize_keyboard=True, input_field_placeholder="Оцените клуб")

# НОВАЯ клавиатура для отмены написания сообщения
cancel_message_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="❌ Отменить сообщение")]
], resize_keyboard=True, input_field_placeholder="Напишите сообщение или отмените")

def get_subscription_keyboard_all():
    """Клавиатура для проверки подписки на оба канала"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на @mamoballtinder",
                    url="https://t.me/mamoballtinder"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на @romamamoball",
                    url="https://t.me/romamamoball"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Я подписался на оба канала",
                    callback_data="check_subscription_all"
                )
            ]
        ]
    )

def get_subscription_keyboard():
    """Альтернативная клавиатура для проверки подписки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на каналы",
                    url="https://t.me/mamoballtinder"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription"
                )
            ]
        ]
    )
def filter_position_keyboard(current_filter: str = 'all') -> InlineKeyboardMarkup:
    """Клавиатура для выбора фильтра позиций"""
    
    # Создаем кнопки с отметкой текущего выбора
    buttons = []
    
    # Одиночные позиции
    buttons.append([
        InlineKeyboardButton(
            text=f"{'✅ ' if current_filter == 'op' else ''}Только OP (опорники)",
            callback_data="filter_position_op"
        )
    ])
    
    buttons.append([
        InlineKeyboardButton(
            text=f"{'✅ ' if current_filter == 'gk' else ''}Только GK (вратари)",
            callback_data="filter_position_gk"
        )
    ])
    
    buttons.append([
        InlineKeyboardButton(
            text=f"{'✅ ' if current_filter == 'nap' else ''}Только NAP (нападающие)",
            callback_data="filter_position_nap"
        )
    ])
    
    # Комбинации
    buttons.append([
        InlineKeyboardButton(
            text=f"{'✅ ' if current_filter == 'op+gk' else ''}OP + GK",
            callback_data="filter_position_op+gk"
        ),
        InlineKeyboardButton(
            text=f"{'✅ ' if current_filter == 'op+nap' else ''}OP + NAP",
            callback_data="filter_position_op+nap"
        )
    ])
    
    buttons.append([
        InlineKeyboardButton(
            text=f"{'✅ ' if current_filter == 'gk+nap' else ''}GK + NAP",
            callback_data="filter_position_gk+nap"
        ),
        InlineKeyboardButton(
            text=f"{'✅ ' if current_filter == 'op+gk+nap' else ''}Все позиции",
            callback_data="filter_position_op+gk+nap"
        )
    ])
    
    # Кнопка "Все позиции" (упрощенная)
    buttons.append([
        InlineKeyboardButton(
            text=f"{'✅ ' if current_filter == 'all' else ''}Все позиции (без фильтра)",
            callback_data="filter_position_all"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text=f"{' ' if current_filter == 'all' else ''}Сохранить фильтр",
            callback_data="save_filter"
        )
    ])
    
    # Кнопка возврата

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Клавиатура для выбора позиции игрока
def get_player_positions_keyboard():
    """Inline-клавиатура для выбора позиции игрока"""
    keyboard = [
        [
            InlineKeyboardButton(text="ОП (опорник)", callback_data="position_op"),
            InlineKeyboardButton(text="ГК (вратарь)", callback_data="position_gk"),
        ],
        [
            InlineKeyboardButton(text="НАП (нападающий)", callback_data="position_nap"),
            InlineKeyboardButton(text="ОП+ГК", callback_data="position_op+gk"),
        ],
        [
            InlineKeyboardButton(text="ОП+НАП", callback_data="position_op+nap"),
            InlineKeyboardButton(text="ГК+НАП", callback_data="position_gk+nap"),
        ],
        [
            InlineKeyboardButton(text="Универсал (все позиции)", callback_data="position_op+gk+nap"),
        ],
        [InlineKeyboardButton(text="Отмена", callback_data="position_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для выбора позиций для овнера (какие позиции ищет клуб)
def get_owner_positions_keyboard():
    """Inline-клавиатура для выбора позиций владельца"""
    keyboard = [
        [
            InlineKeyboardButton(text="ОП (опорники)", callback_data="owner_position_op"),
            InlineKeyboardButton(text="ГК (вратари)", callback_data="owner_position_gk"),
        ],
        [
            InlineKeyboardButton(text="НАП (нападающие)", callback_data="owner_position_nap"),
            InlineKeyboardButton(text="ОП+ГК", callback_data="owner_position_op+gk"),
        ],
        [
            InlineKeyboardButton(text="ОП+НАП", callback_data="owner_position_op+nap"),
            InlineKeyboardButton(text="ГК+НАП", callback_data="owner_position_gk+nap"),
        ],
        [
            InlineKeyboardButton(text="Все позиции", callback_data="owner_position_op+gk+nap"),
        ],]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для подтверждения выбора позиции
def get_position_confirm_keyboard(user_type: str):
    """Клавиатура для подтверждения выбора позиции"""
    if user_type == "player":
        keyboard = [
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_position_player"),
                InlineKeyboardButton(text="🔄 Изменить", callback_data="change_position_player")
            ]
        ]
    else:  # owner
        keyboard = [
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_position_owner"),
                InlineKeyboardButton(text="🔄 Изменить", callback_data="change_position_owner")
            ]
        ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


#
def get_kartezhnik_keyboard():
    """Клавиатура для Картежник пака"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Купить за 7 звезд", callback_data="oplata_yes_kartezhnik")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="kartezhnik_info"),
        InlineKeyboardButton(text="⬅️ К пакам", callback_data="back_to_packs")
    )
    return builder.as_markup()
# Обновите существующую клавиатуру packs, добавив новый пак
packs = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎄 Новогодний пак", callback_data="newyearpack")],
    [InlineKeyboardButton(text="🎲 Картежник ", callback_data="kartezhnikpack")],  # Добавлено
    [InlineKeyboardButton(text="🍀 Лаки Пак", callback_data="luckypack")],
    [InlineKeyboardButton(text="🔥 Супер-пак", callback_data="superpack")]
])

# Объединенная клавиатура для новогоднего пакета
def get_newyear_pack_keyboard(with_back: bool = True):
    """Единая клавиатура для новогоднего пакета"""
    keyboard = [
        [InlineKeyboardButton(text="⚡ Оплатить рулетку", callback_data="oplata_yes_new_year_pack")]
    ]
    
    if with_back:
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="oplata_no")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Инвойс клавиатура с pay-кнопкой
def get_payment_invoice_keyboard(payload: str = None):
    """Клавиатура для инвойса оплаты"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Оплатить", pay=True)
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="oplata_no")
    )
    return builder.as_markup()

def get_superpack_keyboard(with_back: bool = True):
    """Единая клавиатура для новогоднего пакета"""
    keyboard = [
        [InlineKeyboardButton(text="⚡ Оплатить пак", callback_data="oplata_yes_superpack")]
    ]
    
    if with_back:
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="oplata_no")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

request_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Одобрить заявку", callback_data="accept_request")],
    [InlineKeyboardButton(text="❌ Отклонить заявку", callback_data="deny_request")]
])

request_otmena_kb = ReplyKeyboardMarkup(keyboard=
                                        [
                                            [KeyboardButton(text="❌ Отмена заявки")]
                                        ], resize_keyboard=True)


# В mamokeyboardsAmvera.py в разделе с клавиатурами трейдинга добавьте:

# Клавиатура главного меню трейдинга (уже существующая)
leaders_main = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="💰 По коинам", callback_data="leaders_coins"),
        InlineKeyboardButton(text="🃏 По карточкам", callback_data="leaders_cards")
    ],
    [
        InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
    ]
])

# Обновим основную панель трейдинга (добавим кнопку Лидеры)
trade_main = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🛒 Купить карточки", callback_data="bay_cards"),
        InlineKeyboardButton(text="💰 Продать карточки", callback_data="sell_my_card")
    ],
    [
        InlineKeyboardButton(text="🎨 Крафт", callback_data="craft_cards"),
        InlineKeyboardButton(text="📊 Профиль", callback_data="trade_profile")
    ],
    [
        InlineKeyboardButton(text="🏆 Лидеры", callback_data="trade_leaders"),
        InlineKeyboardButton(text="📜 История покупок", callback_data="view_user_history")
    ]
])


def get_buy_cards_keyboard(page: int = 0, total_pages: int = 1, cards: list = None):
    """Создает клавиатуру для списка карточек в продаже"""
    builder = InlineKeyboardBuilder()
    
    # Если есть карточки, показываем их с кнопками покупки
    if cards:
        for i, card in enumerate(cards, 1):
            # Кнопка покупки конкретной карточки
            builder.row(
                InlineKeyboardButton(
                    text=f"🛒 Купить: {card['nickname']} - {card['price']} коинов",
                    callback_data=f"buy_card_{card['sell_id']}"
                )
            )
    
    # Навигация по страницам
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"buy_page_{page - 1}"
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="noop"
        )
    )
    
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=f"buy_page_{page + 1}"
            )
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Основные кнопки
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="bay_cards"),
        InlineKeyboardButton(text="💰 Продать карточку", callback_data="sell_my_card")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои продажи", callback_data="my_active_sales"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
    )
    
    return builder.as_markup()

# Клавиатура для подтверждения покупки
def get_purchase_confirmation_keyboard(sell_id: int):
    """Создает клавиатуру для подтверждения покупки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, купить", callback_data=f"confirm_buy_{sell_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy")
        ]
    ])

# Клавиатура для списка карточек пользователя для продажи
def get_sell_cards_keyboard(page: int = 0, total_pages: int = 1, cards: list = None):
    """Создает клавиатуру для списка карточек пользователя для продажи"""
    builder = InlineKeyboardBuilder()
    
    # Если есть карточки, показываем их с кнопками продажи
    if cards:
        for i, card in enumerate(cards, 1):
            # Кнопка продажи конкретной карточки
            builder.row(
                InlineKeyboardButton(
                    text=f"💰 Продать: {card['nickname']} (ID: {card['id']})",
                    callback_data=f"sell_card_{card['id']}"
                )
            )
    
    # Навигация по страницам
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"sell_page_{page - 1}"
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="noop"
        )
    )
    
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=f"sell_page_{page + 1}"
            )
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Основные кнопки
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="sell_my_card"),
        InlineKeyboardButton(text="📋 Мои продажи", callback_data="my_active_sales")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
    )
    
    return builder.as_markup()

# Клавиатура для указания цены продажи
def get_sell_price_keyboard(card_id: int):
    """Создает клавиатуру для указания цены продажи"""
    builder = InlineKeyboardBuilder()
    
    # Быстрые кнопки с ценами
    builder.row(
        InlineKeyboardButton(text="💰 10 коинов", callback_data=f"set_price_{card_id}_10"),
        InlineKeyboardButton(text="💰 50 коинов", callback_data=f"set_price_{card_id}_50")
    )
    builder.row(
        InlineKeyboardButton(text="💰 100 коинов", callback_data=f"set_price_{card_id}_100"),
        InlineKeyboardButton(text="💰 500 коинов", callback_data=f"set_price_{card_id}_500")
    )
    builder.row(
        InlineKeyboardButton(text="💰 1000 коинов", callback_data=f"set_price_{card_id}_1000"),
        InlineKeyboardButton(text="💰 5000 коинов", callback_data=f"set_price_{card_id}_5000")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="sell_my_card")
    )
    
    return builder.as_markup()

# Клавиатура для подтверждения продажи
def get_sell_confirmation_keyboard(card_id: int, price: int):
    """Создает клавиатуру для подтверждения продажи"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, выставить на продажу", callback_data=f"confirm_sell_{card_id}_{price}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="sell_my_card")
        ]
    ])




trade_obmen = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")]
])


def get_luckypack_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Купить за 5 звезд", callback_data="oplata_yes_luckypack")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="oplata_no")]
    ])


