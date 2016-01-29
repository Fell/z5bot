import logging
import os

import telegram

from dfrotz import DFrotz

logging.basicConfig(
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  level=logging.DEBUG,
)
logging.getLogger('telegram').setLevel(logging.INFO)

class MenuState:
  pass

class GameSelectionState(MenuState):
  def execute(self):
    return 

class Story:

  instances = []

  def __init__(self, name, abbrev, filename):
    self.__class__.instances.append(self)
    self.name = name
    self.abbrev = abbrev
    self.path = os.path.join('stories', filename)

  @classmethod
  def get_instance_by_abbrev(self, abbrev):
    for story in self.instances:
      if story.abbrev == abbrev:
        return story

class Player:

  instances = []

  def __init__(self, username):
    self.__class__.instances.append(self)
    self.username = username
    self.story = None
    #self.stage = 

  @classmethod
  def get_instance_by_username(self, username):
    for player in self.instances:
      if player.username == username:
        return player

  def set_story(self, story):
    self.story = story
    self.frotz = DFrotz(Z5Bot.interpreter, self.story.path)

  def __repr__(self):
    if self.story is not None:
      return '<Player %r, playing %r>' % (self.username, self.story.name)

    return '<Player %r>' % self.username

class Z5Bot:

  instances = []
  interpreter = os.path.join('tools', 'dfrotz')

  def __init__(self):
    self.__class__.instances.append(self)
    self.players = []

  def add_player(self, player):
    self.players.append(player)

  def get_player_by_username(self, username):
    for player in self.players:
      if player.username == username:
        return player

  def process(self, username, command):
    import pprint
    pprint.pprint(self.players)

    self.player = self.get_player_by_username(username)
    self.player.frotz.send('%s\r\n' % command)

  def receive(self, username):
    self.player = self.get_player_by_username(username)
    return self.player.frotz.get()


def cmd_start(bot, update):
  text =  'Welcome, %s!\n' % update.message.from_user.first_name
  text += 'Please use the /select command to select a game.'
  bot.sendMessage(update.message.chat_id, text=text)

def cmd_select(bot, update):
  
  text = 'For Zork 1, write /select z1\nMore games soon.'
  if update.message.text == '/select z1':
    z5bot = Z5Bot.instances[0]
    player =  Player.get_instance_by_username(update.message.from_user.username)
    print(player)
    player.set_story(Story(name='Zork 1', abbrev='z1', filename='zork_1-r52.z5'))
    z5bot.add_player(player)
    bot.sendMessage(update.message.chat_id, text=z5bot.receive(update.message.from_user.username))
  else:
    bot.sendMessage(update.message.chat_id, text=text)

def on_message(bot, update):
  if len(Z5Bot.instances) == 0:
    logging.debug('Creating new Z5Bot instance.')
    z5bot = Z5Bot()
  else:
    z5bot = Z5Bot.instances[0]
    logging.debug('Using existing Z5Bot instance: %r' % z5bot)

  username = update.message.from_user.username

  if Player.get_instance_by_username(username) is None:
    logging.debug('No instance of Player found, creating.')
    player = Player(username)
  else:
    player = Player.get_instance_by_username(username)

  if player.story is None:
    text = 'Please use the /select command to select a game.'
    bot.sendMessage(update.message.chat_id, text=text)
    return

  print(player.story)

  if z5bot.get_player_by_username(username) is None:
    logging.debug('Adding Player %r to the bot.' % player)
    z5bot.add_player(player)
  z5bot.process(username, update.message.text)

  received = z5bot.receive(username)
  #print(received)
  bot.sendMessage(update.message.chat_id, text=received)

def on_error(bot, update, error):
  logger = logging.getLogger(__name__)
  logger.warn('Update %r caused error %r!' % (update, error))


if __name__ == '__main__':
  with open('config.txt', 'r') as config_file:
    api_key = config_file.read().replace('\n', '')
    print('api key: ' + api_key)
    updater = telegram.Updater(api_key)
  dispatcher = updater.dispatcher

  dispatcher.addTelegramCommandHandler('start', cmd_start)
  dispatcher.addTelegramCommandHandler('select', cmd_select)
  dispatcher.addTelegramMessageHandler(on_message)
  dispatcher.addErrorHandler(on_error)
  updater.start_polling()
  updater.idle()