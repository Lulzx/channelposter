#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import os
import sys
import time
from functools import wraps
from uuid import uuid4
from cal import *
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, InlineQueryResultArticle, \
    InputTextMessageContent
from process_engine import *
from telegram.ext import DispatcherHandlerStop
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, InlineQueryHandler, CallbackQueryHandler
from tinydb import TinyDB, Query

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
    dp.add_handler(CommandHandler("start", start))
    """conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        states={
            GENDER: [RegexHandler('^(Boy|Girl|Other)$', gender)],

            PHOTO: [MessageHandler(Filters.photo, photo),
                    CommandHandler('skip', skip_photo)],

            LOCATION: [MessageHandler(Filters.location, location),
                       CommandHandler('skip', skip_location)],

            BIO: [MessageHandler(Filters.text, bio)]
        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(conv_handler)"""
    dp.add_handler(CommandHandler("calendar", calendar_handler))
    dp.add_handler(CallbackQueryHandler(inline_handler))
    dp.add_handler(InlineQueryHandler(inline))
    dp.add_handler(MessageHandler(~Filters.command, process_message))
    dp.add_error_handler(MessageHandler(Filters.command, unknown))
    dp.add_error_handler(error)
    updater.start_polling()
    logger.info("Ready to rock..!")
    updater.idle()


if __name__ == '__main__':
    main()
