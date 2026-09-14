from __future__ import annotations
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import discord
from discord import app_commands
from .catalog import Catalog
from .config import ConfigStore, RuntimeConfig
from .engine import PipelineClient
from .pipelines import handlers

logger = logging.getLogger("discord_client")

OPTION_TYPES = {
    "text": "str",
    "int": "int",
    "member": "discord.Member",
    "user": "discord.User",
    "channel": "discord.TextChannel",
    "role": "discord.Role",
}

SLOW_TYPES = {"ai_chat", "ai_task", "music"}
SLOW_ACTIONS = {"weather", "define", "meme"}

GROUP_DESCRIPTIONS = {
    "ai": "AI helper commands",
    "write": "AI writing commands",
    "mod": "Moderation commands",
    "fun": "Fun commands",
    "games": "Mini games",
    "eco": "Economy commands",
    "levels": "XP level commands",
    "social": "Server social setup",
    "util": "Utility commands",
}


class DiscordClient:

    def __init__(
        self,
        pipeline_client: PipelineClient,
        config_store: ConfigStore,
        runtime: RuntimeConfig,
        catalog: Catalog,
        stores: Dict[str, Any],
    ) -> None:
        self.pipeline_client = pipeline_client
        self.config_store = config_store
        self.runtime = runtime
        self.catalog = catalog
        self.stores = stores
        self.status = "OFFLINE"
        self.started_at: Optional[float] = None
        self._built: List[str] = []

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)

        self._register_events()

    def _build_callback(self, entry: Dict[str, Any]):
        opts = [o for o in entry.get("options", []) if o.get("name")]
        sig = ""
        for o in opts:
            ann = OPTION_TYPES.get(o.get("type", "text"), "str")
            default = "" if o.get("required", True) else "=None"
            sig += f", {o['name']}: {ann}{default}"
        args = ", ".join(f"'{o['name']}': {o['name']}" for o in opts)
        src = (
            f"async def _cb(interaction: discord.Interaction{sig}):\n"
            f"    return await _run(interaction, _entry, {{{args}}})\n"
        )
        ns: Dict[str, Any] = {"discord": discord, "_run": self._run_command, "_entry": entry}
        exec(src, ns)
        return ns["_cb"]

    def build_commands(self) -> int:
        for name in self._built:
            try:
                self.tree.remove_command(name)
            except Exception:
                pass
        self._built = []
        groups: Dict[str, app_commands.Group] = {}
        total = 0

        for entry in self.catalog.all():
            if entry.get("hidden") or not entry.get("command"):
                continue
            if not self.runtime.is_enabled(entry["id"]):
                continue
            cb = self._build_callback(entry)
            descs = {o["name"]: o.get("desc", o["name"]) for o in entry.get("options", [])}
            if descs:
                cb = app_commands.describe(**descs)(cb)
            if entry.get("guild_only"):
                cb = app_commands.guild_only()(cb)
            cmd = app_commands.Command(
                name=entry["command"],
                description=(entry.get("description") or entry["command"])[:100],
                callback=cb,
            )
            if entry.get("perm"):
                cmd.default_permissions = discord.Permissions(**{entry["perm"]: True})
            group_name = entry.get("group")
            if entry.get("marquee") or not group_name:
                try:
                    self.tree.add_command(cmd)
                except Exception as exc:
                    logger.warning("Skipping /%s: %s", entry["command"], exc)
                    continue
                self._built.append(entry["command"])
                total += 1
                continue
            g = groups.get(group_name)
            if g is None:
                g = app_commands.Group(
                    name=group_name,
                    description=GROUP_DESCRIPTIONS.get(group_name, f"{group_name} commands"),
                )
                groups[group_name] = g
            try:
                g.add_command(cmd)
            except Exception as exc:
                logger.warning("Skipping /%s %s: %s", group_name, entry["command"], exc)
                continue
            total += 1

        for gname, g in groups.items():
            try:
                self.tree.add_command(g)
                self._built.append(gname)
            except Exception as exc:
                logger.warning("Skipping group /%s: %s", gname, exc)

        logger.info(
            "Built %d commands (%d top-level entries incl. %d groups)",
            total, len(self._built), len(groups),
        )
        return total

    async def resync(self) -> None:
        self.build_commands()
        if self.client.is_ready():
            try:
                await self.tree.sync()
                logger.info("Command tree re-synced")
            except Exception:
                logger.exception("Failed to re-sync command tree")

    def request_resync(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._safe_resync())

    async def _safe_resync(self) -> None:
        try:
            await self.resync()
        except Exception:
            logger.exception("Resync failed")

    def _register_events(self) -> None:
        @self.client.event
        async def on_ready() -> None:
            self.status = "ONLINE"
            if self.started_at is None:
                self.started_at = time.time()
            logger.info("Discord connected as %s", self.client.user)
            if not self._built:
                self.build_commands()
            try:
                await self.tree.sync()
            except Exception:
                logger.exception("Failed to sync command tree")

        @self.client.event
        async def on_disconnect() -> None:
            self.status = "OFFLINE"

        @self.client.event
        async def on_message(message: discord.Message) -> None:
            if message.author.bot or self.client.user is None:
                return
            if message.guild is not None:
                try:
                    await self.pipeline_client.run(
                        "levels",
                        {
                            "entry": {"action": "track", "type": "levels"},
                            "interaction": None,
                            "discord": {
                                "user_id": message.author.id,
                                "username": str(message.author),
                                "guild_id": message.guild.id,
                                "channel_id": message.channel.id,
                            },
                        },
                    )
                except Exception:
                    pass
            if self.client.user not in message.mentions:
                return
            content = message.content
            for mention in (f"<@{self.client.user.id}>", f"<@!{self.client.user.id}>"):
                content = content.replace(mention, "")
            content = content.strip()
            if not content:
                return
            payload = {
                "entry": {"action": "chat", "type": "ai_chat"},
                "input": {"message": content},
                "interaction": None,
                "discord": {
                    "user_id": message.author.id,
                    "username": str(message.author),
                    "guild_id": message.guild.id if message.guild else None,
                    "channel_id": message.channel.id,
                },
                "_actor_name": message.author.display_name,
            }
            async with message.channel.typing():
                try:
                    reply = await self.pipeline_client.run("ai_chat", payload)
                    await message.reply(str(reply)[:2000], mention_author=False)
                except Exception:
                    logger.exception("Mention chat failed")
                    await message.reply("Oops, the AI hit an error. Please try again.", mention_author=False)

        @self.client.event
        async def on_member_join(member: discord.Member) -> None:
            try:
                result = await self.pipeline_client.run(
                    "social",
                    {
                        "entry": {"action": "greet", "type": "social"},
                        "input": {"user": member},
                        "interaction": None,
                        "discord": {
                            "user_id": member.id,
                            "username": str(member),
                            "guild_id": member.guild.id,
                            "channel_id": member.guild.system_channel.id if member.guild.system_channel else None,
                        },
                    },
                )
                channel = member.guild.system_channel
                if channel is not None and isinstance(result, str):
                    await channel.send(result)
            except Exception:
                logger.exception("on_member_join handling failed")

    async def _run_command(self, interaction: discord.Interaction, entry: Dict[str, Any], kwargs: Dict[str, Any]) -> None:
        payload: Dict[str, Any] = {
            "entry": entry,
            "input": {k: v for k, v in kwargs.items() if v is not None},
            "interaction": interaction,
            "discord": {
                "user_id": interaction.user.id,
                "username": str(interaction.user),
                "guild_id": interaction.guild_id,
                "channel_id": interaction.channel_id,
            },
            "_actor_name": interaction.user.display_name,
            "_uptime": (time.time() - self.started_at) if self.started_at else 0,
        }
        slow = entry.get("type") in SLOW_TYPES or entry.get("action") in SLOW_ACTIONS
        try:
            if slow:
                await interaction.response.defer(thinking=True)
            result = await self.pipeline_client.run(entry["type"], payload)
            await self._render(interaction, result, deferred=slow)
        except ValueError as exc:
            await self._safe_send(interaction, f"⚠️ {exc}", deferred=slow)
        except Exception:
            logger.exception("Command %s failed", entry.get("command"))
            await self._safe_send(interaction, "Oops, something went wrong running that. Please try again later.", deferred=slow)

    async def _safe_send(self, interaction: discord.Interaction, text: str, deferred: bool, embed: Optional[discord.Embed] = None, ephemeral: bool = False) -> None:
        try:
            if deferred:
                if embed is not None:
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    await interaction.followup.send(text, ephemeral=ephemeral)
            else:
                if embed is not None:
                    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
                else:
                    await interaction.response.send_message(text, ephemeral=ephemeral)
        except Exception:
            logger.exception("Failed to send response")

    async def _render(self, interaction: discord.Interaction, result: Any, deferred: bool) -> None:
        if isinstance(result, dict):
            ephemeral = bool(result.get("ephemeral"))
            if result.get("poll"):
                question = str(result["poll"])
                if deferred:
                    m = await interaction.followup.send(question)
                else:
                    await interaction.response.send_message(question)
                    m = await interaction.original_response()
                try:
                    for e in ("1️⃣", "2️⃣", "3️⃣"):
                        await m.add_reaction(e)
                except Exception:
                    pass
                return
            if result.get("announce"):
                text = f"📢 **Announcement**\n{result['announce']}"
                await self._safe_send(interaction, text[:2000], deferred)
                return
            title = result.get("title")
            fields = result.get("fields") or []
            image = result.get("image")
            content = result.get("content")
            if title or fields or image:
                embed = discord.Embed(title=title or None, description=content or None)
                for name, value in fields:
                    embed.add_field(name=str(name), value=str(value), inline=True)
                if image:
                    embed.set_image(url=image)
                await self._safe_send(interaction, "", deferred, embed=embed, ephemeral=ephemeral)
                return
            if content:
                await self._safe_send(interaction, str(content)[:2000], deferred, ephemeral=ephemeral)
                return
            await self._safe_send(interaction, "✅ Done.", deferred, ephemeral=ephemeral)
        else:
            await self._safe_send(interaction, str(result)[:2000], deferred)

    async def reminder_loop(self) -> None:
        while not self.client.is_closed():
            try:
                due = handlers.pop_due_reminders(self.stores["_reminders"])
                for r in due:
                    ch = self.client.get_channel(int(r["channel_id"]))
                    if ch is not None:
                        await ch.send(f"⏰ <@{r['user_id']}> reminder: **{r['text']}**")
            except Exception:
                logger.exception("Reminder loop error")
            await asyncio.sleep(20)

    async def start(self) -> None:
        token = self.config_store.get("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("DISCORD_TOKEN isn't set yet (paste it in via the dashboard).")
        self.started_at = time.time()
        try:
            await self.client.start(token)
        finally:
            self.status = "OFFLINE"

    async def close(self) -> None:
        await handlers.close_music_connections()
        if not self.client.is_closed():
            await self.client.close()
        self.status = "OFFLINE"