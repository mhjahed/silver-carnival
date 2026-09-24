#!/usr/bin/env python3
from __future__ import annotations
import os, re, shutil, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "that_body_slowed.mp3"
LRC = ROOT / "that_body_synced.lrc"
TITLE, ARTIST = "ROCK THAT BODY · SLOWED", "The Black Eyed Peas"
DURATION = 288.7
C = {"reset":"\033[0m", "pink":"\033[38;5;213m", "violet":"\033[38;5;141m", "cyan":"\033[38;5;117m", "gray":"\033[38;5;242m", "white":"\033[97m", "bold":"\033[1m", "dim":"\033[2m"}
STAMP = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$")

def lyrics():
    out=[]
    for row in LRC.read_text(encoding="utf-8-sig").splitlines():
        if m:=STAMP.match(row): out.append((int(m[1])*60+float(m[2]),m[3].strip()))
    return out

def center(s,w):
    plain=re.sub(r"\033\[[0-9;]*m", "", s)
    return " "*max(0,(w-len(plain))//2)+s

def keyboard(queue, lock):
    if os.name=="nt":
        import msvcrt
        while True:
            k=msvcrt.getwch()
            if k in "\x00\xe0": k={"K":"LEFT","M":"RIGHT","H":"UP","P":"DOWN"}.get(msvcrt.getwch(),"")
            with lock: queue.append(k)
            if k.lower()=="q": return
    else:
        import select, termios, tty
        fd=sys.stdin.fileno(); old=termios.tcgetattr(fd); tty.setcbreak(fd)
        try:
            while True:
                if not select.select([sys.stdin],[],[],.1)[0]: continue
                k=sys.stdin.read(1)
                if k=="\x1b": k={"\x1b[D":"LEFT","\x1b[C":"RIGHT","\x1b[A":"UP","\x1b[B":"DOWN"}.get(k+sys.stdin.read(2),"")
                with lock: queue.append(k)
                if k.lower()=="q": return
        finally: termios.tcsetattr(fd,termios.TCSADRAIN,old)

def screen(data,pos,paused,offset):
    """Draw a clean, minimal player that still feels alive."""
    w,h=shutil.get_terminal_size((86,26)); adjusted=pos+offset; idx=-1
    for n,(at,_) in enumerate(data):
        if at<=adjusted: idx=n
        else: break

    cur=data[idx][1] if idx>=0 else "get ready"
    nxt=data[idx+1][1] if idx+1<len(data) else ""
    barw=min(54,max(24,w-24)); fill=max(0,min(barw,round(pos/DURATION*barw)))

    # A tiny animated pulse—visual movement without making the UI busy.
    pulse="▁▂▃▄▅▄▃▂"
    wave="".join(pulse[(i+int(pos*7))%len(pulse)] for i in range(9))
    state="PAUSED" if paused else wave
    now=f"{int(pos)//60:02}:{int(pos)%60:02}"
    total="04:49"

    rows=["\033[2J\033[H"]
    rows.append(center(f"{C['bold']}{C['white']}ROCK THAT BODY{C['reset']}  {C['gray']}— slowed{C['reset']}",w))
    rows.append(center(f"{C['dim']}{C['gray']}THE BLACK EYED PEAS{C['reset']}",w))
    rows += [""]*max(3,h//4)
    rows.append(center(f"{C['pink']}{C['bold']}{cur}{C['reset']}",w))
    rows.append("")
    rows.append(center(f"{C['dim']}{C['gray']}{nxt}{C['reset']}",w) if nxt else "")
    rows += [""]*max(2,h-len(rows)-7)
    rows.append(center(f"{C['violet']}{state}{C['reset']}",w))
    rows.append(center(f"{C['pink']}{'━'*fill}●{C['gray']}{'─'*(barw-fill)}{C['reset']}",w))
    rows.append(center(f"{C['gray']}{now}   {total}{C['reset']}",w))
    rows.append(center(f"{C['dim']}{C['gray']}SPACE  ·  ← →  ·  Q{C['reset']}",w))
    return "\n".join(rows)

def main():
    try: import pygame
    except ImportError:
        print("Missing pygame. Install it with:\n  python -m pip install pygame"); return 1
    if not AUDIO.exists() or not LRC.exists(): print("Keep the MP3, LRC, and script in the same folder."); return 1
    os.system("") if os.name=="nt" else None
    pygame.mixer.init(frequency=48000); pygame.mixer.music.load(str(AUDIO)); pygame.mixer.music.play()
    data=lyrics(); queue=[]; lock=threading.Lock(); threading.Thread(target=keyboard,args=(queue,lock),daemon=True).start()
    base=0.; started=time.monotonic(); paused=False; pause_at=0.; offset=0.
    print("\033[?25l",end="")
    try:
        while True:
            pos=pause_at if paused else base+(time.monotonic()-started)
            with lock: pending,queue[:]=queue[:],[]
            for k in pending:
                if k==" ":
                    if paused: pygame.mixer.music.unpause(); started=time.monotonic(); base=pause_at; paused=False
                    else: pygame.mixer.music.pause(); pause_at=pos; paused=True
                elif k in ("LEFT","RIGHT","r"):
                    target=0 if k=="r" else max(0,min(DURATION,pos+(-5 if k=="LEFT" else 5)))
                    pygame.mixer.music.play(start=target); base=target; started=time.monotonic(); pause_at=target
                    if paused: pygame.mixer.music.pause()
                elif k=="UP": offset+=.1
                elif k=="DOWN": offset-=.1
                elif k.lower()=="q": return 0
            print(screen(data,pos,paused,offset),end="",flush=True)
            if pos>=DURATION: return 0
            time.sleep(.04)
    finally: pygame.mixer.music.stop(); pygame.mixer.quit(); print(f"{C['reset']}\033[?25h\n")

if __name__=="__main__": raise SystemExit(main())
