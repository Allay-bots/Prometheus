"""
Ce programme est régi par la licence CeCILL soumise au droit français et
respectant les principes de diffusion des logiciels libres. Vous pouvez
utiliser, modifier et/ou redistribuer ce programme sous les conditions
de la licence CeCILL diffusée sur le site "http://www.cecill.info".
"""

import hashlib
import re
# Requirements
# ------------
# - Python 3.12
# Standard libraries
import asyncio
from datetime import datetime

# Project modules
import allay
# External libraries
import discord
from prometheus_client import *
from discord.ext import commands, tasks


# Cog
# ---


class PromCog(commands.Cog):

    # SETUP
    # -----

    def __init__(self, bot):
        self.bot = bot
        self.start_date = datetime.now()

        try:
            self.polling_interval = int(allay.BotConfig.get("plugins.prometheus.polling_interval"))
            self.recalibration_interval = allay.BotConfig.get("plugins.prometheus.recalibration_interval")
        except ValueError:
            raise ValueError("Polling/recalibration intervals must be integers")

        try:
            self.prometheus_port = int(allay.BotConfig.get("plugins.prometheus.exporter_port"))
        except ValueError:
            raise ValueError("Prometheus port must be an integer")

        self.guilds = Gauge("discord_guilds", "Number of guilds")
        self.guild_names = Info("discord_guild_names", "Guild names", ["guild"])
        self.users = Gauge("discord_users", "Number of users per guild", ["guild"])
        self.online = Gauge("discord_online", "Number of online users per guild", ["guild"])
        self.channels = Gauge("discord_channels", "Number of channels per guild", ["guild"])
        self.threads = Gauge("discord_threads", "Number of threads per guild", ["guild"])
        self.messages_sent = Counter("discord_messages", "Number of messages sent in guild", ["guild"])
        self.messages_edited = Counter("discord_messages_edited", "Number of messages edited in guild", ["guild"])
        self.messages_deleted = Counter("discord_messages_deleted", "Number of messages deleted in guild", ["guild"])
        self.reactions = Counter("discord_reactions", "Number of reactions in guild", ["guild", "emoji"])

        self.latency = Gauge("discord_latency", "Bot latency")
        self.uptime = Gauge("discord_uptime", "Bot uptime")

    async def cog_load(self):
        self.start_prometheus()
        await self.setup_metrics()
        self.loop.change_interval(seconds=self.polling_interval)
        self.loop.start()
        self.recalibrate.change_interval(seconds=self.recalibration_interval)
        self.recalibrate.start()

    def start_prometheus(self):
        start_http_server(self.prometheus_port)

    async def setup_metrics(self):
        # clear all guild-related metrics
        self.guilds.set(0)
        self.users.clear()
        self.online.clear()
        self.channels.clear()
        self.threads.clear()
        for guild in self.bot.guilds:
            # simulate on_guild_join event for each guild
            await self.on_guild_join(guild)

    # EVENTS UPDATERS
    # ---------------

    @commands.Cog.listener()
    async def on_message(self, message):
        self.messages_sent.labels(message.guild.id).inc()

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        self.messages_edited.labels(before.guild.id).inc()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        self.messages_deleted.labels(message.guild.id).inc()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        print("Nouvelle réaction")
        # wait 10s and check if the reaction is still there
        user = await reaction.message.guild.fetch_member(user.id)
        await asyncio.sleep(10)
        users = [u async for u in reaction.users()]
        if not any(u.id == user.id for u in users):
            print("Réaction enlevée")
            return
        print("Réaction toujours là")
        self.reactions.labels(reaction.message.guild.id, reaction.emoji).inc()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        self.guilds.inc()
        self.guild_names.labels(guild.id).info({"name": guild.name})
        self.users.labels(guild.id).set(len(guild.members))
        self.online.labels(guild.id).set(len([m for m in guild.members if m.status != discord.Status.offline]))
        self.channels.labels(guild.id).set(len(guild.channels))
        self.threads.labels(guild.id).set(len(guild.threads))

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        self.guilds.dec()
        self.users.remove(guild.id)
        self.online.remove(guild.id)
        self.channels.remove(guild.id)
        self.threads.remove(guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.users.labels(member.guild.id).inc()
        if member.status != discord.Status.offline:
            self.online.labels(member.guild.id).inc()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        self.users.labels(member.guild.id).dec()
        if member.status != discord.Status.offline:
            self.online.labels(member.guild.id).dec()

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if before.status == discord.Status.offline and after.status != discord.Status.offline:
            self.online.labels(after.guild.id).inc()
        elif before.status != discord.Status.offline and after.status == discord.Status.offline:
            self.online.labels(after.guild.id).dec()

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        self.channels.labels(channel.guild.id).inc()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        self.channels.labels(channel.guild.id).dec()

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        self.threads.labels(thread.guild.id).inc()

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        self.threads.labels(thread.guild.id).dec()

    # SCHEDULED UPDATERS
    # ------------------

    @tasks.loop(seconds=60)
    async def loop(self):
        await self.update_metrics()

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    async def update_metrics(self):
        # uptime
        uptime = datetime.now() - self.start_date
        self.uptime.set(uptime.total_seconds())
        # latency
        self.latency.set(self.bot.latency)

    # RECALIBRATION
    # -------------
    @tasks.loop(seconds=3600)
    async def recalibrate(self):
        await self.setup_metrics()

    @recalibrate.before_loop
    async def before_recalibrate(self):
        await self.bot.wait_until_ready()
