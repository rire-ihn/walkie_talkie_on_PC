import socket
import sys
import threading

import numpy as np
import pygame
import sounddevice as sd
from pygame.locals import *

if len(sys.argv) < 2 or 3 < len(sys.argv):
    sys.stderr.write("Usage: " + sys.argv[0] + " PORT HOST(optional)\n")
    sys.exit(0)

is_server = len(sys.argv) == 2

HOST = "" if is_server else sys.argv[2]
PORT = int(sys.argv[1])

SR = 44100
DT = np.float32

BUF = 1024

WPM_MIN = 6
WPM_MAX = 48
CW_FREQ_MIN = 300
CW_FREQ_MAX = 900

SILENT, STOP, STRAIGHT, SHORT, LONG, SQUEEZE, TALK = range(7)

sd.default.samplerate = SR
sd.default.channels = 1
sd.default.dtype = DT
sd.default.latency = "high"

istream = sd.InputStream()
ostream = sd.OutputStream()

wpm = 15
cw_freq = 600

cw_state = SILENT

lastlong = False
is_connected = False


def recv_data(s):
    global is_connected
    while True:
        data = s.recv(BUF)
        if len(data) <= 0:
            s.close()
            break
        data_array = np.frombuffer(data, dtype=DT)
        if np.all(data_array == 1):
            if ostream.active:
                ostream.stop()
            continue
        if ostream.stopped:
            ostream.start()
            ostream.write(np.zeros(BUF * 4, dtype=DT))
        ostream.write(data_array)
    is_connected = False
    ostream.stop()
    ostream.close()


def daemon_server(HOST, PORT):
    global conn, addr, is_connected
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ss:
        ss.bind((HOST, PORT))
        ss.listen(1)

        conn, addr = ss.accept()
        is_connected = True

        thread = threading.Thread(target=recv_data, args=(conn,))
        thread.start()

        istream.start()

        while True:
            data, overflowed = istream.read(BUF)
            if not is_connected:
                break
            elif cw_state == TALK:
                conn.sendall(data.tobytes())

        thread.join()
        istream.stop()
        istream.close()


def daemon_client(HOST, PORT):
    global conn, is_connected
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((HOST, PORT))
    is_connected = True

    thread = threading.Thread(target=recv_data, args=(conn,))
    thread.start()

    istream.start()

    while True:
        data, overflowed = istream.read(BUF)
        if not is_connected:
            break
        elif cw_state == TALK:
            conn.sendall(data.tobytes())

    thread.join()
    istream.stop()
    istream.close()


pygame.init()
screen = pygame.display.set_mode((600, 400))
pygame.display.set_caption("EEIC-walkie-talkie")
font = pygame.font.Font(None, 55)

if is_server:
    thread = threading.Thread(target=daemon_server, daemon=True, args=(HOST, PORT))
    thread.start()
else:
    thread = threading.Thread(target=daemon_client, daemon=True, args=(HOST, PORT))
    thread.start()

while True:
    screen.fill((0, 0, 0))

    if is_server:
        text = font.render("SERVER MODE", True, (255, 255, 255))
        screen.blit(text, [20, 20])
    else:
        text = font.render("CLIENT MODE", True, (255, 255, 255))
        screen.blit(text, [20, 20])

    text = font.render(
        "WPM: " + str(wpm) + "    FREQ: " + str(cw_freq), True, (255, 255, 255)
    )
    screen.blit(text, [20, 100])

    if is_server:
        if is_connected:
            text = font.render("CONNECTED", True, (255, 255, 255))
            screen.blit(text, [20, 180])
            text = font.render("CLIENT IP: " + addr[0], True, (255, 255, 255))
            screen.blit(text, [20, 220])
        else:
            text = font.render("CONNECTION STOPPED", True, (255, 255, 255))
            screen.blit(text, [20, 180])
            text = font.render(
                "SERVER IP: " + str(socket.gethostbyname(socket.gethostname())),
                True,
                (255, 255, 255),
            )
            screen.blit(text, [20, 220])
    else:
        if is_connected:
            text = font.render("CONNECTED", True, (255, 255, 255))
            screen.blit(text, [20, 180])
            text = font.render("SERVER IP: " + HOST, True, (255, 255, 255))
            screen.blit(text, [20, 220])
        else:
            text = font.render("CONNECTION STOPPED", True, (255, 255, 255))
            screen.blit(text, [20, 180])
            text = font.render(
                "CLIENT IP: " + str(socket.gethostbyname(socket.gethostname())),
                True,
                (255, 255, 255),
            )
            screen.blit(text, [20, 220])
    text = font.render("PORT: " + str(PORT), True, (255, 255, 255))
    screen.blit(text, [20, 260])
    if cw_state == TALK:
        text = font.render("TALKING", True, (255, 255, 255))
        screen.blit(text, [20, 340])

    array_short = np.sin(
        2 * np.pi * np.arange(int(SR * 1.2 / wpm)) * cw_freq / SR, dtype=DT
    )
    array_long = np.sin(
        2 * np.pi * np.arange(int(SR * 3.6 / wpm)) * cw_freq / SR, dtype=DT
    )
    array_silent = np.zeros(int(SR * 1.2 / wpm), dtype=DT)

    for event in pygame.event.get():
        if event.type == QUIT:
            if is_connected:
                conn.shutdown(socket.SHUT_WR)
                is_connected = False
                thread.join()
            pygame.quit()
            sys.exit()
        elif event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                if is_connected:
                    conn.shutdown(socket.SHUT_WR)
                    is_connected = False
                    thread.join()
                pygame.quit()
                sys.exit()
            elif event.key == K_SPACE:
                if cw_state == SILENT and ostream.stopped or cw_state == STOP:
                    cw_state = STRAIGHT
            elif event.key == K_t:
                if cw_state == SILENT and ostream.stopped or cw_state == STOP:
                    cw_state = TALK
                    text = font.render("TALKING", True, (255, 255, 255))
                    screen.blit(text, [20, 340])
            elif event.key == K_v:
                if cw_state == LONG:
                    cw_state = SQUEEZE
                elif cw_state == SILENT and ostream.stopped or cw_state == STOP:
                    cw_state = SHORT
            elif event.key == K_b:
                if cw_state == SHORT:
                    cw_state = SQUEEZE
                elif cw_state == SILENT and ostream.stopped or cw_state == STOP:
                    cw_state = LONG
            elif event.key == K_UP:
                if wpm < WPM_MAX:
                    wpm += 1
            elif event.key == K_DOWN:
                if wpm > WPM_MIN:
                    wpm -= 1
            elif event.key == K_LEFT:
                if cw_freq > CW_FREQ_MIN:
                    cw_freq -= 20
            elif event.key == K_RIGHT:
                if cw_freq < CW_FREQ_MAX:
                    cw_freq += 20

        elif event.type == KEYUP:
            if event.key == K_SPACE:
                if cw_state == STRAIGHT:
                    cw_state = STOP
            if event.key == K_t:
                if cw_state == TALK:
                    cw_state = STOP
                    text = font.render("TALKING", True, (0, 0, 0), (0, 0, 0))
                    screen.blit(text, [20, 340])
            if event.key == K_v:
                if cw_state == SQUEEZE:
                    cw_state = LONG
                elif cw_state == SHORT:
                    cw_state = STOP
            if event.key == K_b:
                if cw_state == SQUEEZE:
                    cw_state = SHORT
                elif cw_state == LONG:
                    cw_state = STOP

    pygame.display.update()

    if cw_state == SILENT:
        pass
    elif cw_state == STOP:
        if is_connected:
            conn.sendall(np.ones(BUF, dtype=DT).tobytes())
        if ostream.active:
            ostream.stop()
        cw_state = SILENT
    elif cw_state == STRAIGHT:
        if is_connected:
            conn.sendall(array_short.tobytes())
        if ostream.stopped:
            ostream.start()
        ostream.write(array_short)
    elif cw_state == SHORT:
        arr = np.hstack([array_short, array_silent])
        if is_connected:
            conn.sendall(arr.tobytes())
        if ostream.stopped:
            ostream.start()
        ostream.write(arr)
        lastlong = False
    elif cw_state == LONG:
        arr = np.hstack([array_long, array_silent])
        if is_connected:
            conn.sendall(arr.tobytes())
        if ostream.stopped:
            ostream.start()
        ostream.write(arr)
        lastlong = True
    elif cw_state == SQUEEZE:
        if lastlong:
            arr = np.hstack([array_short, array_silent])
            if is_connected:
                conn.sendall(arr.tobytes())
            if ostream.stopped:
                ostream.start()
            ostream.write(arr)
            lastlong = False
        else:
            arr = np.hstack([array_long, array_silent])
            if is_connected:
                conn.sendall(arr.tobytes())
            if ostream.stopped:
                ostream.start()
            ostream.write(arr)
            lastlong = True
