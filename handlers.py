from __future__ import annotations

import asyncio
import datetime as dt
import random
import re
import time
from typing import Any, Dict, List, Optional

import aiohttp

from ..config import ConfigStore, JSONStore, RuntimeConfig

EIGHTBALL = [
    "It is certain.", "It is decidedly so.", "Without a doubt.",
    "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
    "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Don't count on it.", "My reply is no.",
    "My sources say no.", "Outlook not so good.", "Very doubtful.",
]
JOKES = [
    "Why do Java developers wear glasses? Because they don't C#!",
    "I told my computer I needed a break... it said 'no problem, I'll crash'.",
    "There are only 10 kinds of people: those who understand binary and those who don't.",
    "Why did the developer go broke? Because he used up all his cache.",
    "A SQL query walks into a bar, approaches two tables and asks: 'may I join you?'",
    "!false — it's funny because it's true.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
]
TOPICS = [
    "The best pizza topping and why you're wrong about pineapple",
    "Would you rather fight 1 horse-sized duck or 100 duck-sized horses?",
    "Is water wet? Defend your answer.",
    "The most overrated movie of all time",
    "If you could have any superpower but only for 1 hour a day, which one?",
    "Cereal first or milk first — the eternal debate",
    "What conspiracy theory would you start just for fun?",
]
WYR = [
    "Would you rather have unlimited pizza for life or unlimited tacos for life?",
    "Would you rather always be 10 minutes late or always be 20 minutes early?",
    "Would you rather have a pause button or a rewind button for your life?",
    "Would you rather know the history of every object you touch or be able to talk to animals?",
    "Would you rather be the funniest person in the room or the smartest?",
    "Would you rather explore space or the deep ocean?",
]
QUOTES = [
    ("The best way to predict the future is to invent it.", "Alan Kay"),
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("Programs must be written for people to read.", "Harold Abelson"),
    ("Simplicity is the soul of efficiency.", "Austin Freeman"),
    ("First, solve the problem. Then, write the code.", "John Johnson"),
]
FACTS = [
    "Honey never spoils — 3000-year-old honey is still edible.",
    "Octopuses have three hearts and blue blood.",
    "The first computer bug was an actual moth, found in 1947.",
    "Bananas are berries. Strawberries are not.",
    "A day on Venus is longer than a year on Venus.",
    "Sharks existed before trees.",
]
FORTUNES = [
    "A fresh start will bring you luck this week.",
    "Great XP gains are coming to those who chat.",
    "Someone is thinking about you right now. Fortune? Yes.",
    "Your next /eco daily claim will be extra lucky.",
    "You will find what you seek, probably in the last place you look.",
    "The bot senses greatness in your next message.",
]
PUNS = [
    "I'm reading a book about anti-gravity — it's impossible to put down.",
    "I told my computer a joke about UDP. I'm not sure it got it.",
    "The past, present and future walked into a bar. It was tense.",
    "Why do APIs never panic? They stay calm and carry on(tract).",
    "I would tell you a joke about infinity, but it never ends.",
    "There's a fine line between a numerator and a denominator.",
]
COMPLIMENTS = [
    "You have impeccable taste in Discord bots, clearly.",
    "Your typing speed is, statistically speaking, elite.",
    "You're the reason this server's vibe score is so high.",
    "Scientists studied your last message. It slaps.",
]
INSULTS = [
    "You're the human version of a 404 page.",
    "Your takes are so cold they need a jacket.",
    "You'd lose a debate with a rubber duck.",
    "I've seen smarter configs in a default .env file.",
]
TRIVIA = [
    ("What does HTTP 404 mean?", ["not found", "404"], "Not Found — the resource doesn't exist."),
    ("Which planet is largest?", ["jupiter"], "Jupiter."),
    ("What year was the first iPhone released?", ["2007"], "2007."),
    ("What does 'GPU' stand for?", ["graphics processing unit"], "Graphics Processing Unit."),
    ("Who created Linux?", ["linus", "torvalds", "linus torvalds"], "Linus Torvalds."),
    ("What's the capital of Japan?", ["tokyo"], "Tokyo."),
    ("How many bits are in a byte?", ["8", "eight"], "8."),
    ("What does SQL stand for?", ["structured query language"], "Structured Query Language."),
    ("Which company created Discord?", ["discord", "jason citron"], "Discord Inc. (Jason Citron & Stan Vishnevskiy)."),
    ("What is 2^10?", ["1024"], "1024."),
    ("What language has the mascot 'snek'?", ["python"], "Python."),
    ("What does RAM stand for?", ["random access memory"], "Random Access Memory."),
]
HANGMAN_WORDS = [
    "discord", "pipeline", "python", "server", "dashboard", "moderation",
    "fireworks", "asynchronous", "emoji", "keyboard", "minecraft", "protocol",
    "database", "bandwidth", "encryption", "compiler", "hardware", "laptop",
]
RPS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
SHOP_ITEMS = {
    "coffee": 50, "gaming-chair": 300, "rgb-everything": 500,
    "minecraft-account": 800, "xbox": 1200, "supercar": 50000,
}
SLOT_SYMBOLS = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
AI_PROVIDERS = {
    "fireworks": {
        "key": "FIREWORKS_API_KEY",
        "url": "https://api.fireworks.ai/inference/v1/chat/completions",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    },
    "openai": {
        "key": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o-mini",
    },
    "deepseek": {
        "key": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "default_model": "deepseek-chat",
    },
}


def _d(payload: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = payload
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _now() -> float:
    return time.time()


def _input_text(payload: Dict[str, Any]) -> str:
    inp = payload.get("input")
    if isinstance(inp, dict):
        return str(
            inp.get("text") or inp.get("message") or inp.get("query")
            or inp.get("question") or inp.get("expression") or inp.get("input") or ""
        ).strip()
    return str(inp or "").strip()

async def ai_chat(payload: Dict[str, Any]) -> Any:
    runtime: RuntimeConfig = payload["_runtime"]
    secrets: ConfigStore = payload["_secrets"]
    ai = runtime.ai
    provider = AI_PROVIDERS.get(ai.get("provider", "fireworks"), AI_PROVIDERS["fireworks"])
    api_key = secrets.get(provider["key"])
    if not api_key:
        return "AI isn't configured yet. Ask an admin to set the API key from the dashboard Settings page."

    user_input = _input_text(payload)
    if not user_input:
        return "Type something first."

    system_prompt = (
        payload.get("_system_prompt")
        or ai.get("system_prompt")
        or "You are a helpful, concise assistant."
    )
    body = {
        "model": ai.get("model") or provider["default_model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        "max_tokens": 512,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                provider["url"],
                json=body,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    msg = data.get("error", {}).get("message") or data.get("message") or f"HTTP {resp.status}"
                    return f"AI provider error: {msg}"
    except asyncio.TimeoutError:
        return "The AI service timed out. Please try again later."
    except aiohttp.ClientError as exc:
        return f"Couldn't reach the AI service: {exc.__class__.__name__}"

    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return "The AI returned an unexpected response format. Please try again."

    if len(text) > 1990:
        text = text[:1990] + "…"
    return text


async def ai_task(payload: Dict[str, Any]) -> Any:
    """Variant AI commands (translate, summarize, roast...) driven by entry prompt."""
    prompt_template: str = _d(payload, "entry", "prompt", default="Help with: {input}")
    user_input = _input_text(payload)
    if not user_input:
        return "Provide some input first."
    override = prompt_template.replace("{input}", user_input)
    return await ai_chat({**payload, "_system_prompt": override})

async def music_resolve(payload: Dict[str, Any]) -> Dict[str, Any]:
    import yt_dlp

    query = _input_text(payload)
    if not query:
        raise ValueError("Provide a song title or YouTube link first.")

    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        "source_address": "0.0.0.0",
    }

    def _extract() -> Dict[str, Any]:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
        if info and "entries" in info:
            entries = [e for e in info["entries"] if e]
            if not entries:
                raise ValueError(f"No results found for: {query}")
            info = entries[0]
        if not info:
            raise ValueError(f"No results found for: {query}")
        return {
            "title": info.get("title", "Unknown"),
            "url": info["url"],
            "webpage_url": info.get("webpage_url"),
            "duration": info.get("duration"),
        }

    return await asyncio.to_thread(_extract)

async def mod(payload: Dict[str, Any]) -> Any:
    interaction = payload.get("interaction")
    action = _d(payload, "entry", "action")
    inp = _d(payload, "input") or {}
    guild = interaction.guild if interaction else None
    if guild is None:
        return "This command only works inside a server."

    warnings_store: JSONStore = payload["_warnings"]
    actor = interaction.user

    def _perm(perm: str) -> bool:
        return bool(getattr(actor.guild_permissions, perm, False))

    if action == "kick":
        member = inp.get("member")
        if not _perm("kick_members"):
            return "You don't have the Kick Members permission."
        reason = str(inp.get("reason") or "No reason given")
        await member.kick(reason=f"{actor}: {reason}")
        return f"👢 **{member.display_name}** was kicked. Reason: {reason}"

    if action == "ban":
        member = inp.get("member")
        if not _perm("ban_members"):
            return "You don't have the Ban Members permission."
        reason = str(inp.get("reason") or "No reason given")
        await member.ban(reason=f"{actor}: {reason}")
        return f"🔨 **{member.display_name}** was banned. Reason: {reason}"

    if action == "unban":
        if not _perm("ban_members"):
            return "You don't have the Ban Members permission."
        user_id = str(inp.get("user_id") or "").strip()
        if not user_id.isdigit():
            return "Provide a valid user ID."
        banned = [b async for b in guild.bans(limit=200)]
        match = next((b for b in banned if str(b.user.id) == user_id), None)
        if match is None:
            return "That user isn't on the ban list."
        await guild.unban(match.user)
        return f"✅ {match.user} has been unbanned."

    if action == "timeout":
        member = inp.get("member")
        minutes = int(inp.get("minutes") or 10)
        if not _perm("moderate_members"):
            return "You don't have the Timeout Members permission."
        until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=max(1, min(40320, minutes)))
        await member.timeout(until, reason=f"timeout by {actor}")
        return f"🔇 **{member.display_name}** was timed out for {minutes} minutes."

    if action == "warn":
        member = inp.get("member")
        reason = str(inp.get("reason") or "No reason given")
        if not _perm("moderate_members") and not _perm("kick_members"):
            return "You don't have a moderation permission for this."
        gid, uid = str(guild.id), str(member.id)

        def _add_warn(d: dict) -> dict:
            d.setdefault(gid, {}).setdefault(uid, []).append(
                {"reason": reason, "by": str(actor), "ts": _now()}
            )
            return d

        warnings_store.update(_add_warn)
        count = len(warnings_store.read().get(gid, {}).get(uid, []))
        return f"⚠️ **{member.display_name}** has been warned ({count} total). Reason: {reason}"

    if action == "warnings":
        member = inp.get("member")
        gid, uid = str(guild.id), str(member.id)
        warns = warnings_store.read().get(gid, {}).get(uid, [])
        if not warns:
            return f"**{member.display_name}** has a clean record — no warnings. ✨"
        lines = [f"⚠️ **{member.display_name}** has {len(warns)} warning(s):"]
        for i, w in enumerate(warns[-10:], 1):
            when = dt.datetime.fromtimestamp(w["ts"]).strftime("%d/%m/%y")
            lines.append(f"{i}. [{when}] {w['reason']} — by {w['by']}")
        return "\n".join(lines)

    if action == "clearwarns":
        member = inp.get("member")
        if not _perm("moderate_members"):
            return "You don't have a moderation permission for this."
        gid, uid = str(guild.id), str(member.id)

        def _clear(d: dict) -> dict:
            d.get(gid, {}).pop(uid, None)
            return d

        warnings_store.update(_clear)
        return f"🧹 Warnings for **{member.display_name}** have been cleared."

    if action == "purge":
        if not _perm("manage_messages"):
            return "You don't have the Manage Messages permission."
        count = max(1, min(100, int(inp.get("count") or 5)))
        deleted = await interaction.channel.purge(limit=count)
        return f"🧹 Deleted {len(deleted)} message(s)."

    if action == "slowmode":
        if not _perm("manage_channels"):
            return "You don't have the Manage Channels permission."
        seconds = max(0, min(21600, int(inp.get("seconds") or 0)))
        await interaction.channel.edit(slowmode_delay=seconds)
        return f"🐢 Slowmode set to {seconds}s."

    if action == "lock":
        if not _perm("manage_channels"):
            return "You don't have the Manage Channels permission."
        overwrite = interaction.channel.overwrites_for(guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_overwrites(guild.default_role, overwrite)
        return "🔒 Channel locked."

    if action == "unlock":
        if not _perm("manage_channels"):
            return "You don't have the Manage Channels permission."
        overwrite = interaction.channel.overwrites_for(guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_overwrites(guild.default_role, overwrite)
        return "🔓 Channel unlocked."

    if action == "nickname":
        if not _perm("manage_nicknames"):
            return "You don't have the Manage Nicknames permission."
        member = inp.get("member")
        new_nick = str(inp.get("nickname") or "").strip() or None
        await member.edit(nick=new_nick)
        return f"✏️ Nickname for {member.display_name} → {new_nick or '(reset)'}"

    return f"Moderation action '{action}' isn't recognized."


async def fun(payload: Dict[str, Any]) -> Any:
    action = _d(payload, "entry", "action")
    inp = _d(payload, "input") or {}
    text = _input_text(payload)

    def _target_name() -> str:
        t = inp.get("user")
        if t is not None:
            return getattr(t, "display_name", None) or str(t)
        return text or "target"

    if action == "eightball":
        if not text:
            return "Ask a question first."
        return f"🎱 {random.choice(EIGHTBALL)}"
    if action == "dice":
        sides = max(2, min(1000, int(inp.get("sides") or 6)))
        return f"🎲 {random.randint(1, sides)} (d{sides})"
    if action == "coinflip":
        return f"🪙 {random.choice(['HEADS', 'TAILS'])}"
    if action == "rps":
        choice = (str(inp.get("choice") or "") or text or "rock").lower()
        if choice not in RPS:
            return "Pick rock, paper, or scissors."
        bot = random.choice(list(RPS))
        win = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
        outcome = "It's a tie! 🤝" if bot == choice else (
            "You win! 🎉" if win[choice] == bot else "I win! 🤖"
        )
        return f"{RPS[choice]} vs {RPS[bot]} — {outcome}"
    if action == "say":
        if not text:
            return "Give me some text to say."
        return text[:1900]
    if action == "clap":
        if not text:
            return "Give me some text."
        return "👏 " + " 👏 ".join(text.split()) + " 👏"
    if action == "pick":
        opts = [o.strip() for o in re.split(r"[,|/]", text) if o.strip()]
        if len(opts) < 2:
            return "Give me a few options, e.g. 'pizza, sushi, ramen'."
        return f"👉 I pick **{random.choice(opts)}**"
    if action in ("ship", "lovecalc"):
        names = [o.strip() for o in re.split(r"[,|/xX×]", text) if o.strip()]
        if len(names) < 2:
            return "Give me two names, e.g. 'alex, sam'."
        score = random.randint(0, 100)
        meter = "❤️" * max(1, score // 10) + "🖤" * (10 - max(1, score // 10))
        return f"💖 {names[0]} + {names[1]} = **{score}%**\n{meter}"
    if action == "compliment":
        return f"💕 {_target_name()}: {random.choice(COMPLIMENTS)}"
    if action == "insult":
        return f"🔥 {_target_name()}: {random.choice(INSULTS)} (just kidding)"
    if action == "fakehack":
        steps = [
            "Searching for wifi signal...", "Bypassing firewall...", "Downloading RAM...",
            "Bypassing mainframe...", "Access granted.",
        ]
        return f"💻 **Hacking {_target_name()}...**\n" + "\n".join(f"`> {s}`" for s in steps) + "\n✅ Hack successful (not real, relax)."
    if action == "rate":
        return f"⭐ {_target_name()} gets a rating of **{random.randint(1, 10)}/10**"
    if action == "wyr":
        return f"🤔 {random.choice(WYR)}"
    if action == "topic":
        return f"💬 Today's topic: {random.choice(TOPICS)}"
    if action == "quote":
        q, who = random.choice(QUOTES)
        return f"❝{q}❞ — **{who}**"
    if action == "joke":
        return f"😂 {random.choice(JOKES)}"
    if action == "pun":
        return f"😏 {random.choice(PUNS)}"
    if action == "fact":
        return f"🧠 {random.choice(FACTS)}"
    if action == "fortune":
        return f"🥠 {random.choice(FORTUNES)}"
    if action == "meme":
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://meme-api.com/gimme",
                                       timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
            return {"content": f"😂 **{data.get('title', 'meme')}**", "image": data.get("url")}
        except Exception:
            return "The meme service is down right now. Try again later."
    if action == "catfact":
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://catfact.ninja/fact",
                                       timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
            return f"🐱 {data.get('fact', 'Cats are cute.')}"
        except Exception:
            return "The cat facts service is down right now."
    if action in ("slap", "hug", "poke"):
        t = inp.get("user")
        if t is None:
            return "Tag the person first."
        actor = payload.get("_actor_name") or "Someone"
        emoji = {"slap": "👋", "hug": "🤗", "poke": "👉"}[action]
        verb = {"slap": "slaps", "hug": "hugs", "poke": "pokes"}[action]
        return f"{emoji} **{actor}** {verb} **{t.display_name}**!"
    return f"Fun action '{action}' doesn't exist yet."

GAMES: Dict[int, Dict[str, Any]] = {}


def _gkey(payload: Dict[str, Any]) -> int:
    return int(_d(payload, "discord", "channel_id") or 0)


async def game(payload: Dict[str, Any]) -> Any:
    action = _d(payload, "entry", "action")
    inp = _d(payload, "input") or {}
    key = _gkey(payload)
    g = GAMES.get(key, {})

    if action == "trivia":
        if g.get("type") == "trivia" and inp.get("guess"):
            guess = str(inp.get("guess")).lower().strip()
            if guess in g["answers"]:
                GAMES.pop(key, None)
                return f"✅ Correct! The answer was **{g['answer']}**. Point goes to <@{payload['discord']['user_id']}>!"
            return f"❌ Not quite. Hint: **{g['answer'][:1]}...** — try `/games trivia` again with `guess`."
        q = random.choice(TRIVIA)
        GAMES[key] = {"type": "trivia", "answers": q[1], "answer": q[2]}
        return f"🧠 **Trivia:** {q[0]}\n_(answer with `/games trivia` + `guess:<answer>`)_"

    if action == "hangman":
        guess_text = str(inp.get("guess") or "").strip()
        if not guess_text:
            word = random.choice(HANGMAN_WORDS).lower()
            GAMES[key] = {"type": "hangman", "word": word, "guessed": set(), "tries": 6}
            g = GAMES[key]
        else:
            g = GAMES.get(key)
            if not g or g.get("type") != "hangman":
                return "There's no hangman game running. Start one with `/games hangman` (no guess)."
            ch = guess_text.lower()
            if len(ch) == 1:
                g["guessed"].add(ch)
            elif ch == g["word"]:
                GAMES.pop(key, None)
                return f"🎉 You got the whole word! **{g['word']}**"
            else:
                g["tries"] -= 1
        mask = "".join(c if c in g["guessed"] else "_" for c in g["word"])
        if "_" not in mask:
            GAMES.pop(key, None)
            return f"🎉 Solved! The word was: **{g['word']}**"
        if g["tries"] <= 0:
            word = g["word"]
            GAMES.pop(key, None)
            return f"💀 You lost! The word was: **{word}**"
        return f"🎭 `{mask}` — lives left: {'❤️' * g['tries']} — guess with `/games hangman guess:<letter>`"

    if action == "numberguess":
        if not g or g.get("type") != "numberguess":
            GAMES[key] = {"type": "numberguess", "n": random.randint(1, 100), "tries": 7}
            return "🔢 I'm thinking of a number between 1-100. Guess with `/games numberguess guess:<number>` (7 lives)."
        guess = inp.get("guess")
        if guess is None:
            return "Give me your guess."
        g["tries"] -= 1
        n = g["n"]
        if int(guess) == n:
            GAMES.pop(key, None)
            return f"🎉 **{n}** is correct! You win!"
        if g["tries"] <= 0:
            GAMES.pop(key, None)
            return f"💀 Out of lives. The number was **{n}**."
        hint = "too high 📈" if int(guess) > n else "too low 📉"
        return f"❌ {hint} — lives left: {g['tries']}"

    if action in ("mathquiz", "mathanswer"):
        g = GAMES.get(key)
        if inp.get("answer") is not None and g and g.get("type") == "math":
            try:
                if int(inp["answer"]) == g["answer"]:
                    GAMES.pop(key, None)
                    return f"✅ Correct! {g['answer']} 🎉"
            except (TypeError, ValueError):
                pass
            return "❌ Not yet. Try again (the question is still active)."
        a, b = random.randint(2, 15), random.randint(2, 15)
        op = random.choice(["+", "-", "*"])
        answer = a + b if op == "+" else (a - b if op == "-" else a * b)
        GAMES[key] = {"type": "math", "answer": answer}
        return f"🧮 What's **{a} {op} {b}**? Answer with `/mathquiz answer:<answer>`."

    if action == "duel":
        return await fun({**payload, "entry": {**payload["entry"], "action": "rps"}})

    return f"Game '{action}' doesn't exist yet."


def _eco_user(store: JSONStore, user_id: int) -> Dict[str, Any]:
    data = store.read()
    u = data.get(str(user_id))
    if not u:
        u = {"balance": 100, "daily": 0.0, "work": 0.0, "items": []}
    return dict(u)


async def eco(payload: Dict[str, Any]) -> Any:
    action = _d(payload, "entry", "action")
    inp = _d(payload, "input") or {}
    user_id = int(_d(payload, "discord", "user_id") or 0)
    store: JSONStore = payload["_economy"]
    COOLDOWN_DAILY, COOLDOWN_WORK = 20 * 3600, 3600

    def _save(u: Dict[str, Any]) -> None:
        store.update(lambda d: d.__setitem__(str(user_id), u))

    u = _eco_user(store, user_id)

    if action == "daily":
        if _now() - u["daily"] < COOLDOWN_DAILY:
            left = int((COOLDOWN_DAILY - (_now() - u["daily"])) / 3600) + 1
            return f"⏳ You've already claimed your daily. Wait ~{left} more hour(s)."
        u["daily"] = _now()
        u["balance"] += 100
        _save(u)
        return f"🎁 +100 daily coins! Balance: **{u['balance']}**"
    if action == "balance":
        target = inp.get("user")
        if target is not None:
            t = _eco_user(store, int(target.id))
            return f"💰 **{target.display_name}**: {t['balance']} coins, items: {len(t.get('items', []))}"
        return f"💰 You have **{u['balance']}** coins, items: {len(u.get('items', []))}"
    if action == "work":
        if _now() - u["work"] < COOLDOWN_WORK:
            return "You just finished work — wait 1 hour for the cooldown to reset."
        u["work"] = _now()
        pay = random.randint(20, 80)
        u["balance"] += pay
        _save(u)
        return f"Work done! +{pay} coins. Balance: **{u['balance']}**"
    if action == "gamble":
        try:
            amount = int(inp.get("amount") or 0)
        except (TypeError, ValueError):
            return "Invalid gamble amount."
        if amount <= 0 or amount > u["balance"]:
            return "Invalid gamble amount."
        if random.random() < 0.45:
            u["balance"] += amount
            _save(u)
            return f"Jackpot! +{amount}. Balance: **{u['balance']}**"
        u["balance"] -= amount
        _save(u)
        return f"You lost... -{amount}. Balance: **{u['balance']}**"
    if action == "slots":
        try:
            amount = int(inp.get("amount") or 0)
        except (TypeError, ValueError):
            return "Invalid bet amount."
        if amount <= 0 or amount > u["balance"]:
            return "Invalid bet amount or insufficient coins."
        reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        display = " | ".join(reels)
        if reels[0] == reels[1] == reels[2]:
            u["balance"] += amount * 4
            _save(u)
            return f"{display} — jackpot! +{amount * 4}. Balance: **{u['balance']}**"
        if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            u["balance"] += amount
            _save(u)
            return f"{display} — pair! +{amount}. Balance: **{u['balance']}**"
        u["balance"] -= amount
        _save(u)
        return f"{display} — no luck. -{amount}. Balance: **{u['balance']}**"
    if action == "rob":
        target = inp.get("user")
        if target is None:
            return "Who do you want to rob?"
        t_id = int(target.id)
        if t_id == user_id:
            return "You can't rob yourself."
        t = _eco_user(store, t_id)
        if t["balance"] < 50:
            return f"**{target.display_name}** doesn't have anything worth robbing."
        if random.random() < 0.5:
            stolen = random.randint(10, min(200, t["balance"]))
            t["balance"] -= stolen
            u["balance"] += stolen
            store.update(lambda d: d.__setitem__(str(t_id), t))
            _save(u)
            return f"Success! Stole {stolen} coins from **{target.display_name}**!"
        fine = 30
        u["balance"] = max(0, u["balance"] - fine)
        _save(u)
        return f"Caught! Fined {fine} coins."
    if action == "gift":
        target = inp.get("user")
        if target is None:
            return "Who do you want to send coins to?"
        t_id = int(target.id)
        if t_id == user_id:
            return "You can't gift coins to yourself."
        try:
            amount = int(inp.get("amount") or 0)
        except (TypeError, ValueError):
            return "Invalid gift amount."
        if amount <= 0 or amount > u["balance"]:
            return "Invalid gift amount or insufficient coins."
        t = _eco_user(store, t_id)
        u["balance"] -= amount
        t["balance"] += amount
        store.update(lambda d: d.__setitem__(str(t_id), t))
        _save(u)
        return f"🎁 You gave **{amount}** coins to **{target.display_name}**."
    if action == "shop":
        lines = [f"**Market** — your coins: {u['balance']}", "```"]
        for item, price in SHOP_ITEMS.items():
            lines.append(f"{item:<20} {price} coins")
        lines.append("```")
        lines.append("Buy: `/eco buy item:<name>`")
        return "\n".join(lines)
    if action == "buy":
        item = str(inp.get("item") or "").strip().lower()
        if item not in SHOP_ITEMS:
            return f"Item '{item}' isn't in the shop catalog. See `/eco shop`."
        if u["balance"] < SHOP_ITEMS[item]:
            return "Insufficient funds — go work first."
        u["balance"] -= SHOP_ITEMS[item]
        u.setdefault("items", []).append(item)
        _save(u)
        return f"You bought **{item}**. Balance: **{u['balance']}**"
    if action == "leaderboard":
        data = store.read()
        top = sorted(data.items(), key=lambda kv: kv[1].get("balance", 0), reverse=True)[:10]
        if not top:
            return "No one has any coins yet."
        lines = ["Coin leaderboard"]
        for i, (uid, ud) in enumerate(top, 1):
            lines.append(f"{i}. <@{uid}> — {ud.get('balance', 0)} coins")
        return "\n".join(lines)
    return f"Economy action '{action}' not found."


async def levels(payload: Dict[str, Any]) -> Any:
    action = _d(payload, "entry", "action")
    xp_store: JSONStore = payload["_xp"]
    user_id = int(_d(payload, "discord", "user_id") or 0)
    data = xp_store.read()

    if action == "track":
        gained = random.randint(5, 15)
        cur = data.get(str(user_id), 0) + gained

        def _set_xp(d: dict) -> dict:
            d[str(user_id)] = cur
            return d

        xp_store.update(_set_xp)
        return {"level": cur // 100, "xp": cur, "ephemeral": True}

    if action == "rank":
        if str(user_id) not in data:
            return "Get active and start earning XP first."
        xp = data[str(user_id)]
        return f"Level **{xp // 100}** — {xp} XP (next level in {100 - xp % 100} XP)"

    if action == "leaderboard":
        if not data:
            return "No XP recorded yet."
        top = sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:10]
        lines = ["Leaderboard"]
        for i, (uid, xp) in enumerate(top, 1):
            lines.append(f"{i}. <@{uid}> — level {xp // 100} ({xp} XP)")
        return "\n".join(lines)
    return f"Levels action '{action}' not found."


async def social(payload: Dict[str, Any]) -> Any:
    action = _d(payload, "entry", "action")
    inp = _d(payload, "input") or {}
    guild_id = str(_d(payload, "discord", "guild_id") or 0)
    store: JSONStore = payload["_social"]

    if action in ("welcome", "goodbye"):
        updates: Dict[str, Any] = {}
        if inp.get("channel") is not None:
            updates[f"{action}_channel"] = int(inp["channel"].id)
        if inp.get("message"):
            updates[f"{action}_message"] = str(inp["message"])

        def _apply(d: dict) -> dict:
            d.setdefault(guild_id, {}).update(updates)
            return d

        store.update(_apply)
        cfg = store.read().get(guild_id, {})
        return {"content": f"**{action}** config saved: `{cfg}`"}

    if action == "autorole":
        if inp.get("role") is None:
            return "Specify the role."

        def _set_role(d: dict) -> dict:
            d.setdefault(guild_id, {})["autorole_role"] = int(inp["role"].id)
            return d

        store.update(_set_role)
        return {"content": f"Autorole saved: {inp['role'].name}"}

    if action == "announce":
        text = str(inp.get("text") or "").strip()
        if not text:
            return "Provide the announcement text."
        return {"announce": text}

    if action == "greet":
        who = inp.get("user")
        name = who.display_name if who is not None else str(inp.get("username") or "member")
        msg = store.read().get(guild_id, {}).get("welcome_message") or "Welcome {user} to the server!"
        return msg.replace("{user}", name)

    return f"Social action '{action}' not implemented yet."


async def util(payload: Dict[str, Any]) -> Any:
    action = _d(payload, "entry", "action")
    inp = _d(payload, "input") or {}
    interaction = payload.get("interaction")
    catalog_count = payload.get("_catalog_count", "?")

    if action == "poll":
        question = str(inp.get("question") or "").strip()
        if not question:
            return "Provide a poll question."
        return {"poll": question}
    if action == "remind":
        minutes = int(inp.get("minutes") or 0)
        text = str(inp.get("text") or "").strip() or "reminder"
        if minutes <= 0:
            return "Provide a valid duration in minutes."
        reminders: JSONStore = payload["_reminders"]

        def _add_reminder(d: dict) -> dict:
            d.setdefault("items", []).append(
                {
                    "user_id": payload["discord"]["user_id"],
                    "channel_id": payload["discord"]["channel_id"],
                    "due": _now() + minutes * 60,
                    "text": text,
                }
            )
            return d

        reminders.update(_add_reminder)
        return f"Got it: I'll remind you about **{text}** in {minutes} minutes."
    if action == "reminders-list":
        reminders: JSONStore = payload["_reminders"]
        uid = payload["discord"]["user_id"]
        items = [r for r in reminders.read().get("items", []) if r.get("user_id") == uid]
        if not items:
            return "You don't have any active reminders."
        lines = ["Your reminders:"]
        for r in items:
            due = dt.datetime.fromtimestamp(r["due"]).strftime("%d/%m %H:%M")
            lines.append(f"- **{r['text']}** (at {due})")
        return "\n".join(lines)
    if action == "serverinfo":
        g = interaction.guild
        return {
            "title": g.name,
            "fields": [
                ("Members", str(g.member_count)),
                ("Created", str(g.created_at.date())),
                ("Channels", str(len(g.channels))),
                ("Roles", str(len(g.roles))),
            ],
        }
    if action == "membercount":
        return f"**{interaction.guild.name}** has {interaction.guild.member_count} members."
    if action == "servercreated":
        return f"**{interaction.guild.name}** was created on {interaction.guild.created_at.date()}."
    if action == "userinfo":
        u = inp.get("user") or interaction.user
        return {
            "title": str(u),
            "fields": [("ID", str(u.id)), ("Joined Discord", str(u.created_at.date()))],
            "image": str(u.display_avatar.url),
        }
    if action == "avatar":
        u = inp.get("user") or interaction.user
        return {"image": str(u.display_avatar.url), "content": f"Avatar for **{u.display_name}**"}
    if action == "banner":
        u = inp.get("user") or interaction.user
        if u.banner is None:
            return f"**{u.display_name}** has no banner."
        return {"image": str(u.banner.url), "content": f"Banner for **{u.display_name}**"}
    if action == "servericon":
        if interaction.guild.icon is None:
            return "This server doesn't have an icon set."
        return {"image": str(interaction.guild.icon.url), "content": f"**{interaction.guild.name}**"}
    if action == "ping":
        return "Pong, up and healthy (probably)."
    if action == "uptime":
        up = payload.get("_uptime", 0)
        h, m = int(up // 3600), int(up % 3600 // 60)
        return f"Uptime: {h}h {m}m — {catalog_count} pipelines in catalog."
    if action == "invite":
        return "Find the invite link in the Discord Developer Portal for more setup options."
    if action == "embed":
        title = str(inp.get("title") or "Embed")
        text = str(inp.get("text") or "")
        return {"title": title, "content": text or None}
    if action == "help":
        return {
            "content": "All of these features are controlled by an admin — ask them for setup help. "
                       "Available commands: `/ai`, `/music`, `/mod`, `/fun`, `/games`, `/eco`, `/social`, `/util`."
        }
    if action == "random-number":
        lo, hi = int(inp.get("min") or 1), int(inp.get("max") or 100)
        return f"{random.randint(min(lo, hi), max(lo, hi))}"
    if action == "random-color":
        c = "%06x" % random.randint(0, 0xFFFFFF)
        return {"content": f"`#{c}`", "image": f"https://singlecolorimage.com/get/{c}/200x100"}
    if action == "calc":
        expr = str(inp.get("expression") or "").replace("^", "**")
        if not re.fullmatch(r"[0-9+\-*/(). %]+", expr or ""):
            return "Invalid expression."
        try:
            val = eval(expr, {"__builtins__": {}}, {})
        except Exception as exc:
            return f"Couldn't evaluate that: {exc.__class__.__name__}"
        return f"{expr} = **{val}**"
    if action == "define":
        word = str(inp.get("word") or "").strip()
        if not word:
            return "Provide a word to look up."
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}",
                                 timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json()
            if isinstance(data, dict):
                return f"'{word}' wasn't found in the dictionary."
            meaning = data[0]["meanings"][0]["definitions"][0]["definition"]
            return f"**{word}**: {meaning}"
        except Exception:
            return "The dictionary service is down right now."
    if action == "weather":
        city = str(inp.get("city") or "").strip()
        if not city:
            return "Provide a city name."
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1",
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as r:
                    geo = await r.json()
                if not geo.get("results"):
                    return f"Couldn't find the city '{city}'."
                lat, lon = geo["results"][0]["latitude"], geo["results"][0]["longitude"]
                async with s.get(
                    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true",
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as r:
                    wx = await r.json()
            cw = wx["current_weather"]
            return f"{city}: {cw['temperature']}°C, wind {cw['windspeed']} km/h"
        except Exception:
            return "The weather service is down right now."
    if action == "time":
        return f"{dt.datetime.now().strftime('%H:%M:%S')} (server time)"
    return f"Util action '{action}' not found."


def register_all(engine, secrets: ConfigStore, runtime: RuntimeConfig, catalog) -> Dict[str, Any]:
    stores = {
        "_economy": JSONStore("economy"),
        "_warnings": JSONStore("warnings"),
        "_xp": JSONStore("xp"),
        "_social": JSONStore("social"),
        "_reminders": JSONStore("reminders"),
    }

    def bind(fn, **extra):
        async def _wrapped(payload: Dict[str, Any]) -> Any:
            full = {
                **payload,
                "_secrets": secrets,
                "_runtime": runtime,
                **stores,
                **extra,
            }
            return await fn(full)
        return _wrapped

    engine.register("ai_chat", bind(ai_chat))
    engine.register("ai_task", bind(ai_task))
    engine.register("music_resolve", bind(music_resolve))
    engine.register("mod", bind(mod))
    engine.register("fun", bind(fun))
    engine.register("game", bind(game))
    engine.register("eco", bind(eco))
    engine.register("levels", bind(levels))
    engine.register("social", bind(social))
    engine.register("util", bind(util, _catalog_count=catalog.count()))
    return stores
