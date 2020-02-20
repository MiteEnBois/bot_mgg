# bot.py

import asyncio
import os
import json
import yaml
import datetime
import discord
import time
import math
import re
import requests
from random import shuffle
import defusedxml.ElementTree
import xml.etree.ElementTree as ET
from copy import deepcopy
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

global NATION, PASSWORD, GUILD_ID, GUILD, CHANNEL_ISSUES_ID, CHANNEL, ISSUES, PATH, EMOJI, UPDATE, COOLDOWN_VOTE, RAPPEL
global EMOJI_VOTE, MIN_BEFORE_COOLDOWN, LIST_RANK_ID, RESULTS_XML, ROLE_PING, CURRENT_ID

UPDATE = 30
COOLDOWN_VOTE = 60*60*5
RAPPEL = 60*60
MIN_BEFORE_COOLDOWN = 5
CURRENT_ID = 0
CHANNEL = None
GUILD = None

ROLE_PING = "572159388865789987"
EMOJI_VOTE = ["☑️", "✅", "✔️"]
EMOJI = [":apple:", ":pineapple:", ":kiwi:", ":cherries:", ":banana:", ":eggplant:", ":tomato:", ":corn:", ":carrot:"]
NATION = 'controlistania'
PATH = 'vote.yml'
RESULTS_XML = ET.parse("test_result.xml")

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PASSWORD = os.getenv('PASSWORD')
GUILD_ID = os.getenv('GUILD')
CHANNEL_ISSUES_ID = os.getenv('CHANNEL_ISSUES')

bot = commands.Bot(command_prefix=';')

with open("list_rank.yml") as f:
    LIST_RANK_ID = yaml.load(f, Loader=yaml.FullLoader)
    f.close()


with open(PATH) as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    if data is not None:
        ISSUES = data
    else:
        ISSUES = {}
    f.close()


@bot.event
async def on_ready():
    print(f'{bot.user} is connected to the following guild:')
    for guild in bot.guilds:
        print(f'-{guild.name}')
    print(f'{bot.user} has started')


def backup():
    with open(PATH, mode="r+") as f:
        f.truncate(0)
        data = yaml.dump(ISSUES, f)
        f.close()


def embed(title="", description="", fv="", num=0, color=None, footer=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if num > len(EMOJI)+1:
        EMOJI[num] = ""
    if(num != 0):
        embed.add_field(name=f"{EMOJI[num-1]} OPTION {num}:", value=fv, inline=False)
    if footer is not None:
        embed.set_footer(text=footer)
    return embed


def duree(t):
    s = t % 60
    t = math.floor(t/60)
    m = t % 60
    t = math.floor(t/60)
    h = t % 24
    t = math.floor(t/24)
    txt = ""
    if h != 0:
        txt += f"{h}h"
    if m != 0 or h != 0:
        txt += f"{m}m"
    txt += f"{s}s"
    return txt


@bot.command(name='ping', help='Pong!')
async def ping(ctx):
    await ctx.send("Pong!")


@bot.command(name='start', help='Pong!')
async def start(ctx):
    await start_vote(ctx)


async def start_vote(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    global CHANNEL, GUILD
    CHANNEL = ctx.guild.get_channel(int(CHANNEL_ISSUES_ID))
    if CHANNEL is None:
        CHANNEL = ctx.channel
    if ctx.guild.id == GUILD_ID:
        GUILD = ctx.guild

    response = requests.get(
        f"https://www.nationstates.net/cgi-bin/api.cgi?nation={NATION}&q=issues",
        headers={
            'User-Agent': 'Controlistania Discord Bot - owner:timothee.bouvin@gmail.com',
            'X-Password': PASSWORD
        },
    )
    n = defusedxml.ElementTree.fromstring(response.text)

    issues = n.find('ISSUES').findall('ISSUE')
    issue = issues[0]
    issue_id = int(issue.get('id'))
    title = issue.find('TITLE').text
    text = issue.find("TEXT").text.replace("<i>", "*").replace("</i>", "*")
    msg = embed(title, text, color=0xdb151b, footer=f"ID : {issue_id}")
    title_message = await CHANNEL.send(embed=msg)

    shuffle(EMOJI)
    options = []
    i = 1
    for option in issue.findall('OPTION'):
        txt = option.text.replace("<i>", "*").replace("</i>", "*")
        print(txt)
        msgoption = embed(fv=txt, num=i, color=0xecb440)
        option_message = await CHANNEL.send(embed=msgoption)
        obj = {option_message.id: txt}
        options.append(obj)
        i += 1

    msg_info = f"**<@&{ROLE_PING}>, un nouveau vote est lancé!**\nVeuillez voter en mettant une réaction sous l'option de votre choix (Un vote par personne! En cas de multiple vote, la premiere option rencontrée sera prise et les autres seront ignorées)\n"
    msg_info += "Les emojis comptant pour le vote sont les suivants : "
    for i in EMOJI_VOTE:
        msg_info += f"{i} "
    msg_info += "; tout les autres emojis ne seront pas comptés\n"
    msg_info += f"Une fois que {MIN_BEFORE_COOLDOWN} personnes auront voté, une période de {duree(COOLDOWN_VOTE)} commencera, à la fin de laquelle les votes seront comptabilisé et envoyé au serveur.\n"
    await CHANNEL.send(msg_info)

    ISSUES[int(issue_id)] = {
        "title_msg_id": title_message.id,
        "title_text": title,
        "option_msg_id": options,
        "time_posted": time.time(),
        "time_start_countdown": 0,
        "option_taken": -2,
        "guild_id": CHANNEL.guild.id,
        "channel_id": CHANNEL.id
    }

    global CURRENT_ID
    CURRENT_ID = issue_id

    backup()

    verif.start(ctx)


async def launch_issue(issue, option):
    # response = requests.get(
    #     f"https://www.nationstates.net/cgi-bin/api.cgi?nation={NATION}&c=issue&issue={issue}&option={option}",
    #     headers={
    #         'User-Agent': 'Controlistania Discord Bot - owner:timothee.bouvin@gmail.com',
    #         'X-Password': PASSWORD
    #     },
    # )
    # return response
    return RESULTS_XML


async def count_votes(opt, channel):
    votes = []
    voters = []
    for o in opt:
        id_mes = 0
        for x, y in o.items():
            id_mes = x
        if x == 0:
            print("erreur id message")
            return

        mes = await channel.fetch_message(id_mes)
        count = 0
        for r in mes.reactions:
            if(str(r) in EMOJI_VOTE):
                async for user in r.users():
                    if user in voters:
                        continue
                    else:
                        voters.append(user)
                        count += 1
        votes.append(count)
    return votes


@tasks.loop(seconds=UPDATE)
async def verif(ctx):
    iss = ISSUES[CURRENT_ID]
    opt = iss["option_msg_id"]
    guild = GUILD
    channel = CHANNEL
    if iss["option_taken"] != -2:
        print("continue")
        return True
    if iss["time_start_countdown"] == 0:

        votes = await count_votes(opt, channel)
        # votes = [1, 0, 0]
        cvotes = 0
        for i in votes:
            cvotes += i
        print(f"{votes}")
        if cvotes >= MIN_BEFORE_COOLDOWN:
            ISSUES[CURRENT_ID]["time_start_countdown"] = time.time()
            iss["time_start_countdown"] = time.time()
            backup()
            print("start countdown")
            txt = f"Assez de personnes ont voté. Les votes seront comptés dans {duree(COOLDOWN_VOTE)}!\n"
            txt += f"Rendez-vous à {time.ctime(time.time()+COOLDOWN_VOTE)}"
            await channel.send(txt)
    else:
        print("verif2")
        tsc = math.floor(time.time()-iss["time_start_countdown"])
        if tsc < COOLDOWN_VOTE:
            temps_restant = COOLDOWN_VOTE-tsc
            if temps_restant <= RAPPEL and temps_restant >= (RAPPEL-UPDATE):
                print(f"{duree(RAPPEL)} avant vote")
                await channel.send(f"Il reste {duree(RAPPEL)} avant la fin du vote!")
            return True
        else:
            votes = await count_votes(opt, channel)
            print(votes)
            tp = math.floor(time.time()-iss["time_posted"])
            msg = "__**RESULTAT DES VOTES**__\n"
            msg += f"ID : {CURRENT_ID}\nTemps écoulé : **{duree(tp)}**\n"
            maxv = 0
            winv = -1
            numv = 0
            for x, v in enumerate(votes):
                if v == maxv:
                    numv += 1
                if v > maxv:
                    maxv = v
                    winv = x
                    numv = 1

                msg += f"Option {x+1} : {v} votes\n"
            if numv > 1:
                winv = -1
                msg += f"Egalité"
            else:
                msg += f"\n **Option gagnante : {winv+1} avec {maxv} votes**\n"
            ISSUES[CURRENT_ID]["option_taken"] = winv
            iss["option_taken"] = winv
            backup()
            await channel.send(msg)
            xml = await launch_issue(CURRENT_ID, winv)
            await results(channel, xml)
            verif.stop()
            return False


@bot.command(name='res', help='Pong!')
async def res(ctx):
    await results(ctx.channel, RESULTS_XML)


async def results(channel, xml):
    msg = ""
    # issue = RESULTS_XML.find("ISSUE")
    issue = xml.find("ISSUE")
    desc = issue.find("DESC").text
    id_issue = int(issue.get("id"))
    text_issue = ISSUES[id_issue]["title_text"]

    choice_issue = int(issue.get("choice"))
    text_option = ""
    for x, y in ISSUES[id_issue]["option_msg_id"][choice_issue].items():
        text_option = y
    msg += f"__**RESOLUTION DE PROBLEME**__\n"
    msg += f"Le problème **#{id_issue}** (*{text_issue}*) a été résolu via l'option **{choice_issue+1}**.\n"
    msg += f"**{desc.upper()}**\n"
    await channel.send(msg)

    msg = "**__Unlocks : __**\n"
    for unlock in issue.find("UNLOCKS"):
        msg += f"{unlock.tag.lower()} : {unlock.text}\n"
    msg += "**__Reclassification : __**\n"
    for r in issue.find("RECLASSIFICATIONS").findall("RECLASSIFY"):
        rtype = LIST_RANK_ID[int(r.get("type"))]
        fro = r.find("FROM").text
        to = r.find("TO").text
        msg += f"{rtype} : from {fro} to {to}\n"
    msg += "**__Headlines: __**\n"
    for h in issue.find("HEADLINES").findall("HEADLINE"):
        msg += f"{h.text}\n"
    npol = issue.find("NEW_POLICIES")
    if npol is not None:
        msg += "**__Nouvelles Stratégies : __**\n"
        for p in npol:
            msg += f"{p.tag} : {p.text}\n"
    rpol = issue.find("REMOVED_POLICIES")
    if rpol is not None:
        msg += "**__Stratégies Enlevées : __**\n"
        for p in rpol:
            msg += f"{p.tag} : {p.text}\n"
    await channel.send(msg)
    print(len(msg))

    msg = "**__CHANGEMENT DE RANGS__**\n```c++\n"

    for r in issue.find("RANKINGS").findall("RANK"):
        id_r = r.get("id")
        name = LIST_RANK_ID[int(id_r)]
        score = r.find("SCORE").text
        change = float(r.find("CHANGE").text)
        pchange = round(float(r.find("PCHANGE").text), 2)
        if change >= 0 or pchange >= 0:
            sousmsg = f"{name} : {score} (+{change} ; +{pchange}%)\n"
            # sousmsg = f"{name} : +{pchange}%)\n"
        else:
            sousmsg = f"{name} : {score} ({change} ; {pchange}%)\n"
            # sousmsg = f"{name} : {pchange}%)\n"
        if len(sousmsg)+len(msg) >= 1997:
            msg += "```"
            await channel.send(msg)
            msg = "```c++\n"+sousmsg
        else:
            msg += sousmsg
    if(len(msg) < 2000):
        await channel.send(msg+"```")
        print(len(msg))
    else:
        await channel.send(f"trop long({len(msg)}), print envoyé")
        print(msg)
bot.run(TOKEN)
