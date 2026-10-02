import discord
from discord.ext import commands
import asyncio
import random
import os
import time
import json

TOKEN = os.getenv("DISCORD_TOKEN", "PUT_YOUR_TOKEN_HERE")
PREFIX = ","
SETTINGS_FILE = "settings.json"
START_TIME = time.monotonic()

def load_lines(path):
    if not path.endswith(".txt"):
        path += ".txt"
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    except Exception as e:
        print(f"[load error {path}] {e}")
        return []

def normalize_filename(name, default):
    if not name:
        return default
    if not name.endswith(".txt"):
        name += ".txt"
    return name

DEFAULT_SETTINGS = {
    "global": {
        "case": "M",
        "format": "none",
        "format_chance": 100,
    },
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for section, values in DEFAULT_SETTINGS.items():
            if section not in data:
                data[section] = values
            else:
                for k, v in values.items():
                    if k not in data[section]:
                        data[section][k] = v
        return data
    except Exception as e:
        print(f"[settings load error] {e}")
        return json.loads(json.dumps(DEFAULT_SETTINGS))

def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"[settings save error] {e}")

settings = load_settings()

bot = commands.Bot(command_prefix=PREFIX, self_bot=True, help_command=None)

class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.states = {}

    def register(self, key, task):
        self.cancel(key)
        self.tasks[key] = task
        self.states[key] = "running"

    def cancel(self, key):
        t = self.tasks.get(key)
        if t and not t.done():
            t.cancel()
        self.tasks[key] = None
        self.states[key] = "stopped"

    def pause(self, key):
        if self.states.get(key) == "running":
            self.states[key] = "paused"
            return True
        return False

    def resume(self, key):
        if self.states.get(key) == "paused":
            self.states[key] = "running"
            return True
        return False

    def is_running(self, key):
        t = self.tasks.get(key)
        return t is not None and not t.done() and self.states.get(key) == "running"

    def is_paused(self, key):
        return self.states.get(key) == "paused"

    def status(self, key):
        return self.states.get(key, "stopped")

tm = TaskManager()

def apply_case(text, mode):
    mode = (mode or "M").upper()
    if mode == "U": return text.upper()
    if mode == "L": return text.lower()
    if mode == "M": return "".join(random.choice([c.upper(), c.lower()]) for c in text)
    return text

def apply_format(text, fmt):
    if fmt == "bold": return f"**{text}**"
    if fmt == "italic": return f"*{text}*"
    if fmt == "code": return f"`{text}`"
    if fmt == "codeblock": return f"```\n{text}\n```"
    if fmt == "header": return f"# {text}"
    if fmt == "quote": return f"> {text}"
    if fmt == "spoiler": return f"||{text}||"
    return text

def resolve_case(feature):
    override = settings.get(feature, {}).get("case", "global")
    if override == "global":
        return settings["global"]["case"]
    return override

def resolve_format(feature):
    override = settings.get(feature, {}).get("format", "global")
    if override == "global":
        return settings["global"]["format"]
    return override

def resolve_format_chance(feature):
    override = settings.get(feature, {}).get("format_chance", None)
    if override is None or override == "global":
        return settings["global"]["format_chance"]
    return override

async def safe_send(channel, content=None, **kwargs):
    try: return await channel.send(content, **kwargs)
    except Exception as e: print(f"[send fail] {e}")

async def safe_edit(channel, **kwargs):
    try: return await channel.edit(**kwargs)
    except Exception as e: print(f"[edit fail] {e}")

async def send_typing(channel):
    try: await channel.trigger_typing()
    except: pass

def cancel_all():
    for key in list(tm.tasks.keys()):
        tm.cancel(key)

def build_tag_prefix(feature):
    cfg = settings.get(feature, {})
    mode = cfg.get("tag_mode", "none")
    ids = cfg.get("tag_ids", [])
    if mode == "none" or not ids:
        return ""
    if mode == "single":
        return f"<@{ids[0]}> "
    return " ".join(f"<@{uid}>" for uid in ids) + " "

@bot.event
async def on_ready():
    print("Ryuu SelfBot")
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"Prefix: {bot.command_prefix}")
HELP_MAIN = """```
--- Ryuu SelfBot ---

`,help`           -> this menu
`,help <topic>`   -> sub-commands for a feature
`,files`          -> list .txt files

Topics:
  ab    -> autobeef
  al    -> autoladder
  ak    -> autokill
  spam  -> spam
  ap    -> autopaste
  stam  -> stam (spam w/ counter)
  ac    -> autocount
  gc    -> gcname
  kgc   -> killgc
  agc   -> antigc
  ar    -> autoreply
  rct   -> autoreact
  afk   -> afk
  aafk  -> antiafk
  alias -> aliases
  global-> global settings

Examples:
  ,help spam
  ,help ak
  ,help ap
```"""

HELP_GLOBAL = """```
--- Global Settings ---

  ,case <u/l/m>            global case
  ,format <mode>           global format
  ,formatchance <0-100>    global format chance
  ,settings                show current global settings
  ,resetglobal             reset global to defaults
```"""
@bot.command(name="help", aliases=["h", "menu"])
async def cmd_help(ctx, topic: str = None):
    if not topic:
        await safe_send(ctx.channel, HELP_MAIN)
    else:
        t = topic.lower()
        if t in ("ab", "autobeef", "beef"):
            await safe_send(ctx.channel, HELP_AB)
        elif t in ("al", "autoladder", "ladder"):
            await safe_send(ctx.channel, HELP_AL)
        elif t in ("ak", "autokill", "kill"):
            await safe_send(ctx.channel, HELP_AK)
        elif t in ("spam",):
            await safe_send(ctx.channel, HELP_SPAM)
        elif t in ("ap", "autopaste", "paste"):
            await safe_send(ctx.channel, HELP_AP)
        elif t in ("stam",):
            await safe_send(ctx.channel, HELP_STAM)
        elif t in ("ac", "autocount", "count"):
            await safe_send(ctx.channel, HELP_AC)
        elif t in ("gc", "gcname"):
            await safe_send(ctx.channel, HELP_GC)
        elif t in ("kgc", "killgc"):
            await safe_send(ctx.channel, HELP_KILLGC)
        elif t in ("agc", "antigc"):
            await safe_send(ctx.channel, HELP_ANTIGC)
        elif t in ("agck", "antigckick"):
            # Only if you pasted the antigckick block
            try:
                await safe_send(ctx.channel, HELP_AGC)
            except NameError:
                await safe_send(ctx.channel, "antigckick not installed.")
        elif t in ("ar", "autoreply", "reply"):
            await safe_send(ctx.channel, HELP_REPLY)
        elif t in ("rct", "react", "autoreact"):
            await safe_send(ctx.channel, HELP_REACT)
        elif t in ("afk",):
            await safe_send(ctx.channel, HELP_AFK)
        elif t in ("aafk", "antiafk"):
            await safe_send(ctx.channel, HELP_ANTIAFK)
        elif t in ("alias", "aliases"):
            await safe_send(ctx.channel, HELP_ALIAS)
        elif t in ("global", "settings"):
            await safe_send(ctx.channel, HELP_GLOBAL)
        else:
            await safe_send(ctx.channel, f"Unknown topic: {topic}\nTry ,help for a list.")
    try: await ctx.message.delete()
    except: pass

@bot.command(name="case")
async def cmd_case(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Global case: {settings['global']['case']}")
    mode = mode.upper()
    if mode not in ("U", "L", "M"):
        return await safe_send(ctx.channel, "Use U, L, or M.")
    settings["global"]["case"] = mode
    save_settings()
    await safe_send(ctx.channel, f"Global case set to {mode}.")

@bot.command(name="format")
async def cmd_format(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Global format: {settings['global']['format']}")
    valid = ("none", "bold", "italic", "code", "codeblock", "header", "quote", "spoiler")
    if mode.lower() not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["global"]["format"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"Global format set to {mode.lower()}.")

@bot.command(name="formatchance")
async def cmd_formatchance(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Global format chance: {settings['global']['format_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["global"]["format_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"Global format chance: {pct}%")

@bot.command(name="settings")
async def cmd_settings(ctx):
    g = settings["global"]
    msg = (
        f"```\n--- Global Settings ---\n"
        f"Case:          {g['case']}\n"
        f"Format:        {g['format']}\n"
        f"Format chance: {g['format_chance']}%\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="resetglobal")
async def cmd_resetglobal(ctx):
    settings["global"] = json.loads(json.dumps(DEFAULT_SETTINGS["global"]))
    save_settings()
    await safe_send(ctx.channel, "Global settings reset.")

@bot.command(name="files")
async def cmd_files(ctx):
    txts = sorted([f for f in os.listdir(".") if f.endswith(".txt")])
    if not txts:
        return await safe_send(ctx.channel, "No .txt files in the bot folder.")
    await safe_send(ctx.channel, "Available .txt files:\n" + "\n".join(f"- {f}" for f in txts))

# =========================================================
# AUTOBEEF
# =========================================================
DEFAULT_SETTINGS["autobeef"] = {
    "file": "autobeef.txt",
    "delay": 1.2,
    "case": "global",
    "format": "global",
    "format_chance": 100,
    "bold_chance": 0,
    "header_chance": 0,
    "tag_mode": "none",
    "tag_ids": [],
    "burst": 1,
    "burst_gap": 0.3,
    "typing_indicator": True,
    "random_order": True,
    "loop": True,
}

# Merge into loaded settings so upgrades don't wipe it
if "autobeef" not in settings:
    settings["autobeef"] = json.loads(json.dumps(DEFAULT_SETTINGS["autobeef"]))
else:
    for k, v in DEFAULT_SETTINGS["autobeef"].items():
        if k not in settings["autobeef"]:
            settings["autobeef"][k] = v
save_settings()

HELP_AB = """```
--- Autobeef Sub-Commands ---

Control:
  ,ab [channel_id]         start
  ,abstop                  stop
  ,abpause / ,abresume     pause / resume
  ,abinfo                  show current settings
  ,abreset                 reset to defaults

File:
  ,abfile <name>           change wordlist
  ,abfiles                 list .txt files

Delay:
  ,abdelay <seconds>

Formatting:
  ,abcase <u/l/m/global>
  ,abformat <mode>
  ,abformatchance <0-100>
  ,abbold <0-100>
  ,abheader <0-100>

Tagging:
  ,abtag @user             add tag target
  ,abuntag @user           remove
  ,abcleartags             clear all
  ,abtagmode <none/single/multi>

Burst:
  ,abbust <n>
  ,abbustgap <seconds>

Other:
  ,abtyping on/off
  ,abshuffle on/off
  ,abloop on/off
```"""

async def autobeef_loop(channel, key="autobeef"):
    ab = settings["autobeef"]
    if not load_lines(ab["file"]):
        await safe_send(channel, f"[autobeef] {ab['file']} is empty or missing.")
        return
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            lines = load_lines(ab["file"])
            if not lines:
                await asyncio.sleep(2)
                continue
            if ab["random_order"]:
                random.shuffle(lines)
            for raw in lines:
                while tm.is_paused(key):
                    await asyncio.sleep(0.3)
                text = apply_case(raw, resolve_case("autobeef"))
                fmt = resolve_format("autobeef")
                chance = resolve_format_chance("autobeef")
                if fmt != "none" and random.randint(1, 100) <= chance:
                    text = apply_format(text, fmt)
                bc = ab.get("bold_chance", 0)
                if bc > 0 and random.randint(1, 100) <= bc:
                    text = f"**{text}**"
                hc = ab.get("header_chance", 0)
                if hc > 0 and random.randint(1, 100) <= hc:
                    text = f"# {text}"
                text = build_tag_prefix("autobeef") + text
                if ab.get("typing_indicator", True):
                    await send_typing(channel)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                burst = max(1, int(ab.get("burst", 1)))
                for _ in range(burst):
                    await safe_send(channel, text)
                    if burst > 1:
                        await asyncio.sleep(ab.get("burst_gap", 0.3))
                await asyncio.sleep(ab.get("delay", 1.2))
            if not ab.get("loop", True):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[autobeef error] {e}")
            await asyncio.sleep(3)

@bot.command(name="ab", aliases=["autobeef"])
async def cmd_ab(ctx, channel_id: int = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,ab <channel_id>")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    tm.cancel("autobeef")
    task = asyncio.create_task(autobeef_loop(ch))
    tm.register("autobeef", task)
    await safe_send(ctx.channel, f"autobeef started in {channel_id} using {settings['autobeef']['file']}.")

@bot.command(name="abstop")
async def cmd_abstop(ctx):
    tm.cancel("autobeef")
    await safe_send(ctx.channel, "autobeef stopped.")

@bot.command(name="abpause")
async def cmd_abpause(ctx):
    if tm.pause("autobeef"):
        await safe_send(ctx.channel, "autobeef paused.")
    else:
        await safe_send(ctx.channel, "autobeef is not running.")

@bot.command(name="abresume")
async def cmd_abresume(ctx):
    if tm.resume("autobeef"):
        await safe_send(ctx.channel, "autobeef resumed.")
    else:
        await safe_send(ctx.channel, "autobeef is not paused.")

@bot.command(name="abinfo")
async def cmd_abinfo(ctx):
    ab = settings["autobeef"]
    tags = ab.get("tag_ids", [])
    tag_str = ", ".join(f"<@{u}>" for u in tags) if tags else "none"
    msg = (
        f"```\n--- Autobeef Settings ---\n"
        f"Status:        {tm.status('autobeef')}\n"
        f"File:          {ab['file']}\n"
        f"Delay:         {ab['delay']}s\n"
        f"Case:          {ab['case']}\n"
        f"Format:        {ab['format']} (chance {ab['format_chance']}%)\n"
        f"Bold chance:   {ab['bold_chance']}%\n"
        f"Header chance: {ab['header_chance']}%\n"
        f"Tag mode:      {ab['tag_mode']}\n"
        f"Tag list:      {tag_str}\n"
        f"Burst:         {ab['burst']} (gap {ab['burst_gap']}s)\n"
        f"Typing ind.:   {ab['typing_indicator']}\n"
        f"Random order:  {ab['random_order']}\n"
        f"Loop:          {ab['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="abreset")
async def cmd_abreset(ctx):
    settings["autobeef"] = json.loads(json.dumps(DEFAULT_SETTINGS["autobeef"]))
    save_settings()
    await safe_send(ctx.channel, "autobeef settings reset to defaults.")

@bot.command(name="abfile")
async def cmd_abfile(ctx, filename: str = None):
    if not filename:
        return await safe_send(ctx.channel, f"Current file: {settings['autobeef']['file']}")
    fname = normalize_filename(filename, "autobeef.txt")
    if not os.path.exists(fname):
        return await safe_send(ctx.channel, f"{fname} not found.")
    settings["autobeef"]["file"] = fname
    save_settings()
    await safe_send(ctx.channel, f"autobeef file set to {fname}.")

@bot.command(name="abfiles")
async def cmd_abfiles(ctx):
    txts = sorted([f for f in os.listdir(".") if f.endswith(".txt")])
    if not txts:
        return await safe_send(ctx.channel, "No .txt files.")
    await safe_send(ctx.channel, "Available:\n" + "\n".join(f"- {f}" for f in txts))

@bot.command(name="abdelay")
async def cmd_abdelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['autobeef']['delay']}s")
    if seconds < 0.1:
        return await safe_send(ctx.channel, "Min delay is 0.1s.")
    settings["autobeef"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"autobeef delay set to {seconds}s.")

@bot.command(name="abcase")
async def cmd_abcase(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current case: {settings['autobeef']['case']}")
    mode = mode.lower()
    if mode not in ("u", "l", "m", "global"):
        return await safe_send(ctx.channel, "Use u, l, m, or global.")
    settings["autobeef"]["case"] = mode.upper() if mode != "global" else "global"
    save_settings()
    await safe_send(ctx.channel, f"autobeef case set to {settings['autobeef']['case']}.")

@bot.command(name="abformat")
async def cmd_abformat(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current format: {settings['autobeef']['format']}")
    valid = ("none", "bold", "italic", "code", "codeblock", "header", "quote", "spoiler", "global")
    if mode.lower() not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["autobeef"]["format"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"autobeef format set to {mode.lower()}.")

@bot.command(name="abformatchance")
async def cmd_abformatchance(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current format chance: {settings['autobeef']['format_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autobeef"]["format_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autobeef format chance: {pct}%")

@bot.command(name="abbold")
async def cmd_abbold(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current bold chance: {settings['autobeef']['bold_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autobeef"]["bold_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autobeef bold chance: {pct}%")

@bot.command(name="abheader")
async def cmd_abheader(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current header chance: {settings['autobeef']['header_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autobeef"]["header_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autobeef header chance: {pct}%")

@bot.command(name="abtag")
async def cmd_abtag(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,abtag @user OR ,abtag <user_id>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    ids = settings["autobeef"]["tag_ids"]
    if uid in ids:
        return await safe_send(ctx.channel, f"<@{uid}> already in tag list.")
    ids.append(uid)
    if settings["autobeef"]["tag_mode"] == "none":
        settings["autobeef"]["tag_mode"] = "single"
    save_settings()
    await safe_send(ctx.channel, f"Added <@{uid}>. Mode: {settings['autobeef']['tag_mode']}")

@bot.command(name="abuntag")
async def cmd_abuntag(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,abuntag @user OR ,abuntag <user_id>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    ids = settings["autobeef"]["tag_ids"]
    if uid not in ids:
        return await safe_send(ctx.channel, "Not in tag list.")
    ids.remove(uid)
    if not ids:
        settings["autobeef"]["tag_mode"] = "none"
    save_settings()
    await safe_send(ctx.channel, f"Removed <@{uid}>. Remaining: {len(ids)}")

@bot.command(name="abcleartags")
async def cmd_abcleartags(ctx):
    settings["autobeef"]["tag_ids"] = []
    settings["autobeef"]["tag_mode"] = "none"
    save_settings()
    await safe_send(ctx.channel, "Tag list cleared.")

@bot.command(name="abtagmode")
async def cmd_abtagmode(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current tag mode: {settings['autobeef']['tag_mode']}")
    if mode.lower() not in ("none", "single", "multi"):
        return await safe_send(ctx.channel, "Use none, single, or multi.")
    settings["autobeef"]["tag_mode"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"Tag mode: {mode.lower()}")

@bot.command(name="abbust")
async def cmd_abbust(ctx, n: int = None):
    if n is None:
        return await safe_send(ctx.channel, f"Current burst: {settings['autobeef']['burst']}")
    if not (1 <= n <= 50):
        return await safe_send(ctx.channel, "Use 1-50.")
    settings["autobeef"]["burst"] = n
    save_settings()
    await safe_send(ctx.channel, f"Burst set to {n}.")

@bot.command(name="abbustgap")
async def cmd_abbustgap(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current burst gap: {settings['autobeef']['burst_gap']}s")
    if seconds < 0:
        return await safe_send(ctx.channel, "Must be >= 0.")
    settings["autobeef"]["burst_gap"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"Burst gap: {seconds}s")

@bot.command(name="abtyping")
async def cmd_abtyping(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Typing indicator: {settings['autobeef']['typing_indicator']}")
    val = mode.lower() == "on"
    settings["autobeef"]["typing_indicator"] = val
    save_settings()
    await safe_send(ctx.channel, f"Typing indicator: {'ON' if val else 'OFF'}")

@bot.command(name="abshuffle")
async def cmd_abshuffle(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Random order: {settings['autobeef']['random_order']}")
    val = mode.lower() == "on"
    settings["autobeef"]["random_order"] = val
    save_settings()
    await safe_send(ctx.channel, f"Random order: {'ON' if val else 'OFF'}")

@bot.command(name="abloop")
async def cmd_abloop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['autobeef']['loop']}")
    val = mode.lower() == "on"
    settings["autobeef"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")

# =========================================================
# AUTOLADDER
# =========================================================
DEFAULT_SETTINGS["autoladder"] = {
    "file": "ladder.txt",
    "delay": 1.0,
    "case": "global",
    "format": "global",
    "format_chance": 100,
    "bold_chance": 0,
    "header_chance": 0,
    "tag_mode": "none",
    "tag_ids": [],
    "burst": 1,
    "burst_gap": 0.3,
    "typing_indicator": True,
    "random_order": True,
    "loop": True,
}

if "autoladder" not in settings:
    settings["autoladder"] = json.loads(json.dumps(DEFAULT_SETTINGS["autoladder"]))
else:
    for k, v in DEFAULT_SETTINGS["autoladder"].items():
        if k not in settings["autoladder"]:
            settings["autoladder"][k] = v
save_settings()

HELP_AL = """```
--- Autoladder Sub-Commands ---

Control:
  ,al [channel_id] [@user]  start (use ,altag first or add @user here)
  ,alstop                   stop
  ,alpause / ,alresume      pause / resume
  ,alinfo                   show current settings
  ,alreset                  reset to defaults

Target:
  ,altag @user              add target
  ,aluntag @user            remove target
  ,alcleartags              clear all
  ,altagmode <none/single/multi>

File:
  ,alfile <name>            change wordlist
  ,alfiles                  list .txt files

Delay:
  ,aldelay <seconds>

Formatting:
  ,alcase <u/l/m/global>
  ,alformat <mode>
  ,alformatchance <0-100>
  ,albold <0-100>
  ,alheader <0-100>

Burst:
  ,albust <n>
  ,albustgap <seconds>

Other:
  ,altyping on/off
  ,alshuffle on/off
  ,alloop on/off
```"""

async def autoladder_loop(channel, key="autoladder"):
    al = settings["autoladder"]
    if not load_lines(al["file"]):
        await safe_send(channel, f"[autoladder] {al['file']} is empty or missing.")
        return
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            lines = load_lines(al["file"])
            if not lines:
                await asyncio.sleep(2)
                continue
            if al["random_order"]:
                random.shuffle(lines)
            for raw in lines:
                while tm.is_paused(key):
                    await asyncio.sleep(0.3)
                text = apply_case(raw, resolve_case("autoladder"))
                fmt = resolve_format("autoladder")
                chance = resolve_format_chance("autoladder")
                if fmt != "none" and random.randint(1, 100) <= chance:
                    text = apply_format(text, fmt)
                bc = al.get("bold_chance", 0)
                if bc > 0 and random.randint(1, 100) <= bc:
                    text = f"**{text}**"
                hc = al.get("header_chance", 0)
                if hc > 0 and random.randint(1, 100) <= hc:
                    text = f"# {text}"
                text = build_tag_prefix("autoladder") + text
                if al.get("typing_indicator", True):
                    await send_typing(channel)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                burst = max(1, int(al.get("burst", 1)))
                for _ in range(burst):
                    await safe_send(channel, text)
                    if burst > 1:
                        await asyncio.sleep(al.get("burst_gap", 0.3))
                await asyncio.sleep(al.get("delay", 1.0))
            if not al.get("loop", True):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[autoladder error] {e}")
            await asyncio.sleep(3)

@bot.command(name="al", aliases=["autoladder"])
async def cmd_al(ctx, channel_id: int = None, member: discord.Member = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,al <channel_id> [@user]")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    if member:
        ids = settings["autoladder"]["tag_ids"]
        if member.id not in ids:
            ids.append(member.id)
        settings["autoladder"]["tag_mode"] = "single"
        save_settings()
    tm.cancel("autoladder")
    task = asyncio.create_task(autoladder_loop(ch))
    tm.register("autoladder", task)
    await safe_send(ctx.channel, f"autoladder started in {channel_id} using {settings['autoladder']['file']}.")

@bot.command(name="alstop")
async def cmd_alstop(ctx):
    tm.cancel("autoladder")
    await safe_send(ctx.channel, "autoladder stopped.")

@bot.command(name="alpause")
async def cmd_alpause(ctx):
    if tm.pause("autoladder"):
        await safe_send(ctx.channel, "autoladder paused.")
    else:
        await safe_send(ctx.channel, "autoladder is not running.")

@bot.command(name="alresume")
async def cmd_alresume(ctx):
    if tm.resume("autoladder"):
        await safe_send(ctx.channel, "autoladder resumed.")
    else:
        await safe_send(ctx.channel, "autoladder is not paused.")

@bot.command(name="alinfo")
async def cmd_alinfo(ctx):
    al = settings["autoladder"]
    tags = al.get("tag_ids", [])
    tag_str = ", ".join(f"<@{u}>" for u in tags) if tags else "none"
    msg = (
        f"```\n--- Autoladder Settings ---\n"
        f"Status:        {tm.status('autoladder')}\n"
        f"File:          {al['file']}\n"
        f"Delay:         {al['delay']}s\n"
        f"Case:          {al['case']}\n"
        f"Format:        {al['format']} (chance {al['format_chance']}%)\n"
        f"Bold chance:   {al['bold_chance']}%\n"
        f"Header chance: {al['header_chance']}%\n"
        f"Tag mode:      {al['tag_mode']}\n"
        f"Tag list:      {tag_str}\n"
        f"Burst:         {al['burst']} (gap {al['burst_gap']}s)\n"
        f"Typing ind.:   {al['typing_indicator']}\n"
        f"Random order:  {al['random_order']}\n"
        f"Loop:          {al['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="alreset")
async def cmd_alreset(ctx):
    settings["autoladder"] = json.loads(json.dumps(DEFAULT_SETTINGS["autoladder"]))
    save_settings()
    await safe_send(ctx.channel, "autoladder settings reset to defaults.")

@bot.command(name="alfile")
async def cmd_alfile(ctx, filename: str = None):
    if not filename:
        return await safe_send(ctx.channel, f"Current file: {settings['autoladder']['file']}")
    fname = normalize_filename(filename, "ladder.txt")
    if not os.path.exists(fname):
        return await safe_send(ctx.channel, f"{fname} not found.")
    settings["autoladder"]["file"] = fname
    save_settings()
    await safe_send(ctx.channel, f"autoladder file set to {fname}.")

@bot.command(name="alfiles")
async def cmd_alfiles(ctx):
    txts = sorted([f for f in os.listdir(".") if f.endswith(".txt")])
    if not txts:
        return await safe_send(ctx.channel, "No .txt files.")
    await safe_send(ctx.channel, "Available:\n" + "\n".join(f"- {f}" for f in txts))

@bot.command(name="aldelay")
async def cmd_aldelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['autoladder']['delay']}s")
    if seconds < 0.1:
        return await safe_send(ctx.channel, "Min delay is 0.1s.")
    settings["autoladder"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"autoladder delay set to {seconds}s.")

@bot.command(name="alcase")
async def cmd_alcase(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current case: {settings['autoladder']['case']}")
    mode = mode.lower()
    if mode not in ("u", "l", "m", "global"):
        return await safe_send(ctx.channel, "Use u, l, m, or global.")
    settings["autoladder"]["case"] = mode.upper() if mode != "global" else "global"
    save_settings()
    await safe_send(ctx.channel, f"autoladder case set to {settings['autoladder']['case']}.")

@bot.command(name="alformat")
async def cmd_alformat(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current format: {settings['autoladder']['format']}")
    valid = ("none", "bold", "italic", "code", "codeblock", "header", "quote", "spoiler", "global")
    if mode.lower() not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["autoladder"]["format"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"autoladder format set to {mode.lower()}.")

@bot.command(name="alformatchance")
async def cmd_alformatchance(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current format chance: {settings['autoladder']['format_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autoladder"]["format_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autoladder format chance: {pct}%")

@bot.command(name="albold")
async def cmd_albold(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current bold chance: {settings['autoladder']['bold_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autoladder"]["bold_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autoladder bold chance: {pct}%")

@bot.command(name="alheader")
async def cmd_alheader(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current header chance: {settings['autoladder']['header_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autoladder"]["header_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autoladder header chance: {pct}%")

@bot.command(name="altag")
async def cmd_altag(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,altag @user OR ,altag <user_id>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    ids = settings["autoladder"]["tag_ids"]
    if uid in ids:
        return await safe_send(ctx.channel, f"<@{uid}> already in tag list.")
    ids.append(uid)
    if settings["autoladder"]["tag_mode"] == "none":
        settings["autoladder"]["tag_mode"] = "single"
    save_settings()
    await safe_send(ctx.channel, f"Added <@{uid}>. Mode: {settings['autoladder']['tag_mode']}")

@bot.command(name="aluntag")
async def cmd_aluntag(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,aluntag @user OR ,aluntag <user_id>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    ids = settings["autoladder"]["tag_ids"]
    if uid not in ids:
        return await safe_send(ctx.channel, "Not in tag list.")
    ids.remove(uid)
    if not ids:
        settings["autoladder"]["tag_mode"] = "none"
    save_settings()
    await safe_send(ctx.channel, f"Removed <@{uid}>. Remaining: {len(ids)}")

@bot.command(name="alcleartags")
async def cmd_alcleartags(ctx):
    settings["autoladder"]["tag_ids"] = []
    settings["autoladder"]["tag_mode"] = "none"
    save_settings()
    await safe_send(ctx.channel, "Tag list cleared.")

@bot.command(name="altagmode")
async def cmd_altagmode(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current tag mode: {settings['autoladder']['tag_mode']}")
    if mode.lower() not in ("none", "single", "multi"):
        return await safe_send(ctx.channel, "Use none, single, or multi.")
    settings["autoladder"]["tag_mode"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"Tag mode: {mode.lower()}")

@bot.command(name="albust")
async def cmd_albust(ctx, n: int = None):
    if n is None:
        return await safe_send(ctx.channel, f"Current burst: {settings['autoladder']['burst']}")
    if not (1 <= n <= 50):
        return await safe_send(ctx.channel, "Use 1-50.")
    settings["autoladder"]["burst"] = n
    save_settings()
    await safe_send(ctx.channel, f"Burst set to {n}.")

@bot.command(name="albustgap")
async def cmd_albustgap(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current burst gap: {settings['autoladder']['burst_gap']}s")
    if seconds < 0:
        return await safe_send(ctx.channel, "Must be >= 0.")
    settings["autoladder"]["burst_gap"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"Burst gap: {seconds}s")

@bot.command(name="altyping")
async def cmd_altyping(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Typing indicator: {settings['autoladder']['typing_indicator']}")
    val = mode.lower() == "on"
    settings["autoladder"]["typing_indicator"] = val
    save_settings()
    await safe_send(ctx.channel, f"Typing indicator: {'ON' if val else 'OFF'}")

@bot.command(name="alshuffle")
async def cmd_alshuffle(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Random order: {settings['autoladder']['random_order']}")
    val = mode.lower() == "on"
    settings["autoladder"]["random_order"] = val
    save_settings()
    await safe_send(ctx.channel, f"Random order: {'ON' if val else 'OFF'}")

@bot.command(name="alloop")
async def cmd_alloop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['autoladder']['loop']}")
    val = mode.lower() == "on"
    settings["autoladder"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")

# =========================================================
# AUTOKILL
# =========================================================
DEFAULT_SETTINGS["autokill"] = {
    "file": "kill.txt",
    "delay": 0.5,
    "case": "global",
    "format": "global",
    "format_chance": 100,
    "bold_chance": 0,
    "header_chance": 0,
    "tag_mode": "none",
    "tag_ids": [],
    "burst": 1,
    "burst_gap": 0.3,
    "typing_indicator": False,
    "random_order": True,
    "loop": True,
}

if "autokill" not in settings:
    settings["autokill"] = json.loads(json.dumps(DEFAULT_SETTINGS["autokill"]))
else:
    for k, v in DEFAULT_SETTINGS["autokill"].items():
        if k not in settings["autokill"]:
            settings["autokill"][k] = v
save_settings()

HELP_AK = """```
--- Autokill Sub-Commands ---

Control:
  ,ak [channel_id] [@user]  start
  ,akstop                   stop
  ,akpause / ,akresume      pause / resume
  ,akinfo                   show current settings
  ,akreset                  reset to defaults

Target:
  ,aktag @user              add target
  ,akuntag @user            remove target
  ,akcleartags              clear all
  ,aktagmode <none/single/multi>

File:
  ,akfile <name>            change wordlist
  ,akfiles                  list .txt files

Delay:
  ,akdelay <seconds>

Formatting:
  ,akcase <u/l/m/global>
  ,akformat <mode>
  ,akformatchance <0-100>
  ,akbold <0-100>
  ,akheader <0-100>

Burst:
  ,akburst <n>
  ,akburstgap <seconds>

Other:
  ,aktyping on/off
  ,akshuffle on/off
  ,akloop on/off
```"""

async def autokill_loop(channel, key="autokill"):
    ak = settings["autokill"]
    if not load_lines(ak["file"]):
        await safe_send(channel, f"[autokill] {ak['file']} is empty or missing.")
        return
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            lines = load_lines(ak["file"])
            if not lines:
                await asyncio.sleep(2)
                continue
            if ak["random_order"]:
                random.shuffle(lines)
            for raw in lines:
                while tm.is_paused(key):
                    await asyncio.sleep(0.3)
                text = apply_case(raw, resolve_case("autokill"))
                fmt = resolve_format("autokill")
                chance = resolve_format_chance("autokill")
                if fmt != "none" and random.randint(1, 100) <= chance:
                    text = apply_format(text, fmt)
                bc = ak.get("bold_chance", 0)
                if bc > 0 and random.randint(1, 100) <= bc:
                    text = f"**{text}**"
                hc = ak.get("header_chance", 0)
                if hc > 0 and random.randint(1, 100) <= hc:
                    text = f"# {text}"
                text = build_tag_prefix("autokill") + text
                if ak.get("typing_indicator", False):
                    await send_typing(channel)
                    await asyncio.sleep(random.uniform(0.2, 0.6))
                burst = max(1, int(ak.get("burst", 1)))
                for _ in range(burst):
                    await safe_send(channel, text)
                    if burst > 1:
                        await asyncio.sleep(ak.get("burst_gap", 0.3))
                await asyncio.sleep(ak.get("delay", 0.5))
            if not ak.get("loop", True):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[autokill error] {e}")
            await asyncio.sleep(3)

@bot.command(name="ak", aliases=["autokill"])
async def cmd_ak(ctx, channel_id: int = None, member: discord.Member = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,ak <channel_id> [@user]")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    if member:
        ids = settings["autokill"]["tag_ids"]
        if member.id not in ids:
            ids.append(member.id)
        settings["autokill"]["tag_mode"] = "single"
        save_settings()
    tm.cancel("autokill")
    task = asyncio.create_task(autokill_loop(ch))
    tm.register("autokill", task)
    await safe_send(ctx.channel, f"autokill started in {channel_id} using {settings['autokill']['file']}.")

@bot.command(name="akstop")
async def cmd_akstop(ctx):
    tm.cancel("autokill")
    await safe_send(ctx.channel, "autokill stopped.")

@bot.command(name="akpause")
async def cmd_akpause(ctx):
    if tm.pause("autokill"):
        await safe_send(ctx.channel, "autokill paused.")
    else:
        await safe_send(ctx.channel, "autokill is not running.")

@bot.command(name="akresume")
async def cmd_akresume(ctx):
    if tm.resume("autokill"):
        await safe_send(ctx.channel, "autokill resumed.")
    else:
        await safe_send(ctx.channel, "autokill is not paused.")

@bot.command(name="akinfo")
async def cmd_akinfo(ctx):
    ak = settings["autokill"]
    tags = ak.get("tag_ids", [])
    tag_str = ", ".join(f"<@{u}>" for u in tags) if tags else "none"
    msg = (
        f"```\n--- Autokill Settings ---\n"
        f"Status:        {tm.status('autokill')}\n"
        f"File:          {ak['file']}\n"
        f"Delay:         {ak['delay']}s\n"
        f"Case:          {ak['case']}\n"
        f"Format:        {ak['format']} (chance {ak['format_chance']}%)\n"
        f"Bold chance:   {ak['bold_chance']}%\n"
        f"Header chance: {ak['header_chance']}%\n"
        f"Tag mode:      {ak['tag_mode']}\n"
        f"Tag list:      {tag_str}\n"
        f"Burst:         {ak['burst']} (gap {ak['burst_gap']}s)\n"
        f"Typing ind.:   {ak['typing_indicator']}\n"
        f"Random order:  {ak['random_order']}\n"
        f"Loop:          {ak['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="akreset")
async def cmd_akreset(ctx):
    settings["autokill"] = json.loads(json.dumps(DEFAULT_SETTINGS["autokill"]))
    save_settings()
    await safe_send(ctx.channel, "autokill settings reset to defaults.")

@bot.command(name="akfile")
async def cmd_akfile(ctx, filename: str = None):
    if not filename:
        return await safe_send(ctx.channel, f"Current file: {settings['autokill']['file']}")
    fname = normalize_filename(filename, "kill.txt")
    if not os.path.exists(fname):
        return await safe_send(ctx.channel, f"{fname} not found.")
    settings["autokill"]["file"] = fname
    save_settings()
    await safe_send(ctx.channel, f"autokill file set to {fname}.")

@bot.command(name="akfiles")
async def cmd_akfiles(ctx):
    txts = sorted([f for f in os.listdir(".") if f.endswith(".txt")])
    if not txts:
        return await safe_send(ctx.channel, "No .txt files.")
    await safe_send(ctx.channel, "Available:\n" + "\n".join(f"- {f}" for f in txts))

@bot.command(name="akdelay")
async def cmd_akdelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['autokill']['delay']}s")
    if seconds < 0.1:
        return await safe_send(ctx.channel, "Min delay is 0.1s.")
    settings["autokill"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"autokill delay set to {seconds}s.")

@bot.command(name="akcase")
async def cmd_akcase(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current case: {settings['autokill']['case']}")
    mode = mode.lower()
    if mode not in ("u", "l", "m", "global"):
        return await safe_send(ctx.channel, "Use u, l, m, or global.")
    settings["autokill"]["case"] = mode.upper() if mode != "global" else "global"
    save_settings()
    await safe_send(ctx.channel, f"autokill case set to {settings['autokill']['case']}.")

@bot.command(name="akformat")
async def cmd_akformat(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current format: {settings['autokill']['format']}")
    valid = ("none", "bold", "italic", "code", "codeblock", "header", "quote", "spoiler", "global")
    if mode.lower() not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["autokill"]["format"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"autokill format set to {mode.lower()}.")

@bot.command(name="akformatchance")
async def cmd_akformatchance(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current format chance: {settings['autokill']['format_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autokill"]["format_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autokill format chance: {pct}%")

@bot.command(name="akbold")
async def cmd_akbold(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current bold chance: {settings['autokill']['bold_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autokill"]["bold_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autokill bold chance: {pct}%")

@bot.command(name="akheader")
async def cmd_akheader(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current header chance: {settings['autokill']['header_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autokill"]["header_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autokill header chance: {pct}%")

@bot.command(name="aktag")
async def cmd_aktag(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,aktag @user OR ,aktag <user_id>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    ids = settings["autokill"]["tag_ids"]
    if uid in ids:
        return await safe_send(ctx.channel, f"<@{uid}> already in tag list.")
    ids.append(uid)
    if settings["autokill"]["tag_mode"] == "none":
        settings["autokill"]["tag_mode"] = "single"
    save_settings()
    await safe_send(ctx.channel, f"Added <@{uid}>. Mode: {settings['autokill']['tag_mode']}")

@bot.command(name="akuntag")
async def cmd_akuntag(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,akuntag @user OR ,akuntag <user_id>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    ids = settings["autokill"]["tag_ids"]
    if uid not in ids:
        return await safe_send(ctx.channel, "Not in tag list.")
    ids.remove(uid)
    if not ids:
        settings["autokill"]["tag_mode"] = "none"
    save_settings()
    await safe_send(ctx.channel, f"Removed <@{uid}>. Remaining: {len(ids)}")

@bot.command(name="akcleartags")
async def cmd_akcleartags(ctx):
    settings["autokill"]["tag_ids"] = []
    settings["autokill"]["tag_mode"] = "none"
    save_settings()
    await safe_send(ctx.channel, "Tag list cleared.")

@bot.command(name="aktagmode")
async def cmd_aktagmode(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current tag mode: {settings['autokill']['tag_mode']}")
    if mode.lower() not in ("none", "single", "multi"):
        return await safe_send(ctx.channel, "Use none, single, or multi.")
    settings["autokill"]["tag_mode"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"Tag mode: {mode.lower()}")

@bot.command(name="akburst")
async def cmd_akburst(ctx, n: int = None):
    if n is None:
        return await safe_send(ctx.channel, f"Current burst: {settings['autokill']['burst']}")
    if not (1 <= n <= 50):
        return await safe_send(ctx.channel, "Use 1-50.")
    settings["autokill"]["burst"] = n
    save_settings()
    await safe_send(ctx.channel, f"Burst set to {n}.")

@bot.command(name="akburstgap")
async def cmd_akburstgap(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current burst gap: {settings['autokill']['burst_gap']}s")
    if seconds < 0:
        return await safe_send(ctx.channel, "Must be >= 0.")
    settings["autokill"]["burst_gap"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"Burst gap: {seconds}s")

@bot.command(name="aktyping")
async def cmd_aktyping(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Typing indicator: {settings['autokill']['typing_indicator']}")
    val = mode.lower() == "on"
    settings["autokill"]["typing_indicator"] = val
    save_settings()
    await safe_send(ctx.channel, f"Typing indicator: {'ON' if val else 'OFF'}")

@bot.command(name="akshuffle")
async def cmd_akshuffle(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Random order: {settings['autokill']['random_order']}")
    val = mode.lower() == "on"
    settings["autokill"]["random_order"] = val
    save_settings()
    await safe_send(ctx.channel, f"Random order: {'ON' if val else 'OFF'}")

@bot.command(name="akloop")
async def cmd_akloop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['autokill']['loop']}")
    val = mode.lower() == "on"
    settings["autokill"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")

# =========================================================
# SPAM
# =========================================================
DEFAULT_SETTINGS["spam"] = {
    "message": "spam message here",
    "delay": 0.7,
    "case": "global",
    "format": "global",
    "format_chance": 100,
    "bold_chance": 0,
    "header_chance": 0,
    "typing_indicator": False,
    "burst": 1,
    "burst_gap": 0.3,
    "loop": True,
}

if "spam" not in settings:
    settings["spam"] = json.loads(json.dumps(DEFAULT_SETTINGS["spam"]))
else:
    for k, v in DEFAULT_SETTINGS["spam"].items():
        if k not in settings["spam"]:
            settings["spam"][k] = v
save_settings()

HELP_SPAM = """```
--- Spam Sub-Commands ---

Control:
  ,spam [channel_id]       start (uses saved message)
  ,spamstop                stop
  ,spampause / ,spamresume pause / resume
  ,spaminfo                show current settings
  ,spamreset               reset to defaults

Message:
  ,spammsg <text>          set the message to spam
  ,spamshow                show current spam message

Delay:
  ,spamdelay <seconds>

Formatting:
  ,spamcase <u/l/m/global>
  ,spamformat <mode>
  ,spamformatchance <0-100>
  ,spambold <0-100>
  ,spamheader <0-100>

Burst:
  ,spamburst <n>
  ,spamburstgap <seconds>

Other:
  ,spamtyping on/off
  ,spamloop on/off
```"""

async def spam_loop(channel, key="spam"):
    sp = settings["spam"]
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            raw = sp.get("message", "")
            if not raw:
                await asyncio.sleep(2)
                continue
            text = apply_case(raw, resolve_case("spam"))
            fmt = resolve_format("spam")
            chance = resolve_format_chance("spam")
            if fmt != "none" and random.randint(1, 100) <= chance:
                text = apply_format(text, fmt)
            bc = sp.get("bold_chance", 0)
            if bc > 0 and random.randint(1, 100) <= bc:
                text = f"**{text}**"
            hc = sp.get("header_chance", 0)
            if hc > 0 and random.randint(1, 100) <= hc:
                text = f"# {text}"
            if sp.get("typing_indicator", False):
                await send_typing(channel)
                await asyncio.sleep(random.uniform(0.2, 0.5))
            burst = max(1, int(sp.get("burst", 1)))
            for _ in range(burst):
                await safe_send(channel, text)
                if burst > 1:
                    await asyncio.sleep(sp.get("burst_gap", 0.3))
            await asyncio.sleep(sp.get("delay", 0.7))
            if not sp.get("loop", True):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[spam error] {e}")
            await asyncio.sleep(3)

@bot.command(name="spam")
async def cmd_spam(ctx, channel_id: int = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,spam <channel_id>")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    tm.cancel("spam")
    task = asyncio.create_task(spam_loop(ch))
    tm.register("spam", task)
    await safe_send(ctx.channel, f"spam started in {channel_id}.")

@bot.command(name="spamstop")
async def cmd_spamstop(ctx):
    tm.cancel("spam")
    await safe_send(ctx.channel, "spam stopped.")

@bot.command(name="spampause")
async def cmd_spampause(ctx):
    if tm.pause("spam"):
        await safe_send(ctx.channel, "spam paused.")
    else:
        await safe_send(ctx.channel, "spam is not running.")

@bot.command(name="spamresume")
async def cmd_spamresume(ctx):
    if tm.resume("spam"):
        await safe_send(ctx.channel, "spam resumed.")
    else:
        await safe_send(ctx.channel, "spam is not paused.")

@bot.command(name="spaminfo")
async def cmd_spaminfo(ctx):
    sp = settings["spam"]
    msg = (
        f"```\n--- Spam Settings ---\n"
        f"Status:        {tm.status('spam')}\n"
        f"Message:       {sp['message']}\n"
        f"Delay:         {sp['delay']}s\n"
        f"Case:          {sp['case']}\n"
        f"Format:        {sp['format']} (chance {sp['format_chance']}%)\n"
        f"Bold chance:   {sp['bold_chance']}%\n"
        f"Header chance: {sp['header_chance']}%\n"
        f"Burst:         {sp['burst']} (gap {sp['burst_gap']}s)\n"
        f"Typing ind.:   {sp['typing_indicator']}\n"
        f"Loop:          {sp['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="spamreset")
async def cmd_spamreset(ctx):
    settings["spam"] = json.loads(json.dumps(DEFAULT_SETTINGS["spam"]))
    save_settings()
    await safe_send(ctx.channel, "spam settings reset to defaults.")

@bot.command(name="spammsg")
async def cmd_spammsg(ctx, *, text: str = None):
    if not text:
        return await safe_send(ctx.channel, "Usage: ,spammsg <text>")
    settings["spam"]["message"] = text
    save_settings()
    await safe_send(ctx.channel, f"spam message set to: {text}")

@bot.command(name="spamshow")
async def cmd_spamshow(ctx):
    await safe_send(ctx.channel, f"Current spam message: {settings['spam']['message']}")

@bot.command(name="spamdelay")
async def cmd_spamdelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['spam']['delay']}s")
    if seconds < 0.1:
        return await safe_send(ctx.channel, "Min delay is 0.1s.")
    settings["spam"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"spam delay set to {seconds}s.")

@bot.command(name="spamcase")
async def cmd_spamcase(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current case: {settings['spam']['case']}")
    mode = mode.lower()
    if mode not in ("u", "l", "m", "global"):
        return await safe_send(ctx.channel, "Use u, l, m, or global.")
    settings["spam"]["case"] = mode.upper() if mode != "global" else "global"
    save_settings()
    await safe_send(ctx.channel, f"spam case set to {settings['spam']['case']}.")

@bot.command(name="spamformat")
async def cmd_spamformat(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current format: {settings['spam']['format']}")
    valid = ("none", "bold", "italic", "code", "codeblock", "header", "quote", "spoiler", "global")
    if mode.lower() not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["spam"]["format"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"spam format set to {mode.lower()}.")

@bot.command(name="spamformatchance")
async def cmd_spamformatchance(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current format chance: {settings['spam']['format_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["spam"]["format_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"spam format chance: {pct}%")

@bot.command(name="spambold")
async def cmd_spambold(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current bold chance: {settings['spam']['bold_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["spam"]["bold_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"spam bold chance: {pct}%")

@bot.command(name="spamheader")
async def cmd_spamheader(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current header chance: {settings['spam']['header_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["spam"]["header_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"spam header chance: {pct}%")

@bot.command(name="spamburst")
async def cmd_spamburst(ctx, n: int = None):
    if n is None:
        return await safe_send(ctx.channel, f"Current burst: {settings['spam']['burst']}")
    if not (1 <= n <= 50):
        return await safe_send(ctx.channel, "Use 1-50.")
    settings["spam"]["burst"] = n
    save_settings()
    await safe_send(ctx.channel, f"Burst set to {n}.")

@bot.command(name="spamburstgap")
async def cmd_spamburstgap(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current burst gap: {settings['spam']['burst_gap']}s")
    if seconds < 0:
        return await safe_send(ctx.channel, "Must be >= 0.")
    settings["spam"]["burst_gap"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"Burst gap: {seconds}s")

@bot.command(name="spamtyping")
async def cmd_spamtyping(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Typing indicator: {settings['spam']['typing_indicator']}")
    val = mode.lower() == "on"
    settings["spam"]["typing_indicator"] = val
    save_settings()
    await safe_send(ctx.channel, f"Typing indicator: {'ON' if val else 'OFF'}")

@bot.command(name="spamloop")
async def cmd_spamloop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['spam']['loop']}")
    val = mode.lower() == "on"
    settings["spam"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")

# =========================================================
# AUTOPASTE
# =========================================================
DEFAULT_SETTINGS["autopaste"] = {
    "message": "paste message here",
    "delay": 1.2,
    "case": "global",
    "format": "global",
    "format_chance": 100,
    "bold_chance": 0,
    "header_chance": 0,
    "typing_indicator": False,
    "burst": 1,
    "burst_gap": 0.3,
    "loop": True,
}

if "autopaste" not in settings:
    settings["autopaste"] = json.loads(json.dumps(DEFAULT_SETTINGS["autopaste"]))
else:
    for k, v in DEFAULT_SETTINGS["autopaste"].items():
        if k not in settings["autopaste"]:
            settings["autopaste"][k] = v
save_settings()

HELP_AP = """```
--- Autopaste Sub-Commands ---

Control:
  ,ap [channel_id]         start (uses saved message)
  ,apstop                  stop
  ,appause / ,apresume     pause / resume
  ,apinfo                  show current settings
  ,apreset                 reset to defaults

Message:
  ,apmsg <text>            set the message to paste
  ,apshow                  show current paste message

Delay:
  ,apdelay <seconds>

Formatting:
  ,apcase <u/l/m/global>
  ,apformat <mode>
  ,apformatchance <0-100>
  ,apbold <0-100>
  ,apheader <0-100>

Burst:
  ,apburst <n>
  ,apburstgap <seconds>

Other:
  ,aptyping on/off
  ,aploop on/off
```"""

async def autopaste_loop(channel, key="autopaste"):
    ap = settings["autopaste"]
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            raw = ap.get("message", "")
            if not raw:
                await asyncio.sleep(2)
                continue
            text = apply_case(raw, resolve_case("autopaste"))
            fmt = resolve_format("autopaste")
            chance = resolve_format_chance("autopaste")
            if fmt != "none" and random.randint(1, 100) <= chance:
                text = apply_format(text, fmt)
            bc = ap.get("bold_chance", 0)
            if bc > 0 and random.randint(1, 100) <= bc:
                text = f"**{text}**"
            hc = ap.get("header_chance", 0)
            if hc > 0 and random.randint(1, 100) <= hc:
                text = f"# {text}"
            if ap.get("typing_indicator", False):
                await send_typing(channel)
                await asyncio.sleep(random.uniform(0.2, 0.5))
            burst = max(1, int(ap.get("burst", 1)))
            for _ in range(burst):
                await safe_send(channel, text)
                if burst > 1:
                    await asyncio.sleep(ap.get("burst_gap", 0.3))
            await asyncio.sleep(ap.get("delay", 1.2))
            if not ap.get("loop", True):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[autopaste error] {e}")
            await asyncio.sleep(3)

@bot.command(name="ap", aliases=["autopaste"])
async def cmd_ap(ctx, channel_id: int = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,ap <channel_id>")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    tm.cancel("autopaste")
    task = asyncio.create_task(autopaste_loop(ch))
    tm.register("autopaste", task)
    await safe_send(ctx.channel, f"autopaste started in {channel_id}.")

@bot.command(name="apstop")
async def cmd_apstop(ctx):
    tm.cancel("autopaste")
    await safe_send(ctx.channel, "autopaste stopped.")

@bot.command(name="appause")
async def cmd_appause(ctx):
    if tm.pause("autopaste"):
        await safe_send(ctx.channel, "autopaste paused.")
    else:
        await safe_send(ctx.channel, "autopaste is not running.")

@bot.command(name="apresume")
async def cmd_apresume(ctx):
    if tm.resume("autopaste"):
        await safe_send(ctx.channel, "autopaste resumed.")
    else:
        await safe_send(ctx.channel, "autopaste is not paused.")

@bot.command(name="apinfo")
async def cmd_apinfo(ctx):
    ap = settings["autopaste"]
    msg = (
        f"```\n--- Autopaste Settings ---\n"
        f"Status:        {tm.status('autopaste')}\n"
        f"Message:       {ap['message']}\n"
        f"Delay:         {ap['delay']}s\n"
        f"Case:          {ap['case']}\n"
        f"Format:        {ap['format']} (chance {ap['format_chance']}%)\n"
        f"Bold chance:   {ap['bold_chance']}%\n"
        f"Header chance: {ap['header_chance']}%\n"
        f"Burst:         {ap['burst']} (gap {ap['burst_gap']}s)\n"
        f"Typing ind.:   {ap['typing_indicator']}\n"
        f"Loop:          {ap['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="apreset")
async def cmd_apreset(ctx):
    settings["autopaste"] = json.loads(json.dumps(DEFAULT_SETTINGS["autopaste"]))
    save_settings()
    await safe_send(ctx.channel, "autopaste settings reset to defaults.")

@bot.command(name="apmsg")
async def cmd_apmsg(ctx, *, text: str = None):
    if not text:
        return await safe_send(ctx.channel, "Usage: ,apmsg <text>")
    settings["autopaste"]["message"] = text
    save_settings()
    await safe_send(ctx.channel, f"autopaste message set to: {text}")

@bot.command(name="apshow")
async def cmd_apshow(ctx):
    await safe_send(ctx.channel, f"Current autopaste message: {settings['autopaste']['message']}")

@bot.command(name="apdelay")
async def cmd_apdelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['autopaste']['delay']}s")
    if seconds < 0.1:
        return await safe_send(ctx.channel, "Min delay is 0.1s.")
    settings["autopaste"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"autopaste delay set to {seconds}s.")

@bot.command(name="apcase")
async def cmd_apcase(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current case: {settings['autopaste']['case']}")
    mode = mode.lower()
    if mode not in ("u", "l", "m", "global"):
        return await safe_send(ctx.channel, "Use u, l, m, or global.")
    settings["autopaste"]["case"] = mode.upper() if mode != "global" else "global"
    save_settings()
    await safe_send(ctx.channel, f"autopaste case set to {settings['autopaste']['case']}.")

@bot.command(name="apformat")
async def cmd_apformat(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current format: {settings['autopaste']['format']}")
    valid = ("none", "bold", "italic", "code", "codeblock", "header", "quote", "spoiler", "global")
    if mode.lower() not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["autopaste"]["format"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"autopaste format set to {mode.lower()}.")

@bot.command(name="apformatchance")
async def cmd_apformatchance(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current format chance: {settings['autopaste']['format_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autopaste"]["format_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autopaste format chance: {pct}%")

@bot.command(name="apbold")
async def cmd_apbold(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current bold chance: {settings['autopaste']['bold_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autopaste"]["bold_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autopaste bold chance: {pct}%")

@bot.command(name="apheader")
async def cmd_apheader(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current header chance: {settings['autopaste']['header_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autopaste"]["header_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autopaste header chance: {pct}%")

@bot.command(name="apburst")
async def cmd_apburst(ctx, n: int = None):
    if n is None:
        return await safe_send(ctx.channel, f"Current burst: {settings['autopaste']['burst']}")
    if not (1 <= n <= 50):
        return await safe_send(ctx.channel, "Use 1-50.")
    settings["autopaste"]["burst"] = n
    save_settings()
    await safe_send(ctx.channel, f"Burst set to {n}.")

@bot.command(name="apburstgap")
async def cmd_apburstgap(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current burst gap: {settings['autopaste']['burst_gap']}s")
    if seconds < 0:
        return await safe_send(ctx.channel, "Must be >= 0.")
    settings["autopaste"]["burst_gap"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"Burst gap: {seconds}s")

@bot.command(name="aptyping")
async def cmd_aptyping(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Typing indicator: {settings['autopaste']['typing_indicator']}")
    val = mode.lower() == "on"
    settings["autopaste"]["typing_indicator"] = val
    save_settings()
    await safe_send(ctx.channel, f"Typing indicator: {'ON' if val else 'OFF'}")

@bot.command(name="aploop")
async def cmd_aploop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['autopaste']['loop']}")
    val = mode.lower() == "on"
    settings["autopaste"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")
# =========================================================
# STAM (spam with auto-incrementing counter)
# =========================================================
DEFAULT_SETTINGS["stam"] = {
    "message": "stam message here",
    "delay": 1.5,
    "case": "global",
    "format": "global",
    "format_chance": 100,
    "bold_chance": 0,
    "header_chance": 0,
    "typing_indicator": False,
    "counter_style": "parens",
    "start_at": 1,
    "loop": True,
}

if "stam" not in settings:
    settings["stam"] = json.loads(json.dumps(DEFAULT_SETTINGS["stam"]))
else:
    for k, v in DEFAULT_SETTINGS["stam"].items():
        if k not in settings["stam"]:
            settings["stam"][k] = v
save_settings()

HELP_STAM = """```
--- Stam Sub-Commands ---

Control:
  ,stam [channel_id]       start (uses saved message)
  ,stamstop                stop
  ,stampause / ,stamresume pause / resume
  ,staminfo                show current settings
  ,stamreset               reset to defaults

Message:
  ,stammsg <text>          set the message
  ,stamshow                show current message

Counter:
  ,stamstart <n>           starting number (default 1)
  ,stamstyle <style>       parens / bracket / dash / colon / none
  ,stamloop on/off         reset to start number when looped

Delay:
  ,stamdelay <seconds>

Formatting:
  ,stamcase <u/l/m/global>
  ,stamformat <mode>
  ,stamformatchance <0-100>
  ,stambold <0-100>
  ,stamheader <0-100>

Other:
  ,stamtyping on/off
```"""

def apply_counter_style(n, style):
    if style == "parens":  return f" ({n})"
    if style == "bracket": return f" [{n}]"
    if style == "dash":    return f" - {n}"
    if style == "colon":   return f": {n}"
    if style == "none":    return ""
    return f" ({n})"

async def stam_loop(channel, key="stam"):
    st = settings["stam"]
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            raw = st.get("message", "")
            if not raw:
                await asyncio.sleep(2)
                continue
            text = apply_case(raw, resolve_case("stam"))
            text += apply_counter_style(st.get("counter", st.get("start_at", 1)), st.get("counter_style", "parens"))
            fmt = resolve_format("stam")
            chance = resolve_format_chance("stam")
            if fmt != "none" and random.randint(1, 100) <= chance:
                text = apply_format(text, fmt)
            bc = st.get("bold_chance", 0)
            if bc > 0 and random.randint(1, 100) <= bc:
                text = f"**{text}**"
            hc = st.get("header_chance", 0)
            if hc > 0 and random.randint(1, 100) <= hc:
                text = f"# {text}"
            if st.get("typing_indicator", False):
                await send_typing(channel)
                await asyncio.sleep(random.uniform(0.2, 0.5))
            await safe_send(channel, text)
            st["counter"] = st.get("counter", st.get("start_at", 1)) + 1
            save_settings()
            await asyncio.sleep(st.get("delay", 1.5))
            if not st.get("loop", True):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[stam error] {e}")
            await asyncio.sleep(3)

@bot.command(name="stam")
async def cmd_stam(ctx, channel_id: int = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,stam <channel_id>")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    settings["stam"]["counter"] = settings["stam"].get("start_at", 1)
    save_settings()
    tm.cancel("stam")
    task = asyncio.create_task(stam_loop(ch))
    tm.register("stam", task)
    await safe_send(ctx.channel, f"stam started in {channel_id} at counter {settings['stam']['counter']}.")

@bot.command(name="stamstop")
async def cmd_stamstop(ctx):
    tm.cancel("stam")
    await safe_send(ctx.channel, "stam stopped.")

@bot.command(name="stampause")
async def cmd_stampause(ctx):
    if tm.pause("stam"):
        await safe_send(ctx.channel, "stam paused.")
    else:
        await safe_send(ctx.channel, "stam is not running.")

@bot.command(name="stamresume")
async def cmd_stamresume(ctx):
    if tm.resume("stam"):
        await safe_send(ctx.channel, "stam resumed.")
    else:
        await safe_send(ctx.channel, "stam is not paused.")

@bot.command(name="staminfo")
async def cmd_staminfo(ctx):
    st = settings["stam"]
    current = st.get("counter", st.get("start_at", 1))
    msg = (
        f"```\n--- Stam Settings ---\n"
        f"Status:        {tm.status('stam')}\n"
        f"Message:       {st['message']}\n"
        f"Current num:   {current}\n"
        f"Start number:  {st.get('start_at', 1)}\n"
        f"Style:         {st.get('counter_style', 'parens')}\n"
        f"Delay:         {st['delay']}s\n"
        f"Case:          {st['case']}\n"
        f"Format:        {st['format']} (chance {st['format_chance']}%)\n"
        f"Bold chance:   {st['bold_chance']}%\n"
        f"Header chance: {st['header_chance']}%\n"
        f"Typing ind.:   {st['typing_indicator']}\n"
        f"Loop:          {st['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="stamreset")
async def cmd_stamreset(ctx):
    settings["stam"] = json.loads(json.dumps(DEFAULT_SETTINGS["stam"]))
    save_settings()
    await safe_send(ctx.channel, "stam settings reset to defaults.")

@bot.command(name="stammsg")
async def cmd_stammsg(ctx, *, text: str = None):
    if not text:
        return await safe_send(ctx.channel, "Usage: ,stammsg <text>")
    settings["stam"]["message"] = text
    save_settings()
    await safe_send(ctx.channel, f"stam message set to: {text}")

@bot.command(name="stamshow")
async def cmd_stamshow(ctx):
    await safe_send(ctx.channel, f"Current stam message: {settings['stam']['message']}")

@bot.command(name="stamstart")
async def cmd_stamstart(ctx, n: int = None):
    if n is None:
        return await safe_send(ctx.channel, f"Current start number: {settings['stam'].get('start_at', 1)}")
    if n < 0:
        return await safe_send(ctx.channel, "Must be >= 0.")
    settings["stam"]["start_at"] = n
    settings["stam"]["counter"] = n
    save_settings()
    await safe_send(ctx.channel, f"stam start number set to {n}.")

@bot.command(name="stamstyle")
async def cmd_stamstyle(ctx, style: str = None):
    if style is None:
        return await safe_send(ctx.channel, f"Current counter style: {settings['stam'].get('counter_style', 'parens')}")
    style = style.lower()
    valid = ("parens", "bracket", "dash", "colon", "none")
    if style not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["stam"]["counter_style"] = style
    save_settings()
    await safe_send(ctx.channel, f"Counter style: {style}")

@bot.command(name="stamdelay")
async def cmd_stamdelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['stam']['delay']}s")
    if seconds < 0.1:
        return await safe_send(ctx.channel, "Min delay is 0.1s.")
    settings["stam"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"stam delay set to {seconds}s.")

@bot.command(name="stamcase")
async def cmd_stamcase(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current case: {settings['stam']['case']}")
    mode = mode.lower()
    if mode not in ("u", "l", "m", "global"):
        return await safe_send(ctx.channel, "Use u, l, m, or global.")
    settings["stam"]["case"] = mode.upper() if mode != "global" else "global"
    save_settings()
    await safe_send(ctx.channel, f"stam case set to {settings['stam']['case']}.")

@bot.command(name="stamformat")
async def cmd_stamformat(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current format: {settings['stam']['format']}")
    valid = ("none", "bold", "italic", "code", "codeblock", "header", "quote", "spoiler", "global")
    if mode.lower() not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["stam"]["format"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"stam format set to {mode.lower()}.")

@bot.command(name="stamformatchance")
async def cmd_stamformatchance(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current format chance: {settings['stam']['format_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["stam"]["format_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"stam format chance: {pct}%")

@bot.command(name="stambold")
async def cmd_stambold(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current bold chance: {settings['stam']['bold_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["stam"]["bold_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"stam bold chance: {pct}%")

@bot.command(name="stamheader")
async def cmd_stamheader(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current header chance: {settings['stam']['header_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["stam"]["header_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"stam header chance: {pct}%")

@bot.command(name="stamtyping")
async def cmd_stamtyping(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Typing indicator: {settings['stam']['typing_indicator']}")
    val = mode.lower() == "on"
    settings["stam"]["typing_indicator"] = val
    save_settings()
    await safe_send(ctx.channel, f"Typing indicator: {'ON' if val else 'OFF'}")

@bot.command(name="stamloop")
async def cmd_stamloop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['stam']['loop']}")
    val = mode.lower() == "on"
    settings["stam"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")

# =========================================================
# AUTOCOUNT (count 1 → N in a channel)
# =========================================================
DEFAULT_SETTINGS["autocount"] = {
    "start_at": 1,
    "end_at": 10,
    "delay": 1.5,
    "prefix": "",
    "suffix": "",
    "case": "global",
    "format": "global",
    "format_chance": 100,
    "bold_chance": 0,
    "header_chance": 0,
    "typing_indicator": False,
    "loop": False,
}

if "autocount" not in settings:
    settings["autocount"] = json.loads(json.dumps(DEFAULT_SETTINGS["autocount"]))
else:
    for k, v in DEFAULT_SETTINGS["autocount"].items():
        if k not in settings["autocount"]:
            settings["autocount"][k] = v
save_settings()

HELP_AC = """```
--- Autocount Sub-Commands ---

Control:
  ,ac [channel_id]         start (uses saved start/end)
  ,acstop                  stop
  ,acpause / ,acresume     pause / resume
  ,acinfo                  show current settings
  ,acreset                 reset to defaults

Range:
  ,acstart <n>             set start number
  ,acend <n>               set end number

Text:
  ,acprefix <text>         prefix each number (e.g. "count: ")
  ,acsuffix <text>         suffix each number (e.g. "!")

Delay:
  ,acdelay <seconds>

Formatting:
  ,accase <u/l/m/global>
  ,acformat <mode>
  ,acformatchance <0-100>
  ,acbold <0-100>
  ,acheader <0-100>

Other:
  ,actyping on/off
  ,acloop on/off           restart from start when hitting end
```"""

async def autocount_loop(channel, key="autocount"):
    ac = settings["autocount"]
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            start = int(ac.get("start_at", 1))
            end = int(ac.get("end_at", 10))
            step = 1 if end >= start else -1
            for n in range(start, end + step, step):
                while tm.is_paused(key):
                    await asyncio.sleep(0.3)
                text = f"{ac.get('prefix', '')}{n}{ac.get('suffix', '')}"
                text = apply_case(text, resolve_case("autocount"))
                fmt = resolve_format("autocount")
                chance = resolve_format_chance("autocount")
                if fmt != "none" and random.randint(1, 100) <= chance:
                    text = apply_format(text, fmt)
                bc = ac.get("bold_chance", 0)
                if bc > 0 and random.randint(1, 100) <= bc:
                    text = f"**{text}**"
                hc = ac.get("header_chance", 0)
                if hc > 0 and random.randint(1, 100) <= hc:
                    text = f"# {text}"
                if ac.get("typing_indicator", False):
                    await send_typing(channel)
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                await safe_send(channel, text)
                await asyncio.sleep(ac.get("delay", 1.5))
            if not ac.get("loop", False):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[autocount error] {e}")
            await asyncio.sleep(3)

@bot.command(name="ac", aliases=["autocount"])
async def cmd_ac(ctx, channel_id: int = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,ac <channel_id>")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    tm.cancel("autocount")
    task = asyncio.create_task(autocount_loop(ch))
    tm.register("autocount", task)
    await safe_send(ctx.channel, f"autocount started in {channel_id} ({settings['autocount']['start_at']} → {settings['autocount']['end_at']}).")

@bot.command(name="acstop")
async def cmd_acstop(ctx):
    tm.cancel("autocount")
    await safe_send(ctx.channel, "autocount stopped.")

@bot.command(name="acpause")
async def cmd_acpause(ctx):
    if tm.pause("autocount"):
        await safe_send(ctx.channel, "autocount paused.")
    else:
        await safe_send(ctx.channel, "autocount is not running.")

@bot.command(name="acresume")
async def cmd_acresume(ctx):
    if tm.resume("autocount"):
        await safe_send(ctx.channel, "autocount resumed.")
    else:
        await safe_send(ctx.channel, "autocount is not paused.")

@bot.command(name="acinfo")
async def cmd_acinfo(ctx):
    ac = settings["autocount"]
    msg = (
        f"```\n--- Autocount Settings ---\n"
        f"Status:        {tm.status('autocount')}\n"
        f"Start:         {ac['start_at']}\n"
        f"End:           {ac['end_at']}\n"
        f"Prefix:        {ac['prefix']}\n"
        f"Suffix:        {ac['suffix']}\n"
        f"Delay:         {ac['delay']}s\n"
        f"Case:          {ac['case']}\n"
        f"Format:        {ac['format']} (chance {ac['format_chance']}%)\n"
        f"Bold chance:   {ac['bold_chance']}%\n"
        f"Header chance: {ac['header_chance']}%\n"
        f"Typing ind.:   {ac['typing_indicator']}\n"
        f"Loop:          {ac['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="acreset")
async def cmd_acreset(ctx):
    settings["autocount"] = json.loads(json.dumps(DEFAULT_SETTINGS["autocount"]))
    save_settings()
    await safe_send(ctx.channel, "autocount settings reset to defaults.")

@bot.command(name="acstart")
async def cmd_acstart(ctx, n: int = None):
    if n is None:
        return await safe_send(ctx.channel, f"Current start: {settings['autocount']['start_at']}")
    settings["autocount"]["start_at"] = n
    save_settings()
    await safe_send(ctx.channel, f"autocount start set to {n}.")

@bot.command(name="acend")
async def cmd_acend(ctx, n: int = None):
    if n is None:
        return await safe_send(ctx.channel, f"Current end: {settings['autocount']['end_at']}")
    settings["autocount"]["end_at"] = n
    save_settings()
    await safe_send(ctx.channel, f"autocount end set to {n}.")

@bot.command(name="acprefix")
async def cmd_acprefix(ctx, *, text: str = None):
    if text is None:
        return await safe_send(ctx.channel, f"Current prefix: {settings['autocount']['prefix']!r}")
    settings["autocount"]["prefix"] = text
    save_settings()
    await safe_send(ctx.channel, f"autocount prefix set to: {text!r}")

@bot.command(name="acsuffix")
async def cmd_acsuffix(ctx, *, text: str = None):
    if text is None:
        return await safe_send(ctx.channel, f"Current suffix: {settings['autocount']['suffix']!r}")
    settings["autocount"]["suffix"] = text
    save_settings()
    await safe_send(ctx.channel, f"autocount suffix set to: {text!r}")

@bot.command(name="acdelay")
async def cmd_acdelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['autocount']['delay']}s")
    if seconds < 0.1:
        return await safe_send(ctx.channel, "Min delay is 0.1s.")
    settings["autocount"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"autocount delay set to {seconds}s.")

@bot.command(name="accase")
async def cmd_accase(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current case: {settings['autocount']['case']}")
    mode = mode.lower()
    if mode not in ("u", "l", "m", "global"):
        return await safe_send(ctx.channel, "Use u, l, m, or global.")
    settings["autocount"]["case"] = mode.upper() if mode != "global" else "global"
    save_settings()
    await safe_send(ctx.channel, f"autocount case set to {settings['autocount']['case']}.")

@bot.command(name="acformat")
async def cmd_acformat(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current format: {settings['autocount']['format']}")
    valid = ("none", "bold", "italic", "code", "codeblock", "header", "quote", "spoiler", "global")
    if mode.lower() not in valid:
        return await safe_send(ctx.channel, f"Valid: {', '.join(valid)}")
    settings["autocount"]["format"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"autocount format set to {mode.lower()}.")

@bot.command(name="acformatchance")
async def cmd_acformatchance(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current format chance: {settings['autocount']['format_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autocount"]["format_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autocount format chance: {pct}%")

@bot.command(name="acbold")
async def cmd_acbold(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current bold chance: {settings['autocount']['bold_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autocount"]["bold_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autocount bold chance: {pct}%")

@bot.command(name="acheader")
async def cmd_acheader(ctx, pct: int = None):
    if pct is None:
        return await safe_send(ctx.channel, f"Current header chance: {settings['autocount']['header_chance']}%")
    if not (0 <= pct <= 100):
        return await safe_send(ctx.channel, "Use 0-100.")
    settings["autocount"]["header_chance"] = pct
    save_settings()
    await safe_send(ctx.channel, f"autocount header chance: {pct}%")

@bot.command(name="actyping")
async def cmd_actyping(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Typing indicator: {settings['autocount']['typing_indicator']}")
    val = mode.lower() == "on"
    settings["autocount"]["typing_indicator"] = val
    save_settings()
    await safe_send(ctx.channel, f"Typing indicator: {'ON' if val else 'OFF'}")

@bot.command(name="acloop")
async def cmd_acloop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['autocount']['loop']}")
    val = mode.lower() == "on"
    settings["autocount"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")


# =========================================================
# GCNAME (rotate group chat names)
# =========================================================
DEFAULT_SETTINGS["gcname"] = {
    "file": "gcname.txt",
    "delay": 2.0,
    "random_order": True,
    "loop": True,
}

if "gcname" not in settings:
    settings["gcname"] = json.loads(json.dumps(DEFAULT_SETTINGS["gcname"]))
else:
    for k, v in DEFAULT_SETTINGS["gcname"].items():
        if k not in settings["gcname"]:
            settings["gcname"][k] = v
save_settings()

HELP_GC = """```
--- Gcname Sub-Commands ---

Control:
  ,gcname [channel_id]     start rotating GC name
  ,gcnamestop              stop
  ,gcnamepause / ,gcnameresume
  ,gcnameinfo              show current settings
  ,gcnamereset             reset to defaults

File:
  ,gcnamefile <name>       change the names file
  ,gcnamefiles             list .txt files

Delay:
  ,gcnamedelay <seconds>

Other:
  ,gcnameshuffle on/off    random order
  ,gcnameloop on/off       restart file when exhausted
```"""

async def gcname_loop(channel, key="gcname"):
    gc = settings["gcname"]
    if not load_lines(gc["file"]):
        await safe_send(channel, f"[gcname] {gc['file']} is empty or missing.")
        return
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            names = load_lines(gc["file"])
            if not names:
                await asyncio.sleep(2)
                continue
            if gc.get("random_order", True):
                random.shuffle(names)
            for name in names:
                while tm.is_paused(key):
                    await asyncio.sleep(0.3)
                await safe_edit(channel, name=name)
                await asyncio.sleep(gc.get("delay", 2.0))
            if not gc.get("loop", True):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[gcname error] {e}")
            await asyncio.sleep(3)

@bot.command(name="gcname")
async def cmd_gcname(ctx, channel_id: int = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,gcname <channel_id>")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    if not isinstance(ch, discord.GroupChannel):
        return await safe_send(ctx.channel, "Not a group channel.")
    tm.cancel("gcname")
    task = asyncio.create_task(gcname_loop(ch))
    tm.register("gcname", task)
    await safe_send(ctx.channel, f"gcname started in {channel_id} using {settings['gcname']['file']}.")

@bot.command(name="gcnamestop")
async def cmd_gcnamestop(ctx):
    tm.cancel("gcname")
    await safe_send(ctx.channel, "gcname stopped.")

@bot.command(name="gcnamepause")
async def cmd_gcnamepause(ctx):
    if tm.pause("gcname"):
        await safe_send(ctx.channel, "gcname paused.")
    else:
        await safe_send(ctx.channel, "gcname is not running.")

@bot.command(name="gcnameresume")
async def cmd_gcnameresume(ctx):
    if tm.resume("gcname"):
        await safe_send(ctx.channel, "gcname resumed.")
    else:
        await safe_send(ctx.channel, "gcname is not paused.")

@bot.command(name="gcnameinfo")
async def cmd_gcnameinfo(ctx):
    gc = settings["gcname"]
    msg = (
        f"```\n--- Gcname Settings ---\n"
        f"Status:        {tm.status('gcname')}\n"
        f"File:          {gc['file']}\n"
        f"Delay:         {gc['delay']}s\n"
        f"Random order:  {gc['random_order']}\n"
        f"Loop:          {gc['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="gcnamereset")
async def cmd_gcnamereset(ctx):
    settings["gcname"] = json.loads(json.dumps(DEFAULT_SETTINGS["gcname"]))
    save_settings()
    await safe_send(ctx.channel, "gcname settings reset.")

@bot.command(name="gcnamefile")
async def cmd_gcnamefile(ctx, filename: str = None):
    if not filename:
        return await safe_send(ctx.channel, f"Current file: {settings['gcname']['file']}")
    fname = normalize_filename(filename, "gcname.txt")
    if not os.path.exists(fname):
        return await safe_send(ctx.channel, f"{fname} not found.")
    settings["gcname"]["file"] = fname
    save_settings()
    await safe_send(ctx.channel, f"gcname file set to {fname}.")

@bot.command(name="gcnamefiles")
async def cmd_gcnamefiles(ctx):
    txts = sorted([f for f in os.listdir(".") if f.endswith(".txt")])
    if not txts:
        return await safe_send(ctx.channel, "No .txt files.")
    await safe_send(ctx.channel, "Available:\n" + "\n".join(f"- {f}" for f in txts))

@bot.command(name="gcnamedelay")
async def cmd_gcnamedelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['gcname']['delay']}s")
    if seconds < 0.5:
        return await safe_send(ctx.channel, "Min delay is 0.5s (Discord rate limits rename).")
    settings["gcname"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"gcname delay set to {seconds}s.")

@bot.command(name="gcnameshuffle")
async def cmd_gcnameshuffle(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Random order: {settings['gcname']['random_order']}")
    val = mode.lower() == "on"
    settings["gcname"]["random_order"] = val
    save_settings()
    await safe_send(ctx.channel, f"Random order: {'ON' if val else 'OFF'}")

@bot.command(name="gcnameloop")
async def cmd_gcnameloop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['gcname']['loop']}")
    val = mode.lower() == "on"
    settings["gcname"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")

# =========================================================
# KILLGC (rapid-fire rename a group chat)
# =========================================================
DEFAULT_SETTINGS["killgc"] = {
    "file": "gcname.txt",
    "delay": 1.0,
    "random_order": True,
    "loop": True,
}

if "killgc" not in settings:
    settings["killgc"] = json.loads(json.dumps(DEFAULT_SETTINGS["killgc"]))
else:
    for k, v in DEFAULT_SETTINGS["killgc"].items():
        if k not in settings["killgc"]:
            settings["killgc"][k] = v
save_settings()

HELP_KILLGC = """```
--- Killgc Sub-Commands ---

Control:
  ,killgc [channel_id]     start
  ,killgcstop              stop
  ,killgcpause / ,killgcresume
  ,killgcinfo              show current settings
  ,killgcreset             reset to defaults

File:
  ,killgcfile <name>       change the names file
  ,killgcfiles             list .txt files

Delay:
  ,killgcdelay <seconds>

Other:
  ,killgcshuffle on/off
  ,killgcloop on/off
```"""

async def killgc_loop(channel, key="killgc"):
    kg = settings["killgc"]
    if not load_lines(kg["file"]):
        await safe_send(channel, f"[killgc] {kg['file']} is empty or missing.")
        return
    while True:
        try:
            if tm.is_paused(key):
                await asyncio.sleep(0.5)
                continue
            names = load_lines(kg["file"])
            if not names:
                await asyncio.sleep(2)
                continue
            if kg.get("random_order", True):
                random.shuffle(names)
            for name in names:
                while tm.is_paused(key):
                    await asyncio.sleep(0.3)
                await safe_edit(channel, name=name)
                await asyncio.sleep(kg.get("delay", 1.0))
            if not kg.get("loop", True):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[killgc error] {e}")
            await asyncio.sleep(3)

@bot.command(name="killgc")
async def cmd_killgc(ctx, channel_id: int = None):
    if not channel_id:
        return await safe_send(ctx.channel, "Usage: ,killgc <channel_id>")
    ch = bot.get_channel(channel_id)
    if not ch:
        return await safe_send(ctx.channel, "Channel not found.")
    if not isinstance(ch, discord.GroupChannel):
        return await safe_send(ctx.channel, "Not a group channel.")
    tm.cancel("killgc")
    task = asyncio.create_task(killgc_loop(ch))
    tm.register("killgc", task)
    await safe_send(ctx.channel, f"killgc started in {channel_id} using {settings['killgc']['file']}.")

@bot.command(name="killgcstop")
async def cmd_killgcstop(ctx):
    tm.cancel("killgc")
    await safe_send(ctx.channel, "killgc stopped.")

@bot.command(name="killgcpause")
async def cmd_killgcpause(ctx):
    if tm.pause("killgc"):
        await safe_send(ctx.channel, "killgc paused.")
    else:
        await safe_send(ctx.channel, "killgc is not running.")

@bot.command(name="killgcresume")
async def cmd_killgcresume(ctx):
    if tm.resume("killgc"):
        await safe_send(ctx.channel, "killgc resumed.")
    else:
        await safe_send(ctx.channel, "killgc is not paused.")

@bot.command(name="killgcinfo")
async def cmd_killgcinfo(ctx):
    kg = settings["killgc"]
    msg = (
        f"```\n--- Killgc Settings ---\n"
        f"Status:        {tm.status('killgc')}\n"
        f"File:          {kg['file']}\n"
        f"Delay:         {kg['delay']}s\n"
        f"Random order:  {kg['random_order']}\n"
        f"Loop:          {kg['loop']}\n```"
    )
    await safe_send(ctx.channel, msg)

@bot.command(name="killgcreset")
async def cmd_killgcreset(ctx):
    settings["killgc"] = json.loads(json.dumps(DEFAULT_SETTINGS["killgc"]))
    save_settings()
    await safe_send(ctx.channel, "killgc settings reset.")

@bot.command(name="killgcfile")
async def cmd_killgcfile(ctx, filename: str = None):
    if not filename:
        return await safe_send(ctx.channel, f"Current file: {settings['killgc']['file']}")
    fname = normalize_filename(filename, "gcname.txt")
    if not os.path.exists(fname):
        return await safe_send(ctx.channel, f"{fname} not found.")
    settings["killgc"]["file"] = fname
    save_settings()
    await safe_send(ctx.channel, f"killgc file set to {fname}.")

@bot.command(name="killgcfiles")
async def cmd_killgcfiles(ctx):
    txts = sorted([f for f in os.listdir(".") if f.endswith(".txt")])
    if not txts:
        return await safe_send(ctx.channel, "No .txt files.")
    await safe_send(ctx.channel, "Available:\n" + "\n".join(f"- {f}" for f in txts))

@bot.command(name="killgcdelay")
async def cmd_killgcdelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['killgc']['delay']}s")
    if seconds < 0.5:
        return await safe_send(ctx.channel, "Min delay is 0.5s (Discord rate limits rename).")
    settings["killgc"]["delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"killgc delay set to {seconds}s.")

@bot.command(name="killgcshuffle")
async def cmd_killgcshuffle(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Random order: {settings['killgc']['random_order']}")
    val = mode.lower() == "on"
    settings["killgc"]["random_order"] = val
    save_settings()
    await safe_send(ctx.channel, f"Random order: {'ON' if val else 'OFF'}")

@bot.command(name="killgcloop")
async def cmd_killgcloop(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Loop: {settings['killgc']['loop']}")
    val = mode.lower() == "on"
    settings["killgc"]["loop"] = val
    save_settings()
    await safe_send(ctx.channel, f"Loop: {'ON' if val else 'OFF'}")

# =========================================================
# ANTIGC (auto-leave new group chats, optional message + rename)
# =========================================================
DEFAULT_SETTINGS["antigc"] = {
    "enabled": False,
    "message": "",
    "rename_to": "",
    "leave_delay": 1.2,
    "whitelist": [],
    "blacklist": [],
}

if "antigc" not in settings:
    settings["antigc"] = json.loads(json.dumps(DEFAULT_SETTINGS["antigc"]))
else:
    for k, v in DEFAULT_SETTINGS["antigc"].items():
        if k not in settings["antigc"]:
            settings["antigc"][k] = v
save_settings()

HELP_ANTIGC = """```
--- Antigc Sub-Commands ---

  ,antigc on               enable auto-leave
  ,antigc off              disable
  ,antigc status           show status
  ,antigc info             show all settings

Message:
  ,antigcmsg <text>        message sent before leaving (empty = none)
  ,antigcmsgclear          clear the message

Rename:
  ,antigcrename <name>     rename GC before leaving (empty = none)
  ,antigcrenameclear       clear the rename

Delay:
  ,antigcdelay <seconds>   delay between message and leave

Whitelist (users you NEVER want to trigger auto-leave):
  ,antigcwl @user          add user to whitelist
  ,antigcwlun @user        remove
  ,antigcwllist            show whitelist
  ,antigcwlclear           clear whitelist

Blacklist (users who ALWAYS trigger auto-leave):
  ,antigcbl @user          add user to blacklist
  ,antigcblun @user        remove
  ,antigcbllist            show blacklist
  ,antigcblclear           clear blacklist

  ,antigcreset             reset to defaults
```"""

async def antigc_handle(channel):
    ac = settings["antigc"]
    try:
        # Rename first if set
        if ac.get("rename_to"):
            try:
                await channel.edit(name=ac["rename_to"])
                await asyncio.sleep(ac.get("leave_delay", 1.2))
            except Exception as e:
                print(f"[antigc rename] {e}")

        # Send message if set
        if ac.get("message"):
            try:
                await channel.send(ac["message"])
                await asyncio.sleep(ac.get("leave_delay", 1.2))
            except Exception as e:
                print(f"[antigc msg] {e}")

        # Leave
        await channel.leave()
        print(f"[antigc] Left GC {channel.id}")

    except Exception as e:
        print(f"[antigc handle] {e}")

def antigc_should_leave(channel):
    """Check whitelist / blacklist and decide."""
    ac = settings["antigc"]
    recipients = getattr(channel, "recipients", []) or []
    recipient_ids = {u.id for u in recipients}
    if u_self_id in recipient_ids:
        recipient_ids.discard(u_self_id)

    whitelist = set(ac.get("whitelist", []))
    blacklist = set(ac.get("blacklist", []))

    # If anyone in blacklist is here → leave
    if blacklist & recipient_ids:
        return True

    # If everyone is whitelisted → don't leave
    if recipient_ids and recipient_ids.issubset(whitelist):
        return False

    # If any non-whitelisted user is here → leave
    if whitelist:
        # Some are whitelisted, some aren't
        non_whitelisted = recipient_ids - whitelist
        if non_whitelisted:
            return True
        return False

    # No rules → default leave
    return True

u_self_id = None

@bot.event
async def on_ready_antigc_hook():
    global u_self_id
    if bot.user:
        u_self_id = bot.user.id
        print(f"[antigc] hooked self id = {u_self_id}")

# Attach hook after bot is ready
@bot.event
async def on_private_channel_create(channel):
    if not settings["antigc"].get("enabled"):
        return
    if not isinstance(channel, discord.GroupChannel):
        return
    global u_self_id
    if u_self_id is None and bot.user:
        u_self_id = bot.user.id
    if antigc_should_leave(channel):
        await antigc_handle(channel)

@bot.command(name="antigc")
async def cmd_antigc(ctx, mode: str = None):
    ac = settings["antigc"]
    if mode is None or mode.lower() == "status":
        state = "ON" if ac.get("enabled") else "OFF"
        return await safe_send(ctx.channel, f"antigc: {state}")
    m = mode.lower()
    if m == "on":
        ac["enabled"] = True
        save_settings()
        await safe_send(ctx.channel, "antigc ON.")
    elif m == "off":
        ac["enabled"] = False
        save_settings()
        await safe_send(ctx.channel, "antigc OFF.")
    elif m == "info":
        wl = ac.get("whitelist", [])
        bl = ac.get("blacklist", [])
        wl_str = ", ".join(f"<@{u}>" for u in wl) if wl else "none"
        bl_str = ", ".join(f"<@{u}>" for u in bl) if bl else "none"
        msg = (
            f"```\n--- Antigc Settings ---\n"
            f"Enabled:     {ac.get('enabled')}\n"
            f"Message:     {ac.get('message') or '(none)'}\n"
            f"Rename to:   {ac.get('rename_to') or '(none)'}\n"
            f"Leave delay: {ac.get('leave_delay')}s\n"
            f"Whitelist:   {wl_str}\n"
            f"Blacklist:   {bl_str}\n```"
        )
        await safe_send(ctx.channel, msg)
    else:
        await safe_send(ctx.channel, "Use: ,antigc on | off | status | info")

@bot.command(name="antigcmsg")
async def cmd_antigcmsg(ctx, *, text: str = None):
    if text is None:
        return await safe_send(ctx.channel, f"Current message: {settings['antigc'].get('message') or '(none)'}")
    settings["antigc"]["message"] = text
    save_settings()
    await safe_send(ctx.channel, f"antigc message set to: {text}")

@bot.command(name="antigcmsgclear")
async def cmd_antigcmsgclear(ctx):
    settings["antigc"]["message"] = ""
    save_settings()
    await safe_send(ctx.channel, "antigc message cleared.")

@bot.command(name="antigcrename")
async def cmd_antigcrename(ctx, *, name: str = None):
    if name is None:
        return await safe_send(ctx.channel, f"Current rename: {settings['antigc'].get('rename_to') or '(none)'}")
    settings["antigc"]["rename_to"] = name
    save_settings()
    await safe_send(ctx.channel, f"antigc rename set to: {name}")

@bot.command(name="antigcrenameclear")
async def cmd_antigcrenameclear(ctx):
    settings["antigc"]["rename_to"] = ""
    save_settings()
    await safe_send(ctx.channel, "antigc rename cleared.")

@bot.command(name="antigcdelay")
async def cmd_antigcdelay(ctx, seconds: float = None):
    if seconds is None:
        return await safe_send(ctx.channel, f"Current delay: {settings['antigc']['leave_delay']}s")
    if seconds < 0:
        return await safe_send(ctx.channel, "Must be >= 0.")
    settings["antigc"]["leave_delay"] = seconds
    save_settings()
    await safe_send(ctx.channel, f"antigc leave delay set to {seconds}s.")

@bot.command(name="antigcwl")
async def cmd_antigcwl(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,antigcwl @user")
    uid = ctx.message.mentions[0].id if ctx.message.mentions else None
    if uid is None:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    wl = settings["antigc"]["whitelist"]
    if uid in wl:
        return await safe_send(ctx.channel, "Already whitelisted.")
    wl.append(uid)
    save_settings()
    await safe_send(ctx.channel, f"Whitelisted <@{uid}>.")

@bot.command(name="antigcwlun")
async def cmd_antigcwlun(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,antigcwlun @user")
    uid = ctx.message.mentions[0].id if ctx.message.mentions else None
    if uid is None:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    wl = settings["antigc"]["whitelist"]
    if uid not in wl:
        return await safe_send(ctx.channel, "Not whitelisted.")
    wl.remove(uid)
    save_settings()
    await safe_send(ctx.channel, f"Unwhitelisted <@{uid}>.")

@bot.command(name="antigcwllist")
async def cmd_antigcwllist(ctx):
    wl = settings["antigc"]["whitelist"]
    if not wl:
        return await safe_send(ctx.channel, "Whitelist is empty.")
    await safe_send(ctx.channel, "Whitelist:\n" + "\n".join(f"- <@{u}>" for u in wl))

@bot.command(name="antigcwlclear")
async def cmd_antigcwlclear(ctx):
    settings["antigc"]["whitelist"] = []
    save_settings()
    await safe_send(ctx.channel, "Whitelist cleared.")

@bot.command(name="antigcbl")
async def cmd_antigcbl(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,antigcbl @user")
    uid = ctx.message.mentions[0].id if ctx.message.mentions else None
    if uid is None:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    bl = settings["antigc"]["blacklist"]
    if uid in bl:
        return await safe_send(ctx.channel, "Already blacklisted.")
    bl.append(uid)
    save_settings()
    await safe_send(ctx.channel, f"Blacklisted <@{uid}>.")

@bot.command(name="antigcblun")
async def cmd_antigcblun(ctx, target: str = None):
    if not target:
        return await safe_send(ctx.channel, "Usage: ,antigcblun @user")
    uid = ctx.message.mentions[0].id if ctx.message.mentions else None
    if uid is None:
        try: uid = int(target.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    bl = settings["antigc"]["blacklist"]
    if uid not in bl:
        return await safe_send(ctx.channel, "Not blacklisted.")
    bl.remove(uid)
    save_settings()
    await safe_send(ctx.channel, f"Unblacklisted <@{uid}>.")

@bot.command(name="antigcbllist")
async def cmd_antigcbllist(ctx):
    bl = settings["antigc"]["blacklist"]
    if not bl:
        return await safe_send(ctx.channel, "Blacklist is empty.")
    await safe_send(ctx.channel, "Blacklist:\n" + "\n".join(f"- <@{u}>" for u in bl))

@bot.command(name="antigcblclear")
async def cmd_antigcblclear(ctx):
    settings["antigc"]["blacklist"] = []
    save_settings()
    await safe_send(ctx.channel, "Blacklist cleared.")

@bot.command(name="antigcreset")
async def cmd_antigcreset(ctx):
    settings["antigc"] = json.loads(json.dumps(DEFAULT_SETTINGS["antigc"]))
    save_settings()
    await safe_send(ctx.channel, "antigc settings reset.")

# =========================================================
# LEAVEALLGCS (bulk leave every group chat)
# =========================================================
@bot.command(name="leaveallgcs", aliases=["lag"])
async def cmd_leaveallgcs(ctx):
    gcs = [ch for ch in bot.private_channels if isinstance(ch, discord.GroupChannel)]
    if not gcs:
        return await safe_send(ctx.channel, "No group chats to leave.")
    await safe_send(ctx.channel, f"Leaving {len(gcs)} GC(s)...")
    count = 0
    failed = 0
    for ch in gcs:
        try:
            await ch.leave()
            count += 1
            await asyncio.sleep(0.9)
        except Exception as e:
            failed += 1
            print(f"[leaveallgcs] failed to leave {ch.id}: {e}")
    msg = f"Left {count} GC(s)."
    if failed:
        msg += f" {failed} failed."
    await safe_send(ctx.channel, msg)

@bot.command(name="gclist")
async def cmd_gclist(ctx):
    gcs = [ch for ch in bot.private_channels if isinstance(ch, discord.GroupChannel)]
    if not gcs:
        return await safe_send(ctx.channel, "No group chats found.")
    lines = []
    for ch in gcs:
        try:
            name = ch.name or "(no name)"
            lines.append(f"- {name} | id: {ch.id} | members: {len(ch.recipients) + 1}")
        except Exception:
            lines.append(f"- (unknown) | id: {ch.id}")
    header = f"Group chats ({len(gcs)}):\n"
    # Split into chunks of 15 to avoid message-length issues
    chunk_size = 15
    for i in range(0, len(lines), chunk_size):
        part = header if i == 0 else ""
        part += "\n".join(lines[i:i + chunk_size])
        await safe_send(ctx.channel, part)
        if i + chunk_size < len(lines):
            await asyncio.sleep(0.5)

# =========================================================
# AUTOREACT (react to self or specific users)
# =========================================================
DEFAULT_SETTINGS["autoreact"] = {
    "self_react_emoji": "",
    "targets": {},      # { user_id: "emoji" }
}

if "autoreact" not in settings:
    settings["autoreact"] = json.loads(json.dumps(DEFAULT_SETTINGS["autoreact"]))
else:
    for k, v in DEFAULT_SETTINGS["autoreact"].items():
        if k not in settings["autoreact"]:
            settings["autoreact"][k] = v
save_settings()

HELP_REACT = """```
--- Autoreact Sub-Commands ---

Self-react (bot reacts to its own messages):
  ,selfreact <emoji>       set emoji
  ,selfreactoff            turn off
  ,selfreactinfo           show current

Target-react (bot reacts to specific users' messages):
  ,react @user <emoji>     add target
  ,react <user_id> <emoji> add target by ID
  ,reactlist               show targets
  ,reactun @user           remove one target
  ,reactun <user_id>       remove by ID
  ,reactclear              remove all targets
  ,reactoff                turn off everything (self + targets)
```"""

@bot.command(name="selfreact")
async def cmd_selfreact(ctx, emoji: str = None):
    if not emoji:
        return await safe_send(ctx.channel, "Usage: ,selfreact <emoji>")
    settings["autoreact"]["self_react_emoji"] = emoji
    save_settings()
    await safe_send(ctx.channel, f"Self-react emoji set to: {emoji}")

@bot.command(name="selfreactoff")
async def cmd_selfreactoff(ctx):
    settings["autoreact"]["self_react_emoji"] = ""
    save_settings()
    await safe_send(ctx.channel, "Self-react off.")

@bot.command(name="selfreactinfo")
async def cmd_selfreactinfo(ctx):
    emo = settings["autoreact"].get("self_react_emoji", "")
    if not emo:
        return await safe_send(ctx.channel, "Self-react: off")
    await safe_send(ctx.channel, f"Self-react emoji: {emo}")

@bot.command(name="react")
async def cmd_react(ctx, user: str = None, emoji: str = None):
    if not user or not emoji:
        return await safe_send(ctx.channel, "Usage: ,react @user <emoji>  OR  ,react <user_id> <emoji>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(user.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    settings["autoreact"]["targets"][str(uid)] = emoji
    save_settings()
    await safe_send(ctx.channel, f"Added <@{uid}> → {emoji}")

@bot.command(name="reactun")
async def cmd_reactun(ctx, user: str = None):
    if not user:
        return await safe_send(ctx.channel, "Usage: ,reactun @user OR ,reactun <user_id>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(user.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    targets = settings["autoreact"]["targets"]
    if str(uid) not in targets:
        return await safe_send(ctx.channel, "Not in list.")
    del targets[str(uid)]
    save_settings()
    await safe_send(ctx.channel, f"Removed <@{uid}>.")

@bot.command(name="reactlist")
async def cmd_reactlist(ctx):
    targets = settings["autoreact"]["targets"]
    self_emo = settings["autoreact"].get("self_react_emoji", "")
    lines = []
    if self_emo:
        lines.append(f"SELF → {self_emo}")
    for uid, emo in targets.items():
        lines.append(f"<@{uid}> → {emo}")
    if not lines:
        return await safe_send(ctx.channel, "No reactions set.")
    await safe_send(ctx.channel, "Current reactions:\n" + "\n".join(lines))

@bot.command(name="reactclear")
async def cmd_reactclear(ctx):
    settings["autoreact"]["targets"] = {}
    save_settings()
    await safe_send(ctx.channel, "All target reacts cleared.")

@bot.command(name="reactoff")
async def cmd_reactoff(ctx):
    settings["autoreact"]["targets"] = {}
    settings["autoreact"]["self_react_emoji"] = ""
    save_settings()
    await safe_send(ctx.channel, "Autoreact fully cleared (self + targets).")

# Hook into on_message (append to existing handler via another listener is not possible,
# so we route through a helper that on_message checks)
async def autoreact_try(message):
    try:
        cfg = settings.get("autoreact", {})
        # Self-react
        if message.author.id == bot.user.id:
            emo = cfg.get("self_react_emoji", "")
            if emo:
                try: await message.add_reaction(emo)
                except Exception as e: print(f"[selfreact] {e}")
            return
        # Target react
        targets = cfg.get("targets", {})
        emo = targets.get(str(message.author.id))
        if emo:
            try: await message.add_reaction(emo)
            except Exception as e: print(f"[react] {e}")
    except Exception as e:
        print(f"[autoreact hook] {e}")

# =========================================================
# AUTOREPLY (auto-reply to specific users)
# =========================================================
DEFAULT_SETTINGS["autoreply"] = {
    "targets": {},   # { user_id: "reply text" }
}

if "autoreply" not in settings:
    settings["autoreply"] = json.loads(json.dumps(DEFAULT_SETTINGS["autoreply"]))
else:
    for k, v in DEFAULT_SETTINGS["autoreply"].items():
        if k not in settings["autoreply"]:
            settings["autoreply"][k] = v
save_settings()

HELP_REPLY = """```
--- Autoreply Sub-Commands ---

  ,ar @user <text>         add autoreply for user
  ,ar <user_id> <text>     add by ID
  ,arlist                  show all autoreplies
  ,arun @user              remove one
  ,arun <user_id>          remove by ID
  ,arclear                 remove all
```"""

@bot.command(name="ar", aliases=["autoreply"])
async def cmd_ar(ctx, user: str = None, *, text: str = None):
    if not user or not text:
        return await safe_send(ctx.channel, "Usage: ,ar @user <reply text>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(user.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    settings["autoreply"]["targets"][str(uid)] = text
    save_settings()
    await safe_send(ctx.channel, f"Autoreply set for <@{uid}>: {text}")

@bot.command(name="arun")
async def cmd_arun(ctx, user: str = None):
    if not user:
        return await safe_send(ctx.channel, "Usage: ,arun @user OR ,arun <user_id>")
    uid = None
    if ctx.message.mentions:
        uid = ctx.message.mentions[0].id
    else:
        try: uid = int(user.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user.")
    targets = settings["autoreply"]["targets"]
    if str(uid) not in targets:
        return await safe_send(ctx.channel, "Not in list.")
    del targets[str(uid)]
    save_settings()
    await safe_send(ctx.channel, f"Removed <@{uid}>.")

@bot.command(name="arlist")
async def cmd_arlist(ctx):
    targets = settings["autoreply"]["targets"]
    if not targets:
        return await safe_send(ctx.channel, "No autoreplies set.")
    lines = [f"<@{uid}> → {txt}" for uid, txt in targets.items()]
    await safe_send(ctx.channel, "Autoreplies:\n" + "\n".join(lines))

@bot.command(name="arclear")
async def cmd_arclear(ctx):
    settings["autoreply"]["targets"] = {}
    save_settings()
    await safe_send(ctx.channel, "All autoreplies cleared.")

async def autoreply_try(message):
    try:
        if message.author.id == bot.user.id:
            return
        cfg = settings.get("autoreply", {})
        targets = cfg.get("targets", {})
        txt = targets.get(str(message.author.id))
        if txt:
            try:
                await message.reply(txt)
            except Exception as e:
                print(f"[autoreply] {e}")
    except Exception as e:
        print(f"[autoreply hook] {e}")

# =========================================================
# CENTRAL MESSAGE ROUTER
# =========================================================
@bot.event
async def on_message(message):
    # Ignore our own command processing pipeline still works
    try:
        await autoreact_try(message)
    except Exception as e:
        print(f"[router autoreact] {e}")

    try:
        await autoreply_try(message)
    except Exception as e:
        print(f"[router autoreply] {e}")

    # Let command processing run
    await bot.process_commands(message)

# =========================================================
# AFK (manual AFK mode with auto-reply on mention)
# =========================================================
DEFAULT_SETTINGS["afk"] = {
    "enabled": False,
    "reply": "I'm AFK right now.",
    "started_at": 0,
}

if "afk" not in settings:
    settings["afk"] = json.loads(json.dumps(DEFAULT_SETTINGS["afk"]))
else:
    for k, v in DEFAULT_SETTINGS["afk"].items():
        if k not in settings["afk"]:
            settings["afk"][k] = v
save_settings()

HELP_AFK = """```
--- AFK Sub-Commands ---

  ,afk                     enable AFK
  ,afkoff                  disable AFK (shows duration)
  ,afkinfo                 show status
  ,afkreply <text>         set the auto-reply text
```"""

@bot.command(name="afk")
async def cmd_afk(ctx):
    if settings["afk"].get("enabled"):
        return await safe_send(ctx.channel, "Already AFK.")
    settings["afk"]["enabled"] = True
    settings["afk"]["started_at"] = time.time()
    save_settings()
    await safe_send(ctx.channel, "AFK ON.")

@bot.command(name="afkoff")
async def cmd_afkoff(ctx):
    if not settings["afk"].get("enabled"):
        return await safe_send(ctx.channel, "Not AFK.")
    dur = int(time.time() - settings["afk"].get("started_at", time.time()))
    settings["afk"]["enabled"] = False
    save_settings()
    h, r = divmod(dur, 3600)
    m, s = divmod(r, 60)
    await safe_send(ctx.channel, f"AFK off. Was away {h}h {m}m {s}s.")

@bot.command(name="afkinfo")
async def cmd_afkinfo(ctx):
    cfg = settings["afk"]
    state = "ON" if cfg.get("enabled") else "OFF"
    reply = cfg.get("reply", "")
    await safe_send(ctx.channel, f"AFK: {state}\nReply: {reply}")

@bot.command(name="afkreply")
async def cmd_afkreply(ctx, *, text: str = None):
    if not text:
        return await safe_send(ctx.channel, f"Current reply: {settings['afk'].get('reply')}")
    settings["afk"]["reply"] = text
    save_settings()
    await safe_send(ctx.channel, f"AFK reply set to: {text}")

# =========================================================
# ANTI-AFK (auto-say a reply when someone messages you)
# =========================================================
DEFAULT_SETTINGS["antiafk"] = {
    "enabled": False,
    "reply": "I'm here.",
    "mode": "mention",     # "mention" = only when pinged, "channel" = every msg in monitored channel
    "channel": None,
}

if "antiafk" not in settings:
    settings["antiafk"] = json.loads(json.dumps(DEFAULT_SETTINGS["antiafk"]))
else:
    for k, v in DEFAULT_SETTINGS["antiafk"].items():
        if k not in settings["antiafk"]:
            settings["antiafk"][k] = v
save_settings()

HELP_ANTIAFK = """```
--- Anti-AFK Sub-Commands ---

  ,antiafk on [channel_id]     enable (optional channel ID for channel mode)
  ,antiafk off                 disable
  ,antiafk info                show current settings
  ,antiafk mode <mention|channel>
  ,antiafk channel <id|clear>
  ,antiafk reply <text>
```"""

@bot.command(name="antiafk")
async def cmd_antiafk(ctx, mode: str = None, channel_id: int = None):
    cfg = settings["antiafk"]
    if mode is None or mode.lower() == "info":
        state = "ON" if cfg.get("enabled") else "OFF"
        ch = cfg.get("channel") or "none"
        msg = (
            f"```\n--- Anti-AFK ---\n"
            f"Status:  {state}\n"
            f"Mode:    {cfg.get('mode', 'mention')}\n"
            f"Channel: {ch}\n"
            f"Reply:   {cfg.get('reply')}\n```"
        )
        return await safe_send(ctx.channel, msg)

    m = mode.lower()
    if m == "on":
        cfg["enabled"] = True
        if channel_id is not None:
            cfg["channel"] = channel_id
            cfg["mode"] = "channel"
        save_settings()
        await safe_send(ctx.channel, "Anti-AFK ON.")
    elif m == "off":
        cfg["enabled"] = False
        save_settings()
        await safe_send(ctx.channel, "Anti-AFK OFF.")
    elif m == "mode":
        if channel_id is None:
            return await safe_send(ctx.channel, "Usage: ,antiafk mode <mention|channel>")
        # Actually mode string passed as channel_id here
        return await safe_send(ctx.channel, "Usage: ,antiafk mode mention  OR  ,antiafk mode channel")
    else:
        await safe_send(ctx.channel, "Use: ,antiafk on | off | info")

@bot.command(name="antiafkmode")
async def cmd_antiafkmode(ctx, mode: str = None):
    if mode is None:
        return await safe_send(ctx.channel, f"Current mode: {settings['antiafk'].get('mode')}")
    if mode.lower() not in ("mention", "channel"):
        return await safe_send(ctx.channel, "Use: mention or channel")
    settings["antiafk"]["mode"] = mode.lower()
    save_settings()
    await safe_send(ctx.channel, f"Anti-AFK mode: {mode.lower()}")

@bot.command(name="antiafkchannel")
async def cmd_antiafkchannel(ctx, channel_id: str = None):
    if channel_id is None:
        return await safe_send(ctx.channel, f"Current channel: {settings['antiafk'].get('channel')}")
    if channel_id.lower() == "clear":
        settings["antiafk"]["channel"] = None
        save_settings()
        return await safe_send(ctx.channel, "Anti-AFK channel cleared.")
    try:
        cid = int(channel_id)
    except ValueError:
        return await safe_send(ctx.channel, "Invalid channel ID.")
    settings["antiafk"]["channel"] = cid
    settings["antiafk"]["mode"] = "channel"
    save_settings()
    await safe_send(ctx.channel, f"Anti-AFK channel set to {cid}.")

@bot.command(name="antiafkreply")
async def cmd_antiafkreply(ctx, *, text: str = None):
    if not text:
        return await safe_send(ctx.channel, f"Current reply: {settings['antiafk'].get('reply')}")
    settings["antiafk"]["reply"] = text
    save_settings()
    await safe_send(ctx.channel, f"Anti-AFK reply set to: {text}")

async def afk_try(message):
    """Handle AFK auto-reply when we get pinged."""
    try:
        cfg = settings.get("afk", {})
        if not cfg.get("enabled"):
            return
        if message.author.id == bot.user.id:
            return
        if bot.user in message.mentions:
            try:
                await message.channel.send(cfg.get("reply", "I'm AFK right now."))
            except Exception as e:
                print(f"[afk reply] {e}")
    except Exception as e:
        print(f"[afk hook] {e}")

async def antiafk_try(message):
    try:
        cfg = settings.get("antiafk", {})
        if not cfg.get("enabled"):
            return
        if message.author.id == bot.user.id:
            return
        mode = cfg.get("mode", "mention")
        if mode == "mention":
            if bot.user in message.mentions:
                try:
                    await message.channel.send(cfg.get("reply", "I'm here."))
                except Exception as e:
                    print(f"[antiafk mention] {e}")
        elif mode == "channel":
            ch = cfg.get("channel")
            if ch is not None and message.channel.id == ch:
                try:
                    await message.channel.send(cfg.get("reply", "I'm here."))
                except Exception as e:
                    print(f"[antiafk channel] {e}")
    except Exception as e:
        print(f"[antiafk hook] {e}")

@bot.command(name="antiafkreset")
async def cmd_antiafkreset(ctx):
    settings["antiafk"] = json.loads(json.dumps(DEFAULT_SETTINGS["antiafk"]))
    save_settings()
    await safe_send(ctx.channel, "Anti-AFK settings reset.")

# =========================================================
# COMMAND ALIASES (user-defined shortcuts)
# =========================================================
DEFAULT_SETTINGS["aliases"] = {}   # { "short": "long" }

if "aliases" not in settings:
    settings["aliases"] = {}
save_settings()

HELP_ALIAS = """```
--- Command Aliases ---

  ,alias add <short> <long>   create alias (e.g. ,alias add ab autobeef)
  ,alias remove <short>       remove alias
  ,alias list                 show all aliases
  ,alias clear                remove all aliases

Example:
  ,alias add s spam
  then typing ,s 12345 runs ,spam 12345
```"""

@bot.command(name="alias")
async def cmd_alias(ctx, action: str = None, short: str = None, *, long: str = None):
    if action is None:
        return await safe_send(ctx.channel, HELP_ALIAS)

    a = action.lower()

    if a == "add":
        if not short or not long:
            return await safe_send(ctx.channel, "Usage: ,alias add <short> <long>")
        settings["aliases"][short.lower()] = long.lower()
        save_settings()
        await safe_send(ctx.channel, f"Alias added: ,{short} → ,{long}")

    elif a == "remove":
        if not short:
            return await safe_send(ctx.channel, "Usage: ,alias remove <short>")
        key = short.lower()
        if key not in settings["aliases"]:
            return await safe_send(ctx.channel, f"No alias named {key}.")
        del settings["aliases"][key]
        save_settings()
        await safe_send(ctx.channel, f"Alias removed: {key}")

    elif a == "list":
        al = settings["aliases"]
        if not al:
            return await safe_send(ctx.channel, "No aliases set.")
        lines = [f",{k} → ,{v}" for k, v in al.items()]
        await safe_send(ctx.channel, "Aliases:\n" + "\n".join(lines))

    elif a == "clear":
        settings["aliases"] = {}
        save_settings()
        await safe_send(ctx.channel, "All aliases cleared.")

    else:
        await safe_send(ctx.channel, HELP_ALIAS)

# =========================================================
# CENTRAL MESSAGE ROUTER (final version)
# =========================================================
@bot.event
async def on_message(message):
    # Alias resolver: rewrite short → long before processing
    try:
        if message.author.id == bot.user.id and message.content.startswith(PREFIX):
            al = settings.get("aliases", {})
            if al:
                body = message.content[len(PREFIX):]
                parts = body.split(maxsplit=1)
                if parts:
                    head = parts[0].lower()
                    if head in al:
                        rest = parts[1] if len(parts) > 1 else ""
                        new_cmd = f"{PREFIX}{al[head]}"
                        if rest:
                            new_cmd += f" {rest}"
                        try:
                            await message.edit(content=new_cmd)
                            message = await message.channel.fetch_message(message.id)
                        except Exception as e:
                            print(f"[alias edit] {e}")
    except Exception as e:
        print(f"[alias hook] {e}")

    # Feature hooks
    try:
        await autoreact_try(message)
    except Exception as e:
        print(f"[router autoreact] {e}")

    try:
        await autoreply_try(message)
    except Exception as e:
        print(f"[router autoreply] {e}")

    try:
        await afk_try(message)
    except Exception as e:
        print(f"[router afk] {e}")

    try:
        await antiafk_try(message)
    except Exception as e:
        print(f"[router antiafk] {e}")

    # Command processing
    await bot.process_commands(message)

# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        cancel_all()
        print("\nShutting down.")
