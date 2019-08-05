import time
import calendar
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import ReplyKeyboardRemove

def create_callback_data(action, year, month, day):
    return ";".join([action, str(year), str(month), str(day)])


def separate_callback_data(data):
    return data.split(";")


def create_calendar(year=None, month=None):
    now = datetime.datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    data_ignore = create_callback_data("IGNORE", year, month, 0)
    keyboard = []
    row = [InlineKeyboardButton(calendar.month_name[month] + " " + str(year), callback_data=data_ignore)]
    keyboard.append(row)
    row = []
    for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        row.append(InlineKeyboardButton(day, callback_data=data_ignore))
    keyboard.append(row)

    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data=data_ignore))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=create_callback_data("DAY", year, month, day)))
        keyboard.append(row)
    row = [InlineKeyboardButton("⬅️", callback_data=create_callback_data("PREV-MONTH", year, month, day)),
           InlineKeyboardButton("🔄", callback_data=data_ignore),
           InlineKeyboardButton("➡️", callback_data=create_callback_data("NEXT-MONTH", year, month, day))]
    keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


def create_options_keyboard(options, cancel_msg):
    rows = []
    for i, op in enumerate(options):
        rows.append([InlineKeyboardButton(op, callback_data="CHOSEN;" + str(i))])
    if cancel_msg is not None:
        rows.append([InlineKeyboardButton(cancel_msg, callback_data="CANCEL;0")])
    return InlineKeyboardMarkup(rows)


def process_option_selection(update, context):
    query = update.callback_query
    data = update.callback_query.data
    action, index = data.split(";")
    ret_data = (False, None)
    if action == "CHOSEN":
        context.bot.edit_message_text(text=query.message.text,
                                      chat_id=query.message.chat_id,
                                      message_id=query.message.message_id,
                                      )
        ret_data = True, int(index)
    elif action == "CANCEL":
        context.bot.edit_message_text(text=query.message.text,
                                      chat_id=query.message.chat_id,
                                      message_id=query.message.message_id
                                      )
        ret_data = False, 0
    else:
        context.bot.answer_callback_query(callback_query_id=query.id, text="Something went wrong!")
    return ret_data


def process_calendar_selection(update, context):
    ret_data = (False, None)
    query = update.callback_query
    (action, year, month, day) = separate_callback_data(query.data)
    curr = datetime.datetime(int(year), int(month), 1)
    if action == "IGNORE":
        context.bot.answer_callback_query(callback_query_id=query.id)
    elif action == "DAY":
        context.bot.edit_message_text(text=query.message.text,
                                      chat_id=query.message.chat_id,
                                      message_id=query.message.message_id
                                      )
        ret_data = True, datetime.datetime(int(year), int(month), int(day))
    elif action == "PREV-MONTH":
        pre = curr - datetime.timedelta(days=1)
        context.bot.edit_message_text(text=query.message.text,
                                      chat_id=query.message.chat_id,
                                      message_id=query.message.message_id,
                                      reply_markup=create_calendar(int(pre.year), int(pre.month)))
    elif action == "NEXT-MONTH":
        ne = curr + datetime.timedelta(days=31)
        context.bot.edit_message_text(text=query.message.text,
                                      chat_id=query.message.chat_id,
                                      message_id=query.message.message_id,
                                      reply_markup=create_calendar(int(ne.year), int(ne.month)))
    else:
        context.bot.answer_callback_query(callback_query_id=query.id, text="Something went wrong!")
    return ret_data


def calendar_handler(update, context):
    update.message.reply_text("Please select a date: ",
                              reply_markup=create_calendar())


def inline_handler(update, context):
    selected, date = process_calendar_selection(update, context)
    if selected:
        context.bot.send_message(chat_id=update.callback_query.from_user.id,
                                 text="You selected %s" % (date.strftime("%d/%m/%Y")),
                                 reply_markup=ReplyKeyboardRemove())
