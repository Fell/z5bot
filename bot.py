import json
import logging
import os
import sys
import time

import redis
import telegram.ext

from dfrotz import DFrotz
import models
import parser

logging.basicConfig(
    format='[%(asctime)s-%(name)s-%(levelname)s]\n%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG,
)
logging.getLogger('telegram').setLevel(logging.WARNING)

def log_dialog(in_message, out_message):
    logging.info('@%s[%d] sent: %r' % (
        in_message.from_user.username,
        in_message.from_user.id,
        in_message.text[:40])
    )
    logging.info('Answering @%s[%d]: %r' % (
        in_message.from_user.username,
        in_message.from_user.id,
        out_message.text[:40] if out_message is not None else '[None]')
    )

def on_error(bot, update, error):
    logger = logging.getLogger(__name__)
    logger.warn('Update %r caused error %r!' % (update, error))
    print(error)

def cmd_default(bot, message, z5bot, chat):
    # gameplay messages will be sent here
    if message.text.strip().lower() == 'load':
        text = 'Please use /load.'
        return bot.sendMessage(message.chat_id, text)

    if message.text.strip().lower() == 'save':
        text = 'Your progress is being saved automatically. But /load is available.'
        return bot.sendMessage(message.chat_id, text)

    if not chat.has_story():
        text = 'Please use the /select command to select a game.'
        return bot.sendMessage(message.chat_id, text)

    # here, stuff is sent to the interpreter
    z5bot.redis.rpush('%d:%s' % (message.chat_id, chat.story.abbrev), message.text)
    z5bot.process(message.chat_id, message.text)

    received = z5bot.receive(message.chat_id)
    reply = bot.sendMessage(message.chat_id, received)
    log_dialog(message, reply)

    if ' return ' in received.lower() or ' enter ' in received.lower():
        notice = '(Note: You are able to do use the return key by typing /enter.)'
        return bot.sendMessage(message.chat_id, notice)

def cmd_start(bot, message, *args):
    text =  'Welcome, %s!\n' % message.from_user.first_name
    text += 'Please use the /select command to select a game.\n'
    return bot.sendMessage(message.chat_id, text)

def cmd_select(bot, message, z5bot, chat):
    selection = 'For "%s", write /select %s.'
    msg_parts = []
    for story in models.Story.instances:
        part = selection % (story.name, story.abbrev)
        msg_parts.append(part)
    text = '\n'.join(msg_parts)

    for story in models.Story.instances:
        if ' ' in message.text and message.text.strip().lower().split(' ')[1] == story.abbrev:
            chat.set_story(models.Story.get_instance_by_abbrev(story.abbrev))
            z5bot.add_chat(chat)
            reply = bot.sendMessage(message.chat_id, 'Starting "%s"...' % story.name)
            log_dialog(message, reply)
            notice  = 'Your progress will be saved automatically.'
            reply = bot.sendMessage(message.chat_id, notice)
            log_dialog(message, reply)
            reply = bot.sendMessage(message.chat_id, z5bot.receive(message.chat_id))
            log_dialog(message, reply)
            if z5bot.redis.exists('%d:%s' % (message.chat_id, chat.story.abbrev)):
                notice  = 'Some progress in %s already exists. Use /load to restore it ' % (chat.story.name)
                notice += 'or /clear to reset your recorded actions.'
                reply = bot.sendMessage(message.chat_id, notice)
                log_dialog(message, reply)
            return

    return bot.sendMessage(message.chat_id, text)

def cmd_load(bot, message, z5bot, chat):
    if not chat.has_story():
        text = 'You have to select a game first.'
        return bot.sendMessage(message.chat_id, text)
        
    if not z5bot.redis.exists('%d:%s' % (message.chat_id, chat.story.abbrev)):
        text = 'There is no progress to load.'
        return bot.sendMessage(message.chat_id, text)

    text = 'Restoring %d messages. Please wait.' % z5bot.redis.llen('%d:%s' % (message.chat_id, chat.story.abbrev))
    reply = bot.sendMessage(message.chat_id, text)
    log_dialog(message, reply)

    saved_messages = z5bot.redis.lrange('%d:%s' % (message.chat_id, chat.story.abbrev), 0, -1)

    for index, db_message in enumerate(saved_messages):
        z5bot.process(message.chat_id, db_message.decode('utf-8'))
        if index == len(saved_messages)-2:
            z5bot.receive(message.chat_id) # clear buffer
    reply = bot.sendMessage(message.chat_id, 'Done.')
    log_dialog(message, reply)
    return bot.sendMessage(message.chat_id, z5bot.receive(message.chat_id))


def cmd_clear(bot, message, z5bot, chat):
    if not z5bot.redis.exists('%d:%s' % (message.chat_id, chat.story.abbrev)):
        text = 'There is no progress to clear.'
        return bot.sendMessage(message.chat_id, text)

    text = 'Deleting %d messages. Please wait.' % z5bot.redis.llen('%d:%s' % (message.chat_id, chat.story.abbrev))
    reply = bot.sendMessage(message.chat_id, text)
    log_dialog(message, reply)

    z5bot.redis.delete('%d:%s' % (message.chat_id, chat.story.abbrev))
    return bot.sendMessage(message.chat_id, 'Done.')

def cmd_enter(bot, message, z5bot, chat):
    if not chat.has_story():
        return

    command = '' # \r\n is automatically added by the Frotz abstraction layer
    z5bot.redis.rpush('%d:%s' % (message.chat_id, chat.story.abbrev), command)
    z5bot.process(message.chat_id, command)
    return bot.sendMessage(message.chat_id, z5bot.receive(message.chat_id))

def cmd_broadcast(bot, message, z5bot, *args):
    if z5bot.broadcasted or len(sys.argv) <= 1:
        return

    print(z5bot.redis.keys())
    active_chats = [int(chat_id.decode('utf-8').split(':')[0]) for chat_id in z5bot.redis.keys()]
    logging.info('Broadcasting to %d chats.' % len(active_chats))
    with open(sys.argv[1], 'r') as f:
        notice = f.read()
    for chat_id in active_chats:
        logging.info('Notifying %d...' % chat_id)
        try:
            bot.sendMessage(chat_id, notice)
        except:
            continue
        time.sleep(2) # cooldown
    z5bot.broadcasted = True

def cmd_ignore(*args):
    return

def cmd_ping(bot, message, *args):
    return bot.sendMessage(message.chat_id, 'Pong!')


def on_message(bot, update):
    message = update.message
    z5bot = models.Z5Bot.get_instance_or_create()
    func = z5bot.parser.get_function(message.text)
    chat = models.Chat.get_instance_or_create(message.chat_id)

    out_message = func(bot, message, z5bot, chat)

    log_dialog(message, out_message)

if __name__ == '__main__':
    with open('config.json', 'r') as f:
        config = json.load(f)

    api_key = config['api_key']
    logging.info('Logging in with api key %r.' % api_key)
    if len(sys.argv) > 1:
        logging.info('Broadcasting is available! Send /broadcast.')

    for story in config['stories']:
        models.Story(
            name=story['name'],
            abbrev=story['abbrev'],
            filename=story['filename']
        )

    z5bot = models.Z5Bot.get_instance_or_create()

    p = parser.Parser()
    p.add_default(cmd_default)
    p.add_command('/start', cmd_start)
    p.add_command('/select', cmd_select)
    p.add_command('/load', cmd_load)
    p.add_command('/clear', cmd_clear)
    p.add_command('/enter', cmd_enter)
    p.add_command('/broadcast', cmd_broadcast)
    p.add_command('/i', cmd_ignore)
    p.add_command('/ping', cmd_ping)
    z5bot.add_parser(p)

    r = redis.StrictRedis(
        host=config['redis']['host'],
        port=config['redis']['port'],
        db=config['redis']['db'],
        password=config['redis']['password'],
    )
    z5bot.add_redis(r)

    updater = telegram.ext.Updater(api_key)
    dispatcher = updater.dispatcher
    # Make sure the user's messages get redirected to our parser,
    # with or without a slash in front of them.
    dispatcher.addTelegramMessageHandler(on_message)
    dispatcher.addUnknownTelegramCommandHandler(on_message)
    dispatcher.addErrorHandler(on_error)
    updater.start_polling()
    updater.idle()