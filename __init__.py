"""
Ce programme est régi par la licence CeCILL soumise au droit français et
respectant les principes de diffusion des logiciels libres. Vous pouvez
utiliser, modifier et/ou redistribuer ce programme sous les conditions
de la licence CeCILL diffusée sur le site "http://www.cecill.info".
"""

# Requirements
# ------------
# - Python 3.12
# Standard libraries

# External libraries
import discord
from discord.ext import commands
from LRFutils import logs

# Project modules
import allay
from .src.discord_cog import *

# Infos
# -----

version = "0.0.1"
icon = "📊"
name = "Prometheus"


# Setup
# -----

async def setup(bot: allay.Bot):
    logs.info(f"Loading {icon} {name} v{version}...")
    await bot.add_cog(PromCog(bot), icon=icon, display_name=name)