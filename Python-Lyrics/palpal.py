from __future__ import annotations

import os
import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

TITLE = "PAL PAL"
ARTIST = "Afusic × Talwiinder"
LYRICS_FILE = Path(__file__).with_name("pal_pal_lyrics.txt")
DEFAULT_SECONDS_PER_LINE = 4.25
START_DELAY = 2.0

# ANSI colours
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR = "\033[2J\033[H"
PINK = "\033[38;5;213m"
PURPLE = "\033[38;5;141m"
BLUE = "\033[38;5;117m"
GREY = "\033[38;5;245m"
WHITE = "\033[38;5;255m"

LRC_RE = re.compile(r"^\[(\d{1,2}):(\d{2}(?:\.\d+)?)\]\s*(.*)$")


@dataclass(frozen=True)
class Lyric:
    at: float
    text: str


def enable_ansi_on_windows() -> None:
    if os.name == "nt":
        os.system("")


def load_lyrics(path: Path) -> list[Lyric]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path.name}. Create it beside this script and put one lyric line per line."
        )

    raw = path.read_text(encoding="utf-8-sig").splitlines()
    nonempty = [line.strip() for line in raw if line.strip()]
    if not nonempty:
        raise ValueError(f"{path.name} is empty.")

    parsed: list[Lyric] = []
    all_timestamped = True
    for line in nonempty:
        match = LRC_RE.match(line)
        if match:
            minutes, seconds, text = match.groups()
            parsed.append(Lyric(int(minutes) * 60 + float(seconds), text.strip()))
        else:
            all_timestamped = False
            break

    if all_timestamped:
        return sorted(parsed, key=lambda item: item.at)

    # Untimed lyrics get evenly spaced subtitle timings.
    return [
        Lyric(START_DELAY + i * DEFAULT_SECONDS_PER_LINE, line)
        for i, line in enumerate(nonempty)
    ]


def visible_len(text: str) -> int:
    return len(re.sub(r"\033\[[0-9;?]*[A-Za-z]", "", text))


def centre(text: str, width: int) -> str:
    return " " * max(0, (width - visible_len(text)) // 2) + text


def wrap_centre(text: str, width: int, colour: str = WHITE) -> list[str]:
    words, rows, current = text.split(), [], ""
    max_width = max(20, width - 10)
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_width and current:
            rows.append(centre(f"{colour}{BOLD}{current}{RESET}", width))
            current = word
        else:
            current = candidate
    if current:
        rows.append(centre(f"{colour}{BOLD}{current}{RESET}", width))
    return rows or [""]


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def gradient_bar(progress: float, width: int) -> str:
    width = max(10, width)
    filled = round(max(0.0, min(1.0, progress)) * width)
    return f"{PINK}{'━' * filled}{GREY}{'─' * (width - filled)}{RESET}"


def lyric_index(lyrics: list[Lyric], elapsed: float) -> int:
    index = -1
    for i, lyric in enumerate(lyrics):
        if lyric.at <= elapsed:
            index = i
        else:
            break
    return index


def keyboard_worker(events: list[str], lock: threading.Lock) -> None:
    """Read single keys on Windows and POSIX without external modules."""
    if os.name == "nt":
        import msvcrt
        while True:
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                arrow = msvcrt.getwch()
                key = {"K": "LEFT", "M": "RIGHT"}.get(arrow, "")
            with lock:
                events.append(key)
            if key.lower() == "q":
                return
    else:
        import select
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not ready:
                    continue
                key = sys.stdin.read(1)
                if key == "\x1b":
                    key += sys.stdin.read(2)
                    key = {"\x1b[D": "LEFT", "\x1b[C": "RIGHT"}.get(key, "")
                with lock:
                    events.append(key)
                if key.lower() == "q":
                    return
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def render(lyrics: list[Lyric], elapsed: float, paused: bool) -> str:
    width, height = shutil.get_terminal_size((80, 24))
    idx = lyric_index(lyrics, elapsed)
    final_time = lyrics[-1].at + DEFAULT_SECONDS_PER_LINE
    progress = elapsed / final_time

    lines = [CLEAR]
    lines.append(centre(f"{PINK}✦  {TITLE}  ✦{RESET}", width))
    lines.append(centre(f"{PURPLE}{ITALIC}{ARTIST}{RESET}", width))
    lines.append(centre(f"{GREY}· · ───────────── · ·{RESET}", width))
    lines.extend([""] * max(1, height // 6))

    previous = lyrics[idx - 1].text if idx > 0 else ""
    current = lyrics[idx].text if idx >= 0 else "get ready…"
    following = lyrics[idx + 1].text if idx + 1 < len(lyrics) else ""

    if previous:
        lines.append(centre(f"{GREY}{previous}{RESET}", width))
    else:
        lines.append("")
    lines.append("")
    lines.extend(wrap_centre(current, width, PINK if not paused else BLUE))
    lines.append("")
    if following:
        lines.append(centre(f"{DIM}{PURPLE}{following}{RESET}", width))

    used = len(lines) + 5
    lines.extend([""] * max(1, height - used))
    bar_width = min(58, max(10, width - 22))
    state = "  PAUSED" if paused else ""
    lines.append(centre(gradient_bar(progress, bar_width), width))
    lines.append(centre(
        f"{GREY}{format_time(elapsed)}  /  {format_time(final_time)}{state}{RESET}", width
    ))
    lines.append(centre(f"{DIM}{GREY}space pause  •  ← → seek  •  q quit{RESET}", width))
    return "\n".join(lines)


def main() -> int:
    enable_ansi_on_windows()
    try:
        lyrics = load_lyrics(LYRICS_FILE)
    except (FileNotFoundError, ValueError) as error:
        print(f"\n{error}\n")
        print("Tip: timestamped LRC lines give the best synchronization.")
        return 1

    if not sys.stdin.isatty():
        print("Run this script in an interactive terminal.")
        return 1

    events: list[str] = []
    lock = threading.Lock()
    threading.Thread(target=keyboard_worker, args=(events, lock), daemon=True).start()

    elapsed = 0.0
    paused = False
    last_tick = time.monotonic()
    final_time = lyrics[-1].at + DEFAULT_SECONDS_PER_LINE

    print(HIDE_CURSOR, end="", flush=True)
    try:
        while elapsed <= final_time:
            now = time.monotonic()
            if not paused:
                elapsed += now - last_tick
            last_tick = now

            with lock:
                pending, events[:] = events[:], []
            for event in pending:
                if event == " ":
                    paused = not paused
                elif event == "LEFT":
                    elapsed = max(0.0, elapsed - 5.0)
                elif event == "RIGHT":
                    elapsed = min(final_time, elapsed + 5.0)
                elif event.lower() == "q":
                    return 0

            print(render(lyrics, elapsed, paused), end="", flush=True)
            time.sleep(1 / 20)
        time.sleep(1.0)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        print(f"{RESET}{SHOW_CURSOR}\n")


if __name__ == "__main__":
    raise SystemExit(main())
