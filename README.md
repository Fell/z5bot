# Z5Bot
A script to glue the Telegram Bot API and Frotz together.

At the time of writing, the code is really fucked up,
documentation doesn't exist and a ton of stuff is hardcoded.
But if you want to give it a try anyway...

## Installation (sigh)
Put bot.py and dfrotz.py in a directory. Additionally, create  
- stories/zork_1-r52.z5 (z5 file containing Zork I)
- tools/dfrotz (Frotz compiled in dumb-mode / see Frotz Makefile)
- config.txt (a file JUST containing your Telegram API key)

in the same folder. Install python-telegram-bot and run bot.py.

(Don't) have fun. :D