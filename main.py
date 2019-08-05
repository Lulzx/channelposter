#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import os
import sys
import time
from functools import wraps
from uuid import uuid4
import pickle
from threading import Event
from time import time
from datetime import timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, InlineQueryResultArticle, \
    InputTextMessageContent
from telegram.ext.dispatcher import run_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode    
from telegram.ext import DispatcherHandlerStop
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, InlineQueryHandler, CallbackQueryHandler
from tinydb import TinyDB, Query
import time
import calendar
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import ReplyKeyboardRemove

db = TinyDB('db.json')
user = Query()

logging.basicConfig(format='%(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

def start(update, context):
    update.message.reply_text("Hi!")
    context.bot.send_message("Use me.")


def before_processing(update, context):
    if update.effective_chat.type != "private":
        text = "This bot works only in private."
        update.effective_message.reply_text(text=text)
        context.bot.leave_chat(chat_id=update.effective_message.chat_id)
        raise DispatcherHandlerStop


JOBS_PICKLE = 'job_tuples.pickle'


def load_jobs(jq):
    now = time()

    with open(JOBS_PICKLE, 'rb') as fp:
        while True:
            try:
                next_t, job = pickle.load(fp)
            except EOFError:
                break  # Loaded all job tuples

            # Create threading primitives
            enabled = job._enabled
            removed = job._remove

            job._enabled = Event()
            job._remove = Event()

            if enabled:
                job._enabled.set()

            if removed:
                job._remove.set()

            next_t -= now  # Convert from absolute to relative time

            jq._put(job, next_t)


def save_jobs(jq):
    if jq:
        job_tuples = jq._queue.queue
    else:
        job_tuples = []

    with open(JOBS_PICKLE, 'wb') as fp:
        for next_t, job in job_tuples:
            # Back up objects
            _job_queue = job._job_queue
            _remove = job._remove
            _enabled = job._enabled

            # Replace un-pickleable threading primitives
            job._job_queue = None  # Will be reset in jq.put
            job._remove = job.removed  # Convert to boolean
            job._enabled = job.enabled  # Convert to boolean

            # Pickle the job
            pickle.dump((next_t, job), fp)

            # Restore objects
            job._job_queue = _job_queue
            job._remove = _remove
            job._enabled = _enabled


def save_jobs_job(context):
    save_jobs(context.job_queue)


class MWT(object):
    _caches = {}
    _timeouts = {}

    def __init__(self, timeout=2):
        self.timeout = timeout

    def collect(self):
        for func in self._caches:
            cache = {}
            for key in self._caches[func]:
                if (time.time() - self._caches[func][key][1]) < self._timeouts[func]:
                    cache[key] = self._caches[func][key]
            self._caches[func] = cache

    def __call__(self, f):
        self.cache = self._caches[f] = {}
        self._timeouts[f] = self.timeout

        def func(*args, **kwargs):
            kw = sorted(kwargs.items())
            key = (args, tuple(kw))
            try:
                v = self.cache[key]
                if (time.time() - v[1]) > self.timeout:
                    raise KeyError
            except KeyError:
                v = self.cache[key] = f(*args, **kwargs), time.time()
            return v[0]

        func.func_name = f.__name__
        return func


@MWT(timeout=60 * 60)
def get_admin_ids(context, chat_id):
    return [admin.user.id for admin in context.bot.get_chat_administrators(chat_id)]


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        chat_id = sys.argv[2]
        LIST_OF_ADMINS = get_admin_ids(context, chat_id)
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)

    return wrapped


def unknown(update, context):
    context.bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command.")


@run_async
def process_message(update, context, remove_caption=False, custom_caption=None):
    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 Add url buttons", callback_data='add_url_button')],[
        InlineKeyboardButton("📢 Publish to channel", callback_data='channel_id;announce')],[
        InlineKeyboardButton("🔕 Publish to channel (silent)", callback_data='channel_id;silent')],[
        InlineKeyboardButton("📬 Share", switch_inline_query='message_id')]])
    if update.edited_message:
        message = update.edited_message
    elif remove_caption:
        message = update.message.reply_to_message
    elif custom_caption is not None:
        message = update.message.reply_to_message
    else:
        message = update.message

    if custom_caption is None:
        caption = message.caption_html if (message.caption and remove_caption is False) else None
    else:
        caption = custom_caption

    if message.text:
        message.reply_text(text=message.text_html, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    elif message.voice:
        media = message.voice.file_id
        duration = message.voice.duration
        message.reply_voice(voice=media, duration=duration, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    elif message.photo:
        media = message.photo[-1].file_id
        message.reply_photo(photo=media, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    elif message.sticker:
        media = message.sticker.file_id
        message.reply_sticker(sticker=media, reply_markup=reply_markup)

    elif message.document:
        media = message.document.file_id
        filename = message.document.file_name
        message.reply_document(document=media, filename=filename, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    elif message.audio:
        media = message.audio.file_id
        duration = message.audio.duration
        performer = message.audio.performer
        title = message.audio.title
        message.reply_audio(
            audio=media,
            duration=duration,
            performer=performer,
            title=title,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML)

    elif message.video:
        media = message.video.file_id
        duration = message.video.duration
        message.reply_video(video=media, duration=duration, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    elif message.contact:
        phone_number = message.contact.phone_number
        first_name = message.contact.first_name
        last_name = message.contact.last_name
        message.reply_contact(
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            reply_markup=reply_markup)

    elif message.venue:
        longitude = message.venue.location.longitude
        latitude = message.venue.location.latitude
        title = message.venue.title
        address = message.venue.address
        foursquare_id = message.venue.foursquare_id
        message.reply_venue(
            longitude=longitude,
            latitude=latitude,
            title=title,
            address=address,
            foursquare_id=foursquare_id,
            reply_markup=reply_markup)

    elif message.location:
        longitude = message.location.longitude
        latitude = message.location.latitude
        message.reply_location(latitude=latitude, longitude=longitude, reply_markup=reply_markup)

    elif message.video_note:
        media = message.video_note.file_id
        length = message.video_note.length
        duration = message.video_note.duration
        message.reply_video_note(video_note=media, length=length, duration=duration, reply_markup=reply_markup)

    elif message.game:
        text = "Sorry, telegram doesn't allow to echo this message"
        message.reply_text(text=text, quote=True)

    else:
        text = "Sorry, this kind of media is not supported yet"
        message.reply_text(text=text, quote=True)


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


def inline(update, context, switch_pm=None):
    query = update.inline_query.query
    text = ""
    if not switch_pm:
        switch_pm = ['Switch to PM', 'help']
    try:
        search = db.get(user['message_id'] == query)
        json_str = json.dumps(search)
        resp = json.loads(json_str)
        try:
            text = resp['text']
        except TypeError:
            if search is None:
                text = "Go to private"
        result = [
            InlineQueryResultArticle(
                id=uuid4(),
                title="Your message",
                description="Click here to send in this chat",
                input_message_content=InputTextMessageContent(
                    "{}".format(text)))]
        update.inline_query.answer(result, switch_pm_text=f'{switch_pm[0]}', switch_pm_parameter=f'{switch_pm[1]}')
    except IndexError:
        pass


def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    try:
        TOKEN = sys.argv[1]
    except IndexError:
        TOKEN = os.environ.get("TOKEN")
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    job_queue = updater.job_queue
    job_queue.run_repeating(save_jobs_job, timedelta(minutes=1))
    try:
        load_jobs(job_queue)
    except FileNotFoundError:
        pass
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("calendar", calendar_handler))
    dp.add_handler(CallbackQueryHandler(inline_handler))
    dp.add_handler(InlineQueryHandler(inline))
    dp.add_handler(MessageHandler(~Filters.command, process_message))
    dp.add_error_handler(MessageHandler(Filters.command, unknown))
    dp.add_error_handler(error)
    updater.start_polling()
    logger.info("Ready to rock..!")
    updater.idle()
    save_jobs(job_queue)    


if __name__ == '__main__':
    main()
