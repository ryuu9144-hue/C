import discord
from discord.ext import commands
import asyncio
import random
import os
import time

# =========================================================
# AI FEATURE (Google Gemini)
# =========================================================
try:
    import google.generativeai as genai
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False
    print("[AI] google-generativeai not installed. Run: pip install google-generativeai")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_ai_model = None

if _GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _ai_model = genai.GenerativeModel("gemini-2.0-flash")
        print("[AI] Gemini model loaded.")
    except Exception as e:
        print(f"[AI] init failed: {e}")
        _ai_model = None
elif not GEMINI_API_KEY:
    print("[AI] GEMINI_API_KEY not set. AI commands will be disabled.")


async def ask_ai(prompt: str, timeout: float = 20.0) -> str:
    if _ai_model is None:
        return "AI is not configured. Set GEMINI_API_KEY."
    if not prompt or not prompt.strip():
        return "(empty prompt)"

    def _call():
        try:
            resp = _ai_model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": 500,
                    "temperature": 0.9,
                },
            )
            text = getattr(resp, "text", None)
            if not text:
                return "(no response)"
            return text.strip()
        except Exception as e:
            return f"AI error: {e}"

    try:
        return await asyncio.wait_for(asyncio.to_thread(_call), timeout=timeout)
    except asyncio.TimeoutError:
        return "AI timed out. Try again."
    except Exception as e:
        return f"AI error: {e}"


# =========================================================
# CONFIG
# =========================================================
TOKEN = os.getenv("DISCORD_TOKEN", "PUT_YOUR_TOKEN_HERE")
PREFIX = ","
START_TIME = time.monotonic()

# =========================================================
# FILE LOADER
# =========================================================
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

def normalize_filename(name: str, default: str):
    if not name:
        return default
    if not name.endswith(".txt"):
        name += ".txt"
    return name

# =========================================================
# BOT
# =========================================================
bot = commands.Bot(command_prefix=PREFIX, self_bot=True, help_command=None)

state = {
    "spam_task": None, "beef_task": None, "ladder_task": None,
    "kill_task": None, "gcname_task": None, "count_task": None,
    "stam_task": None, "paste_task": None, "rpc_task": None,
    "killgc_task": None, "massdm_task": None, "massgc_task": None,

    "anti_gc": False, "anti_afk": False, "afk": False,
    "anti_afk_channel": None, "anti_afk_reply": "I'm here.",
    "afk_reply": "I'm AFK right now.",
    "afk_since": None, "case": "M",

    "self_react": None,
    "autoreact_targets": {},
    "autoreply_targets": set(),
    "beef_targets": set(),
    "rpc_list": [], "rpc_index": 0,

    "auto_large": False,
    "ai_auto": False,
    "typing_indicator": True,

    "snipe_cache": {},
    "editsnipe_cache": {},
}

# =========================================================
# HELPERS
# =========================================================
def cancel_task(key):
    t = state.get(key)
    if t and not t.done():
        t.cancel()
        state[key] = None

def apply_case(text, mode):
    mode = (mode or "M").upper()
    if mode == "U": return text.upper()
    if mode == "L": return text.lower()
    if mode == "M": return "".join(random.choice([c.upper(), c.lower()]) for c in text)
    return text

async def safe_send(channel, content=None, **kwargs):
    try: return await channel.send(content, **kwargs)
    except Exception as e: print(f"[send fail] {e}")

async def safe_edit(channel, **kwargs):
    try: return await channel.edit(**kwargs)
    except Exception as e: print(f"[edit fail] {e}")

async def send_typing(channel):
    try:
        await channel.trigger_typing()
    except Exception as e:
        print(f"[typing fail] {e}")

# =========================================================
# EVENTS
# =========================================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"Prefix: {bot.command_prefix}")

@bot.event
async def on_private_channel_create(channel):
    if state["anti_gc"] and isinstance(channel, discord.GroupChannel):
        try:
            await safe_send(channel, "Not joining this GC.")
            await asyncio.sleep(1.0)
            await channel.leave()
        except Exception as e:
            print(f"[anti-gc] {e}")

@bot.event
async def on_message(message):
    # Snipe cache
    if message.author.id != bot.user.id:
        state["snipe_cache"][message.channel.id] = {
            "author": message.author,
            "content": message.content,
            "timestamp": message.created_at,
        }

    # AI auto-reply
    if state.get("ai_auto") and message.author.id != bot.user.id:
        should_reply = False
        if isinstance(message.channel, discord.DMChannel):
            should_reply = True
        elif bot.user in message.mentions:
            should_reply = True

        if should_reply:
            async with message.channel.typing():
                answer = await ask_ai(message.content)
            try:
                await message.reply(answer[:1900])
            except Exception as e:
                print(f"[ai-auto] {e}")

    # Auto-large
    if state["auto_large"] and message.author.id == bot.user.id:
        content = message.content
        if (content
                and not content.startswith(bot.command_prefix)
                and not content.startswith("#")):
            try:
                await message.edit(content=f"# {content}")
            except Exception as e:
                print(f"[auto-large] {e}")

    # Self-react
    if message.author.id == bot.user.id and state["self_react"]:
        try: await message.add_reaction(state["self_react"])
        except: pass

    if message.author.id in state["autoreact_targets"]:
        try: await message.add_reaction(state["autoreact_targets"][message.author.id])
        except: pass

    if message.author.id in state["autoreply_targets"] and message.author.id != bot.user.id:
        try: await message.reply("Not interested.")
        except: pass

    if state["afk"] and bot.user in message.mentions and message.author.id != bot.user.id:
        try: await message.channel.send(state["afk_reply"])
        except: pass

    if (state["anti_afk"] and state["anti_afk_channel"]
            and message.channel.id == state["anti_afk_channel"]
            and message.author.id != bot.user.id):
        try: await message.channel.send(state["anti_afk_reply"])
        except: pass

    if message.author.id in state["beef_targets"] and message.author.id != bot.user.id:
        lines = load_lines("beef.txt")
        if lines:
            try: await message.channel.send(random.choice(lines))
            except: pass

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.id != bot.user.id:
        state["snipe_cache"][message.channel.id] = {
            "author": message.author,
            "content": message.content,
            "timestamp": message.created_at,
        }

@bot.event
async def on_message_edit(before, after):
    if before.author.id != bot.user.id and before.content != after.content:
        state["editsnipe_cache"][before.channel.id] = {
            "author": before.author,
            "before": before.content,
            "after": after.content,
        }

# =========================================================
# HELP
# =========================================================
HELP_TEXT = """```
--- Will SB ---

AI:
  ,ai <question>            

  ,aitoggle on / off    
         

Snipe:
  ,snipe     
  ,editsnipe     
  ,clearsnipe   

Spam / Beef:
  ,spam <msg>                    
  ,spamstop

  ,autobeef <id> <delay> [file]  
  ,autobeefstop

  ,autopaste <id> <delay> <msg>  
  ,autopastestop

  ,autocount <id> <limit> [delay]  
  ,autocountstop

  ,stam <id> <delay> <msg>    
  ,stamstop

Ladder / Kill:
  ,autoladder @user <delay> [file]   
  ,autoladderstop

  ,autokill @user <delay> [file]     
  ,autokillstop

GC:
  ,gcname <id> <delay> [file]    
  ,gcnamestop

  ,killgc <id> <delay> [file]   
  ,killgcstop

  ,antigc on / off / status
  ,leaveallgcs

React / Reply / Beef:
  ,react <emoji>                 (self)
  ,react @user <emoji>           (target)
  ,reactstop

  ,autoreply @user              
  ,autoreplystop

  ,beef @user [file]            
  ,beefstop

AFK:
  ,afk                          
  ,afkoff
  ,afksetreply <text>
  ,antiafk on <id> / off
  ,antiafksetreply <text>

Text:
  ,typing on / off               (typing indicator for autobeef)
  ,autolarge on / off            (toggle auto "# " prefix)
  ,case U / L / M

Server / GC:
  ,nuke 
  ,nukegc
  ,purge <amount>
  ,kick @user  
  ,ban @user
  ,role @user <name> 
 ,removerole @user <name>
  ,server

Mass:
  ,massdm <msg>
  ,massgc <msg>
  ,stopmass

RPC / Stream:
  ,rpc <a,b,c>                   
  ,rpcstop
  ,stream <text>                
  ,streamstop

Utility:
  ,ping
  ,prefix <new>
  ,help

```"""

@bot.command(name="help")
async def cmd_help(ctx):
    await safe_send(ctx.channel, HELP_TEXT)
    try: await ctx.message.delete()
    except: pass

# =========================================================
# SNIPE
# =========================================================
@bot.command(name="snipe")
async def cmd_snipe(ctx):
    data = state["snipe_cache"].get(ctx.channel.id)
    if not data:
        await safe_send(ctx.channel, "Nothing to snipe.")
        try: await ctx.message.delete()
        except: pass
        return

    content = data["content"] or "(no text)"
    if len(content) > 1800:
        content = content[:1800] + "..."

    embed = discord.Embed(
        description=content,
        color=0x2b2d31,
        timestamp=data["timestamp"],
    )
    embed.set_author(
        name=str(data["author"]),
        icon_url=data["author"].display_avatar.url if data["author"].display_avatar else None,
    )
    embed.set_footer(text="Sniped")

    await safe_send(ctx.channel, embed=embed)
    try: await ctx.message.delete()
    except: pass

@bot.command(name="editsnipe")
async def cmd_editsnipe(ctx):
    data = state["editsnipe_cache"].get(ctx.channel.id)
    if not data:
        await safe_send(ctx.channel, "Nothing to editsnipe.")
        try: await ctx.message.delete()
        except: pass
        return

    before = data["before"] or "(empty)"
    after = data["after"] or "(empty)"
    if len(before) > 800: before = before[:800] + "..."
    if len(after) > 800: after = after[:800] + "..."

    embed = discord.Embed(color=0x2b2d31)
    embed.set_author(
        name=str(data["author"]),
        icon_url=data["author"].display_avatar.url if data["author"].display_avatar else None,
    )
    embed.add_field(name="Before", value=before, inline=False)
    embed.add_field(name="After", value=after, inline=False)
    embed.set_footer(text="Edit sniped")

    await safe_send(ctx.channel, embed=embed)
    try: await ctx.message.delete()
    except: pass

@bot.command(name="clearsnipe")
async def cmd_clearsnipe(ctx):
    state["snipe_cache"].clear()
    state["editsnipe_cache"].clear()
    await safe_send(ctx.channel, "Snipe caches cleared.")

# =========================================================
# AI COMMANDS
# =========================================================
@bot.command(name="ai")
async def cmd_ai(ctx, *, prompt: str = None):
    if not prompt:
        return await safe_send(ctx.channel, "Usage: ,ai <your question>")
    async with ctx.typing():
        answer = await ask_ai(prompt)
    await safe_send(ctx.channel, answer)
    try: await ctx.message.delete()
    except: pass

@bot.command(name="aitoggle")
async def cmd_aitoggle(ctx, mode: str = None):
    if mode and mode.lower() == "on":
        state["ai_auto"] = True
        await safe_send(ctx.channel, "AI auto-reply ON.")
    elif mode and mode.lower() == "off":
        state["ai_auto"] = False
        await safe_send(ctx.channel, "AI auto-reply OFF.")
    else:
        state["ai_auto"] = not state.get("ai_auto", False)
        status = "ON" if state["ai_auto"] else "OFF"
        await safe_send(ctx.channel, f"AI auto-reply toggled {status}.")

# =========================================================
# AUTO LARGE / TYPING
# =========================================================
@bot.command(name="autolarge")
async def cmd_autolarge(ctx, mode: str = None):
    if mode and mode.lower() == "on":
        state["auto_large"] = True
        await safe_send(ctx.channel, "Auto-large ON.")
    elif mode and mode.lower() == "off":
        state["auto_large"] = False
        await safe_send(ctx.channel, "Auto-large OFF.")
    else:
        state["auto_large"] = not state["auto_large"]
        status = "ON" if state["auto_large"] else "OFF"
        await safe_send(ctx.channel, f"Auto-large toggled to {status}.")

@bot.command(name="typing")
async def cmd_typing(ctx, mode: str = None):
    if mode and mode.lower() == "on":
        state["typing_indicator"] = True
        await safe_send(ctx.channel, "Typing indicator ON.")
    elif mode and mode.lower() == "off":
        state["typing_indicator"] = False
        await safe_send(ctx.channel, "Typing indicator OFF.")
    else:
        state["typing_indicator"] = not state["typing_indicator"]
        status = "ON" if state["typing_indicator"] else "OFF"
        await safe_send(ctx.channel, f"Typing indicator toggled {status}.")

# =========================================================
# SPAM / BEEF
# =========================================================
@bot.command(name="spam")
async def cmd_spam(ctx, *, msg: str = None):
    if not msg: return
    cancel_task("spam_task")
    async def loop():
        while True:
            await safe_send(ctx.channel, msg)
            await asyncio.sleep(0.7)
    state["spam_task"] = asyncio.create_task(loop())

@bot.command(name="spamstop")
async def cmd_spamstop(ctx): cancel_task("spam_task")

@bot.command(name="autobeef")
async def cmd_autobeef(ctx, channel_id: int = None, delay: float = 1.2, filename: str = "autobeef.txt"):
    fname = normalize_filename(filename, "autobeef.txt")
    lines = load_lines(fname)
    if not channel_id or not lines:
        return await safe_send(ctx.channel, f"Missing channel or {fname} empty/missing.")
    ch = bot.get_channel(channel_id)
    if not ch: return await safe_send(ctx.channel, "Channel not found.")
    cancel_task("beef_task")
    async def loop():
        while True:
            if state["typing_indicator"]:
                await send_typing(ch)
                await asyncio.sleep(random.uniform(0.4, 1.0))
            msg = apply_case(random.choice(lines), state["case"])
            await safe_send(ch, msg)
            await asyncio.sleep(max(delay, 0.5))
    state["beef_task"] = asyncio.create_task(loop())
    await safe_send(ctx.channel, f"autobeef running in {channel_id} using {fname}.")

@bot.command(name="autobeefstop")
async def cmd_autobeefstop(ctx): cancel_task("beef_task")

@bot.command(name="autopaste")
async def cmd_autopaste(ctx, channel_id: int = None, delay: float = 1.2, *, msg: str = None):
    if not channel_id or not msg: return
    ch = bot.get_channel(channel_id)
    if not ch: return await safe_send(ctx.channel, "Channel not found.")
    cancel_task("paste_task")
    async def loop():
        while True:
            await safe_send(ch, msg)
            await asyncio.sleep(max(delay, 0.5))
    state["paste_task"] = asyncio.create_task(loop())

@bot.command(name="autopastestop")
async def cmd_autopastestop(ctx): cancel_task("paste_task")

@bot.command(name="autocount")
async def cmd_autocount(ctx, channel_id: int = None, limit: int = 10, delay: float = 1.5):
    if not channel_id: return
    ch = bot.get_channel(channel_id)
    if not ch: return await safe_send(ctx.channel, "Channel not found.")
    cancel_task("count_task")
    async def loop():
        for i in range(1, limit + 1):
            await safe_send(ch, str(i))
            await asyncio.sleep(max(delay, 1.0))
    state["count_task"] = asyncio.create_task(loop())

@bot.command(name="autocountstop")
async def cmd_autocountstop(ctx): cancel_task("count_task")

@bot.command(name="stam")
async def cmd_stam(ctx, channel_id: int = None, delay: float = 1.5, *, msg: str = None):
    if not channel_id or not msg: return
    ch = bot.get_channel(channel_id)
    if not ch: return await safe_send(ctx.channel, "Channel not found.")
    cancel_task("stam_task")
    async def loop():
        i = 1
        while True:
            await safe_send(ch, f"{msg} ({i})")
            i += 1
            await asyncio.sleep(max(delay, 1.0))
    state["stam_task"] = asyncio.create_task(loop())

@bot.command(name="stamstop")
async def cmd_stamstop(ctx): cancel_task("stam_task")

# =========================================================
# LADDER / KILL
# =========================================================
@bot.command(name="autoladder")
async def cmd_autoladder(ctx, member: discord.Member = None, delay: float = 1.0, filename: str = "ladder.txt"):
    fname = normalize_filename(filename, "ladder.txt")
    lines = load_lines(fname)
    if not member or not lines:
        return await safe_send(ctx.channel, f"Mention a user or create {fname}.")
    cancel_task("ladder_task")
    async def loop():
        while True:
            await safe_send(ctx.channel, f"{member.mention} {random.choice(lines)}")
            await asyncio.sleep(max(delay, 0.5))
    state["ladder_task"] = asyncio.create_task(loop())
    await safe_send(ctx.channel, f"Ladder on {member.name} using {fname}.")

@bot.command(name="autoladderstop")
async def cmd_autoladderstop(ctx): cancel_task("ladder_task")

@bot.command(name="autokill")
async def cmd_autokill(ctx, member: discord.Member = None, delay: float = 0.5, filename: str = "kill.txt"):
    fname = normalize_filename(filename, "kill.txt")
    lines = load_lines(fname)
    if not member or not lines:
        return await safe_send(ctx.channel, f"Mention a user or create {fname}.")
    cancel_task("kill_task")
    async def loop():
        while True:
            await safe_send(ctx.channel, f"{member.mention} {random.choice(lines)}")
            await asyncio.sleep(max(delay, 0.3))
    state["kill_task"] = asyncio.create_task(loop())
    await safe_send(ctx.channel, f"Autokill on {member.name} using {fname}.")

@bot.command(name="autokillstop")
async def cmd_autokillstop(ctx): cancel_task("kill_task")

# =========================================================
# GC
# =========================================================
@bot.command(name="gcname")
async def cmd_gcname(ctx, channel_id: int = None, delay: float = 2.0, filename: str = "gcname.txt"):
    fname = normalize_filename(filename, "gcname.txt")
    names = load_lines(fname)
    if not channel_id or not names:
        return await safe_send(ctx.channel, f"Channel or {fname} missing.")
    ch = bot.get_channel(channel_id)
    if not ch or not isinstance(ch, discord.GroupChannel):
        return await safe_send(ctx.channel, "Not a GC.")
    cancel_task("gcname_task")
    async def loop():
        while True:
            await safe_edit(ch, name=random.choice(names))
            await asyncio.sleep(max(delay, 1.5))
    state["gcname_task"] = asyncio.create_task(loop())
    await safe_send(ctx.channel, f"GC name rotation started using {fname}.")

@bot.command(name="gcnamestop")
async def cmd_gcnamestop(ctx): cancel_task("gcname_task")

@bot.command(name="killgc")
async def cmd_killgc(ctx, channel_id: int = None, delay: float = 1.5, filename: str = "gcname.txt"):
    fname = normalize_filename(filename, "gcname.txt")
    names = load_lines(fname)
    if not channel_id or not names:
        return await safe_send(ctx.channel, f"Channel or {fname} missing.")
    ch = bot.get_channel(channel_id)
    if not ch or not isinstance(ch, discord.GroupChannel):
        return await safe_send(ctx.channel, "Not a GC.")
    cancel_task("killgc_task")
    async def loop():
        while True:
            await safe_edit(ch, name=random.choice(names))
            await asyncio.sleep(max(delay, 1.0))
    state["killgc_task"] = asyncio.create_task(loop())
    await safe_send(ctx.channel, f"Kill-GC started using {fname}.")

@bot.command(name="killgcstop")
async def cmd_killgcstop(ctx): cancel_task("killgc_task")

@bot.command(name="antigc")
async def cmd_antigc(ctx, mode: str = "status"):
    mode = mode.lower()
    if mode == "on":
        state["anti_gc"] = True
        await safe_send(ctx.channel, "Anti-GC ON.")
    elif mode == "off":
        state["anti_gc"] = False
        await safe_send(ctx.channel, "Anti-GC OFF.")
    else:
        await safe_send(ctx.channel, f"Anti-GC is {'ON' if state['anti_gc'] else 'OFF'}.")

@bot.command(name="leaveallgcs")
async def cmd_leaveallgcs(ctx):
    count = 0
    for ch in list(bot.private_channels):
        if isinstance(ch, discord.GroupChannel):
            try:
                await ch.leave()
                count += 1
                await asyncio.sleep(0.8)
            except: pass
    await safe_send(ctx.channel, f"Left {count} GC(s).")

# =========================================================
# REACT / REPLY / BEEF
# =========================================================
@bot.command(name="react")
async def cmd_react(ctx, arg1: str = None, arg2: str = None):
    if arg1 and arg2:
        try: uid = int(arg1.strip("<@!>"))
        except: return await safe_send(ctx.channel, "Invalid user ID.")
        state["autoreact_targets"][uid] = arg2
        await safe_send(ctx.channel, f"Reacting to <@{uid}> with {arg2}.")
    elif arg1:
        state["self_react"] = arg1
        await safe_send(ctx.channel, f"Self-react set to {arg1}.")

@bot.command(name="reactstop")
async def cmd_reactstop(ctx):
    state["self_react"] = None
    state["autoreact_targets"].clear()
    await safe_send(ctx.channel, "Reactions cleared.")

@bot.command(name="autoreply")
async def cmd_autoreply(ctx, member: discord.Member = None):
    if not member: return
    state["autoreply_targets"].add(member.id)
    await safe_send(ctx.channel, f"Autoreply ON for {member.name}.")

@bot.command(name="autoreplystop")
async def cmd_autoreplystop(ctx):
    state["autoreply_targets"].clear()
    await safe_send(ctx.channel, "Autoreply cleared.")

# =========================================================
# BEEF RESPONDER (now file-arg aware via set)
# =========================================================
state["beef_file"] = "beef.txt"

@bot.command(name="beef")
async def cmd_beef(ctx, member: discord.Member = None, filename: str = None):
    if filename:
        state["beef_file"] = normalize_filename(filename, "beef.txt")
    if not member:
        return await safe_send(ctx.channel, f"Usage: ,beef @user [file]  (current: {state['beef_file']})")
    state["beef_targets"].add(member.id)
    await safe_send(ctx.channel, f"Beef responder ON for {member.name} using {state['beef_file']}.")

@bot.command(name="beefstop")
async def cmd_beefstop(ctx):
    state["beef_targets"].clear()
    await safe_send(ctx.channel, "Beef responder cleared.")

@bot.command(name="beefsetfile")
async def cmd_beefsetfile(ctx, filename: str = None):
    if not filename:
        return await safe_send(ctx.channel, f"Current beef file: {state['beef_file']}")
    state["beef_file"] = normalize_filename(filename, "beef.txt")
    await safe_send(ctx.channel, f"Beef file set to {state['beef_file']}.")

# =========================================================
# AFK
# =========================================================
@bot.command(name="afk")
async def cmd_afk(ctx):
    state["afk"] = True
    state["afk_since"] = time.time()
    await safe_send(ctx.channel, "AFK ON.")

@bot.command(name="afkoff")
async def cmd_afkoff(ctx):
    if state["afk"]:
        dur = int(time.time() - state["afk_since"])
        state["afk"] = False
        await safe_send(ctx.channel, f"AFK off. Was away {dur}s.")

@bot.command(name="afksetreply")
async def cmd_afksetreply(ctx, *, text: str = None):
    if not text: return
    state["afk_reply"] = text
    await safe_send(ctx.channel, "AFK reply set.")

@bot.command(name="antiafk")
async def cmd_antiafk(ctx, mode: str = None, channel_id: int = None):
    if mode == "on" and channel_id:
        state["anti_afk"] = True
        state["anti_afk_channel"] = channel_id
        await safe_send(ctx.channel, f"Anti-AFK ON in {channel_id}.")
    elif mode == "off":
        state["anti_afk"] = False
        state["anti_afk_channel"] = None
        await safe_send(ctx.channel, "Anti-AFK OFF.")
    else:
        await safe_send(ctx.channel, "Usage: ,antiafk on <id> | ,antiafk off")

@bot.command(name="antiafksetreply")
async def cmd_antiafksetreply(ctx, *, text: str = None):
    if not text: return
    state["anti_afk_reply"] = text
    await safe_send(ctx.channel, "Anti-AFK reply set.")

# =========================================================
# SERVER MGMT
# =========================================================
@bot.command(name="purge")
async def cmd_purge(ctx, amount: int = 10):
    try: await ctx.message.delete()
    except: pass
    deleted = 0
    async for msg in ctx.channel.history(limit=amount + 10):
        if msg.author.id == bot.user.id:
            try:
                await msg.delete()
                deleted += 1
                if deleted >= amount: break
                await asyncio.sleep(0.8)
            except: pass

@bot.command(name="kick")
async def cmd_kick(ctx, member: discord.Member = None):
    if not member: return
    try:
        await member.kick()
        await safe_send(ctx.channel, f"Kicked {member.name}.")
    except: pass

@bot.command(name="ban")
async def cmd_ban(ctx, member: discord.Member = None):
    if not member: return
    try:
        await member.ban()
        await safe_send(ctx.channel, f"Banned {member.name}.")
    except: pass

@bot.command(name="role")
async def cmd_role(ctx, member: discord.Member = None, *, role_name: str = None):
    if not member or not role_name or not ctx.guild: return
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role:
        try:
            await member.add_roles(role)
            await safe_send(ctx.channel, f"Added {role_name}.")
        except: pass

@bot.command(name="removerole")
async def cmd_removerole(ctx, member: discord.Member = None, *, role_name: str = None):
    if not member or not role_name or not ctx.guild: return
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role:
        try:
            await member.remove_roles(role)
            await safe_send(ctx.channel, f"Removed {role_name}.")
        except: pass

@bot.command(name="server")
async def cmd_server(ctx):
    if not ctx.guild: return
    g = ctx.guild
    await safe_send(ctx.channel, f"Server: {g.name}\nMembers: {g.member_count}\nRoles: {len(g.roles)}\nChannels: {len(g.channels)}")

@bot.command(name="nuke")
async def cmd_nuke(ctx):
    g = ctx.guild
    if not g: return await safe_send(ctx.channel, "Server only.")
    await safe_send(ctx.channel, "Nuke starting...")

    for m in list(g.members):
        if m == g.me or m.bot: continue
        try:
            await m.ban(reason="nuke")
            await asyncio.sleep(2.5)
        except: pass

    for ch in list(g.channels):
        try:
            await ch.delete()
            await asyncio.sleep(2.5)
        except: pass

    new = []
    for i in range(1, 6):
        try:
            new.append(await g.create_text_channel(f"owned-{i}"))
            await asyncio.sleep(2.5)
        except: pass

    for ch in new:
        try:
            await ch.send("# Server nuked.")
            await asyncio.sleep(2.5)
        except: pass

@bot.command(name="nukegc")
async def cmd_nukegc(ctx):
    ch = ctx.channel
    if not isinstance(ch, discord.GroupChannel):
        return await safe_send(ctx.channel, "Only in GC.")
    for m in list(ch.recipients):
        if m.id == bot.user.id: continue
        try:
            await ch.remove_recipients(m)
            await asyncio.sleep(1.0)
        except: pass

# =========================================================
# MASS
# =========================================================
@bot.command(name="massdm")
async def cmd_massdm(ctx, *, msg: str = None):
    if not msg: return
    cancel_task("massdm_task")
    async def loop():
        for friend in bot.user.friends:
            try:
                await friend.send(msg)
                await asyncio.sleep(4.0)
            except: pass
    state["massdm_task"] = asyncio.create_task(loop())
    await safe_send(ctx.channel, "Mass DM started.")

@bot.command(name="massgc")
async def cmd_massgc(ctx, *, msg: str = None):
    if not msg: return
    cancel_task("massgc_task")
    async def loop():
        for gc in bot.private_channels:
            if isinstance(gc, discord.GroupChannel):
                try:
                    await gc.send(msg)
                    await asyncio.sleep(2.0)
                except: pass
    state["massgc_task"] = asyncio.create_task(loop())
    await safe_send(ctx.channel, "Mass GC started.")

@bot.command(name="stopmass")
async def cmd_stopmass(ctx):
    cancel_task("massdm_task")
    cancel_task("massgc_task")
    await safe_send(ctx.channel, "Mass stopped.")

# =========================================================
# RPC / STREAM
# =========================================================
@bot.command(name="rpc")
async def cmd_rpc(ctx, *, list_str: str = None):
    if not list_str: return
    state["rpc_list"] = [s.strip() for s in list_str.split(",") if s.strip()]
    state["rpc_index"] = 0
    cancel_task("rpc_task")
    async def loop():
        while True:
            if not state["rpc_list"]: break
            text = state["rpc_list"][state["rpc_index"] % len(state["rpc_list"])]
            state["rpc_index"] += 1
            try:
                await bot.change_presence(activity=discord.Streaming(name=text, url="https://twitch.tv/x"))
            except: pass
            await asyncio.sleep(15)
    state["rpc_task"] = asyncio.create_task(loop())
    await safe_send(ctx.channel, "RPC rotation started.")

@bot.command(name="rpcstop")
async def cmd_rpcstop(ctx):
    cancel_task("rpc_task")
    try: await bot.change_presence(activity=None)
    except: pass
    await safe_send(ctx.channel, "RPC rotation stopped.")

@bot.command(name="stream")
async def cmd_stream(ctx, *, text: str = None):
    if not text: return
    try:
        await bot.change_presence(activity=discord.Streaming(name=text, url="https://twitch.tv/x"))
        await safe_send(ctx.channel, f"Streaming: {text}")
    except Exception as e:
        await safe_send(ctx.channel, f"Error: {e}")

@bot.command(name="streamstop")
async def cmd_streamstop(ctx):
    try:
        await bot.change_presence(activity=None)
        await safe_send(ctx.channel, "Stream cleared.")
    except: pass

# =========================================================
# UTILITY
# =========================================================
@bot.command(name="ping")
async def cmd_ping(ctx):
    up = int(time.monotonic() - START_TIME)
    d, r = divmod(up, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    await safe_send(ctx.channel, f"Pong | {round(bot.latency*1000)}ms | Uptime {d}d {h}h {m}m {s}s")

@bot.command(name="prefix")
async def cmd_prefix(ctx, new_prefix: str = None):
    if not new_prefix: return
    bot.command_prefix = new_prefix
    await safe_send(ctx.channel, f"Prefix set to {new_prefix}")

@bot.command(name="case")
async def cmd_case(ctx, mode: str = None):
    if not mode: return
    mode = mode.upper()
    if mode not in ["U", "L", "M"]:
        return await safe_send(ctx.channel, "Use U, L, or M.")
    state["case"] = mode
    await safe_send(ctx.channel, f"Case set to {mode}.")

@bot.command(name="files")
async def cmd_files(ctx):
    txts = [f for f in os.listdir(".") if f.endswith(".txt")]
    if not txts:
        return await safe_send(ctx.channel, "No .txt files in the bot folder.")
    await safe_send(ctx.channel, "Available .txt files:\n" + "\n".join(f"• {f}" for f in txts))

# =========================================================
# RUN
# =========================================================
bot.run(TOKEN)
