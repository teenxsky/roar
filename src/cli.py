import curses
import threading
import time
from collections import deque
from curses import window

from loguru import logger

from src.app import VoiceP2PChat
from src.config import config

MODE_MENU = 0
MODE_CHAT = 1


cat_10 = [
    '   -*               ',
    '   #*#+   +:        ',
    '   .*+%#**+*#=      ',
    '   =@%**#%%#%*#     ',
    '   #@%#%%@@%#+      ',
    '   %@@@@@@@+-       ',
    ' *#@@@@@@@@%=.      ',
    '@%%@@@@@@@@+        ',
    '@%#%%%@@@@%#        ',
    '@@%%%%@@@@%#        ',
]

cat_15 = [
    '                              ',
    '     ##*                      ',
    '     #*##*     +:             ',
    '     +**#*%%#***#@@*          ',
    '     *#++*%*+##+ **=++        ',
    '     #@@@#*#%#%%%%@#*#%       ',
    '     #@%##*%%%@@@@%+:=        ',
    '    -%@@%%%@%@@@%##%*         ',
    '    #%@@@@@@@@@@%--=          ',
    '  +##@@@@@@@@@@@@*:           ',
    ':%%%@@@@@@@@@@@@@@%#          ',
    '@@%%%@@@@@@@@@@@@.            ',
    '@%##%%%%@@@@@@@@%+            ',
    '@@%##%%%%@@@@@@%%#            ',
    '@@@%%%@%%@@@@@@%##            ',
]

cat_20 = [
    '       #%                               ',
    '      =##%*                             ',
    '      ##**#%-       +:                  ',
    '      =######%==#+==*#%%+.              ',
    '       #*++#*%@#******%@@#+             ',
    '       @**:**%%*+*#*+  %#*=*+.          ',
    '       @@%@@%***#%#%%#+*%%%%#%*         ',
    '       @@@%%***###%@@@%@@%%##%*         ',
    '      =%@@#%###%%%@@@@@@%**:=           ',
    '      @%@@@%%%%%%%@%%@%#%%%*            ',
    '      @%@@@@%@%@@@@@@@%-=*%             ',
    '     %%%@@@@@@@@@@@@@@#=.:              ',
    '  .*##%@@@@@@@@@@@@@@@@*-               ',
    ' *%#%@@@@@@@@@@@@@@@@@@@%#*             ',
    '%@%%%%@@@@@@@@@@@@@@@@@%#+              ',
    '@@@%%%%@@@@@@@@@@@@@@@%                 ',
    '@@%##%%@@%%@@@@@@@@@@@%=                ',
    '@@%###%%%%%@@@@@@@@@@%#*                ',
    '@@@%#%%@@%%%@@@@@@@%%%##                ',
    '@@@@@%%%@%%@@@@@@@@%%%#*                ',
]

cat_25 = [
    '                                                  ',
    '        +%##-                                     ',
    '        ###%%#            :                       ',
    '        ##*###%*         +=                       ',
    '        *%*####%%*.-**=-=+*%##+.                  ',
    '        +###+##*#%%%#*****#%@@@#+*                ',
    '         #*+=**%@@%++****#%%@@%##=+               ',
    '        .@#*++%*##*++*%#*+==-%**#=#+-:            ',
    '        #@@@%@%%*+#*#%##%%#***%%%@%#%%=           ',
    '        +@@@%@%*+**####%@@@@%@@@@#+#@@+           ',
    '        #@@@%*##++*%#%%@@@@@@@@*#+.#.             ',
    '       .%#@@@@%%%%%%%%%@@@@@@#%%###               ',
    '       +@@@@@%%%%%@@%%%@@%@@*#*@%%+               ',
    '       %@%@@@@@@@@@@@@@@@@@%%.==#+                ',
    '      +@%%@@@@@@@@@@@@@@@@@@*-.-+                 ',
    '    *###%@@@@@@@@@@@@@@@@@@@%#:                   ',
    '  *%*#%%@@@@@@@@@@@@@@@@@@@%@###.*.               ',
    ':%@%##%@@@@@@@@@@@@@@@@@@@@@@@@#%*                ',
    '%@@%#%%%@@@@@@@@@@@@@@@@@@@@@#*+                  ',
    '@@@%%%%%%@@@@@@@@@@@@@@@@@@@#                     ',
    '@@@%##%%%%@%%@@@@@@@@%%@@@@%#-                    ',
    '@@@%#*#%%@%%%%@@@@@@@@@@@@%%#*                    ',
    '@@@@@#*%%%%%%#%@@@@@@@@@@@%%##                    ',
    '@@@@%%%%@@@%%%%@@@@@@@@@%@%%##                    ',
    '@@@@@@%%%%@%%@@@@@@@@@@@%%%##*                    ',
]

cat_30 = [
    '           **.                                              ',
    '          %%##%.                                            ',
    '         -%##%%%*              =                            ',
    '         ##*#*##%%=           -+                            ',
    '         *#%*#**###%-        :==+*=-                        ',
    '          #####%%######%%*+++*#%@@@%%*#-                    ',
    '          *#**+=##+#%@%###**#**+*%@@@@*+*                   ',
    '          .#*+=++*%%@@%*+***##%%#%@@%+*+=-                  ',
    '          -@***:+#**%*++++#%#*+==--@#*%*+%+:+               ',
    '          @@@%*%%%%#**#**#%%%%##*+++%%%%%*#%@#              ',
    '          %@@@@@@@#*+*##%%#%%%%%%%%%@@%****%#%=             ',
    '          #@@@@%%#*+**#####%@@@@@%%@@@%%%#*##*              ',
    '          %@@@@####*+*%%%%%@@@@@@@@@@*+*= *.                ',
    '         %%#@@@@%%%%%%%%%%%@@@@%@@@##%*%##.                 ',
    '        .@%%@@@@%%#%%%@@%%%%%%%%@%*##@@%@+                  ',
    '        :@@%@@@@@@%%%%%@@@@@@@@@@%*-+-%@*                   ',
    '        #@%%@@@@@@@@@@@@@@@@@@@@@##::-=*                    ',
    '       +%%%%@@@@@@@@@@@@@@@@@@@@@%*: ..                     ',
    '    =####%%@@@@@@@@@@@@@@@@@@@@@@@##=                       ',
    '  :%#*#%%%@@@@@@@@@@@@@@@@@@@@@@@%@*##+-=.                  ',
    ' +%%%##%@@@@@@@@@@@@@@@@@@@@@@@@@@@@%#*%*                   ',
    '*@@@%%%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@+                    ',
    '@@@%%%%%%%@@@@@@@@@@@@@@@@@@@@@@@@#                         ',
    '@@@@%%%@%%%@@@@@@@@@@@@@@@@@@@@@@%%.                        ',
    '@@@%%##%%%%%@%%@@@@%@@@@@%%%@@@@@%#:                        ',
    '@@@@%###%%%@%%%%%@@@@@@@@@@@@@@%%%%+                        ',
    '@@@%%%%%#%%%%%%%#%@@@@@@@@@@@@@@%%#*                        ',
    '@@@@@%#%%#%@%%%%%%@@@@@@@@@@%%%%%##*                        ',
    '@@@@@%%%%%@%@@%@%%@@@@@@@@@@@@@%###*                        ',
    '@@@@@@@%@#%%@@%@@@@@@@@@@@@@@%%%%##*                        ',
]

cat_35 = [
    '            +%%#+                                                     ',
    '           .%####%:                                                   ',
    '           *###%%%%*                =                                 ',
    '           ##*#*###%%=             -+.                                ',
    '           *###***####%=          :===*+:                             ',
    '           =##**##%###%##**%%#*++++*#@@%%%#**:                        ',
    '            ####**###*#%%%#%##******##%@@@@%++%.                      ',
    '            +#*+==++#%%%@@#+***#*+++**#%@@@@%*-#                      ',
    '            =#*+*+==*##@@%#*++**####+:.-@@#+++-==                     ',
    '            *@%*++=##**%#*++++#%%##*++=-=*****-=**-=-                 ',
    '           .@@@@*#%%%%#*+*#**#%%#%%###+++*%%%%%%##%%%*                ',
    '           .@@@@@@@@@%*+*###%%##%%%%%%##%%@@@%*#**#%%#:               ',
    '            %@@@@%%%#*++**######%@@@@@@%%@@@@%%%*#%%%+                ',
    '           .@@@@@@####+++*#%%%%%@@@@@@@@@@@%+#*=:#+                   ',
    '           *%#@@@@%%%%##%@@%%%%@@@@@@@@@@@%***++ +                    ',
    '          +%%#@@@@%%%%%#%%%%%%@%@@%%%@@@##%@%%%%+                     ',
    '          +@@@@@@@%%#%@%%%@@%%%%@@@@@@@*+#*%%%%@:                     ',
    '          #@%%@@@@@@@%%%%%@@@@@@@@@@@@%%*:+=*%@-                      ',
    '         +@@%%@@@@@@@@@@@@@@@@@@@@@@@@%#*::--*+                       ',
    '        :%%%%%@@@@@@@@@@@@@@@@@@@@@@@@@#+:...:                        ',
    '     :*#####%@@@@@@@@@@@@@@@@@@@@@@@@@@%#+.                           ',
    '   .*#*###%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@%**+: .:.                     ',
    '  +%%###%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%@%#%#-*=                      ',
    ':#@@%%##%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%%%%.                      ',
    '#@@@%%#%%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@+                        ',
    '@@@@%%%%%%%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@=                             ',
    '@@@@%%%%@%%%%@@@@@@@@@@@@@@@@@@@@@@@@@@%*                             ',
    '@@@@%%%#%%%%%%@@%@@@@@%@@@@@@%%%@@@@@@%%*                             ',
    '@@@@%%####%%%%%%%%%%@%@@@@@@@@@@@@@@%%%##=                            ',
    '@@@@%%#*%%%%%%%%%%%%%@@@@@@@@@@@@@@@@%%#*+                            ',
    '@@@@@@%###%%%%%%%%%%@@@@@@@@@@@@@@@@%#%##*                            ',
    '@@@@@@%#%%%%@@@%%%%%%@@@@@@@@@@@@%%%%%###*                            ',
    '@@@@@@%%%#%%%@@@%@%%@@@@@@@@@@@@@@@@%####*                            ',
    '@@@@@@@@%@%%%%@@%%@@@@@@@@@@@@@@@@%%%%###+                            ',
]

logo = [
    '░▒▓███████▓▒░ ░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░ ',
    '░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░',
    '░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░',
    '░▒▓███████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓███████▓▒░ ',
    '░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░',
    '░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░',
    '░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░',
]


def draw_chat_box(stdscr: window, y: int, x: int, h: int, w: int):
    stdscr.addstr(y, x, '+' + '-' * (w - 2) + '+')
    for i in range(1, h - 1):
        stdscr.addstr(y + i, x, '|' + ' ' * (w - 2) + '|')
    stdscr.addstr(y + h - 1, x, '+' + '-' * (w - 2) + '+')


def draw_messages(stdscr: window, messages, y: int, x: int, h: int, w: int):
    limit = h - 2
    if limit <= 0:
        return

    visible = list(messages)[-limit:]

    for i, msg in enumerate(visible):
        stdscr.addstr(y + i, x + 1, msg[: (w - 1)])
        stdscr.addstr(y + i, x + w, '|')


def draw_input(stdscr: window, chat_input: str, y: int, x: int, w: int):
    stdscr.addstr(y, x, ' ' * w)
    stdscr.addstr(y, x, '> ' + chat_input[: w - 2])


def draw_cat(stdscr: window, h: int, w: int, cat: list[str]) -> None:
    n = len(cat)
    m = len(cat[0])
    if h < n or w < m:
        return
    for i in range(min(h, n)):
        stdscr.addstr(h - 1 - i, 0, cat[n - 1 - i])
        stdscr.addstr(i, w - m - 1, cat[n - 1 - i][::-1])


def draw_logo(stdscr: window, h: int, w: int, offset_h: int = 0, offset_w: int = 0) -> None:
    n = len(logo)
    m = len(logo[0])
    start_h = h // 2 - n // 2 + offset_h
    start_w = w // 2 - m // 2 + offset_w
    if (start_h < 0) or ((start_h + n) > h) or (start_w < 0) or ((start_w + m) > w):
        return

    for i in range(n):
        stdscr.addstr(start_h + i, start_w, logo[i])


def draw_signature(stdscr: window, h: int, w: int):
    authors = 'АВТОРЫ:'
    roma = 'РОМАН СОКОЛОВСКИЙ'
    ruslan = 'РУСЛАН КУТОРГИН'

    if len(roma) > h:
        return

    stdscr.addstr(0, 0, authors)
    stdscr.addstr(1, 0, roma)
    stdscr.addstr(2, 0, ruslan)
    stdscr.addstr(h - 1, w - 3, 'v1')


def draw_button(
    stdscr: window,
    label: str,
    h: int,
    w: int,
    focused=False,
    d: int = 12,
    offset_h: int = 0,
    offset_w: int = 0,
):
    attr = curses.A_REVERSE if focused else curses.A_NORMAL
    start_h = h // 2 - 1 + offset_h
    start_w = w // 2 - d // 2 + offset_w
    if (start_h < 0) or ((start_h + 1) > h) or (start_w < 0) or ((start_w + d) > w):
        return
    stdscr.addstr(start_h, start_w, ' ' * d, attr)
    stdscr.addstr(start_h, start_w + (d - len(label)) // 2, label, attr)


def input_text(stdscr: window, y: int, x: int, max_len: int = 20, prompt: str = '> '):
    curses.curs_set(1)
    buf = ''

    while True:
        stdscr.addstr(y, x, ' ' * (len(prompt) + max_len))
        stdscr.addstr(y, x, prompt + buf)
        stdscr.refresh()

        key = stdscr.getch()

        if key in (curses.KEY_ENTER, ord('\n')):
            break

        elif key in (27,):  # ESC
            buf = ''
            break

        elif key in (curses.KEY_BACKSPACE, 127, 8):
            buf = buf[:-1]

        elif 32 <= key <= 126 and len(buf) < max_len:
            buf += chr(key)

    curses.curs_set(0)
    return buf


def app(stdscr: window):
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    stdscr.clear()
    stdscr.refresh()

    buttons = [
        ('НАЧАТЬ', 5),
        ('ВЫЙТИ', 7),
    ]
    current = 0

    mode = MODE_MENU
    name = ''
    messages = deque(maxlen=300)

    logger.remove()
    logger.add(
        lambda m: messages.append(m),
        format=('<level>{message}</level>'),
        level=config.LOG_LEVEL,
        enqueue=True,
    )
    chat_input = ''
    chat = None

    while True:
        if chat and not chat.running:
            break

        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if h < 10:
            continue

        if mode == MODE_CHAT:
            box_h = h - 6
            box_w = w - 10
            box_y = 2
            box_x = 5

            draw_chat_box(stdscr, box_y, box_x, box_h, box_w)
            draw_messages(stdscr, messages, box_y + 1, box_x + 1, box_h - 2, box_w - 2)
            draw_input(stdscr, chat_input, box_y + box_h - 2, box_x + 1, box_w - 2)

            stdscr.refresh()
            key = stdscr.getch()

            if key in (curses.KEY_ENTER, ord('\n')):
                if chat_input.strip():
                    # Отправляем сообщение через чат
                    if chat:
                        chat.send_message(chat_input)
                    # Добавляем свое сообщение в интерфейс
                    messages.append(f'{name}: {chat_input}')
                chat_input = ''
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                chat_input = chat_input[:-1]
            elif key == 27:  # ESC
                mode = MODE_MENU
            elif 32 <= key <= 126:
                chat_input += chr(key)
            time.sleep(0.03)
            continue

        draw_logo(stdscr, h, w, -2)
        # draw_signature(stdscr, h, w)
        for i, (label, offset_h) in enumerate(buttons):
            draw_button(stdscr, label, h, w, focused=(i == current), offset_h=offset_h)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (curses.KEY_DOWN, ord('\t')):
            current = (current + 1) % len(buttons)
        elif key in (curses.KEY_UP,):
            current = (current - 1) % len(buttons)
        elif key in (curses.KEY_ENTER, ord('\n'), ord(' ')):
            label, _ = buttons[current]
            if label == 'НАЧАТЬ':
                name = input_text(
                    stdscr,
                    h // 2 + 4,
                    w // 2 - 10,
                    max_len=16,
                    prompt='ВВЕДИТЕ ИМЯ: ',
                )
                if name:
                    chat = VoiceP2PChat(name)

                    # Устанавливаем callback для получения сообщений
                    def on_message_received(username, message):
                        messages.append(f'{username}: {message}')

                    chat.set_text_message_callback(on_message_received)

                    chat_thread = threading.Thread(
                        target=chat.start,
                        daemon=True,
                    )

                    chat_thread.start()

                    stdscr.nodelay(True)

                    mode = MODE_CHAT
            elif label == 'ВЫЙТИ':
                break
        time.sleep(0.03)
