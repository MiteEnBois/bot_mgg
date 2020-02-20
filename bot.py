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

# ----------------------------- SETUP VARIABLES GLOBALES ET BOT

global NATION, PASSWORD, GUILD_ID, GUILD, CHANNEL_ISSUES_ID, CHANNEL, ISSUES, PATH, EMOJI, UPDATE, COOLDOWN_VOTE, RAPPEL
global EMOJI_VOTE, MIN_BEFORE_COOLDOWN, LIST_RANK_ID, RESULTS_XML, ROLE_PING, CURRENT_ID, ISSUE_RESULTS

UPDATE = 10
COOLDOWN_VOTE = 60*60*3
RAPPEL = 60*60
MIN_BEFORE_COOLDOWN = 5
CURRENT_ID = 0
CHANNEL = None
GUILD = None
ISSUE_RESULTS = None

ROLE_PING = "671696364056477707"
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

# ----------------------------- LECTURE DES FICHIERS

# Charge la liste des rangs lors du lancement de l'application
with open("list_rank.yml") as f:
    LIST_RANK_ID = yaml.load(f, Loader=yaml.FullLoader)
    f.close()

# Charge le backup de la liste d'issue dans le dictionnaire ISSUES
with open(PATH) as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    if data is not None:
        ISSUES = data
    else:
        ISSUES = {}
    f.close()

# ----------------------------- FONCTIONS UTILITAIRES

# Enregistre dans un fichier le dictionnaire ISSUES


def backup():
    with open(PATH, mode="r+") as f:
        f.truncate(0)
        data = yaml.dump(ISSUES, f)
        f.close()


# Cree un objet Embed pour l'affichage sur discord
def embed(title="", description="", fv="", num=0, color=None, footer=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if num > len(EMOJI)+1:
        EMOJI[num] = ""
    if(num != 0):
        embed.add_field(name=f"{EMOJI[num-1]} OPTION {num}:", value=fv, inline=False)
    if footer is not None:
        embed.set_footer(text=footer)
    return embed


# Convertit une durée en seconde en string de style h m s
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

# ----------------------------- FONCTIONS GESTION DE VOTE

# Setup un vote et lance verif()


async def start_vote(ctx):
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


# Envoie le résultat du vote et retourne l'xml reçu grace à la requete
async def launch_issue(issue, option):
    response = requests.get(
        f"https://www.nationstates.net/cgi-bin/api.cgi?nation={NATION}&c=issue&issue={issue}&option={option}",
        headers={
            'User-Agent': 'Controlistania Discord Bot - owner:timothee.bouvin@gmail.com',
            'X-Password': PASSWORD
        },
    )
    global ISSUE_RESULTS
    ISSUE_RESULTS = response.text
    print(response.text)
    n = defusedxml.ElementTree.fromstring(response.text)
    return n
    # return RESULTS_XML


# Compte les votes de la listes de messages dans le canal "channel" et renvoie un tableau contenant le nombre de vote de chaque option
# Skip les votes d'un user ayant deja voté
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


# Conclut le vote. Utilise launch_issue() pour envoyer les résultats et obtenir le xml de retour, qu'il envoie ensuite à results()
# Stoppe de force verif()
async def end_votes(channel):
    iss = ISSUES[CURRENT_ID]
    if CURRENT_ID == 0 or iss["option_taken"] != -2:
        await channel.send("Pas de vote en cours, annulation de la commande")
        return
    votes = await count_votes(iss["option_msg_id"], channel)
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


# Boucle toutes les UPDATE secondes
# Gere les conditions de fin de vote
# Une fois que le bot est lancé, vérifie si le nombre de vote est suffisent
# Si assez de gens ont votés, un temps limite est décidé (les votes ne seront plus comptés jusqu'à la fin du vote)
# Quand la limite de temps est atteinte, les votes sont comptés une derniere fois, et le processus de cloture du vote peut démarrer
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
            txt += f"Rendez-vous à {time.ctime(time.time()+COOLDOWN_VOTE+3600)} GMT+1"
            await channel.send(txt)
    else:

        tsc = math.floor(time.time()-iss["time_start_countdown"])
        print(f"{duree(tsc)}/{duree(COOLDOWN_VOTE)}")
        if tsc < COOLDOWN_VOTE:
            temps_restant = COOLDOWN_VOTE-tsc
            if temps_restant <= RAPPEL and temps_restant >= (RAPPEL-UPDATE):
                print(f"{duree(RAPPEL)} avant vote")
                await channel.send(f"Il reste {duree(RAPPEL)} avant la fin du vote!")
            return True
        else:
            await end_votes(channel)
            verif.stop()
            return False


# Converti l'xml de résultats en messages clairs
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

    if issue.find("UNLOCKS") is not None:
        msg = "**__Unlocks : __**\n"
        for unlock in issue.find("UNLOCKS"):
            msg += f"{unlock.tag.lower()} : {unlock.text}\n"

    if issue.find("RECLASSIFICATIONS") is not None and issue.find("RECLASSIFICATIONS").findall("RECLASSIFY") is not None:
        msg += "**__Reclassification : __**\n"
        for r in issue.find("RECLASSIFICATIONS").findall("RECLASSIFY"):
            rtype = LIST_RANK_ID[int(r.get("type"))]
            fro = r.find("FROM").text
            to = r.find("TO").text
            msg += f"{rtype} : from {fro} to {to}\n"

    if issue.find("HEADLINES") is not None and issue.find("HEADLINES").findall("HEADLINE") is not None:
        msg += "**__Headlines: __**\n"
        for h in issue.find("HEADLINES").findall("HEADLINE"):
            msg += f"{h.text}\n"

    if issue.find("NEW_POLICIES") is not None:
        msg += "**__Nouvelles Stratégies : __**\n"
        for p in issue.find("NEW_POLICIES"):
            msg += f"{p.tag} : {p.text}\n"

    if issue.find("REMOVED_POLICIES") is not None:
        msg += "**__Stratégies Enlevées : __**\n"
        for p in issue.find("REMOVED_POLICIES"):
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

# ----------------------------- COMMANDES DISCORDS GESTION DE VOTE


@bot.command(name='ping', help='Pong!')
async def ping(ctx):
    await ctx.send("Pong!")


@bot.command(name='delete', help="Supprime des messages\nPrend une liste d'id de message et les supprimes, en plus du message qui a envoyé la commande\nLimité aux admins")
async def delete(ctx, *id_mes):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    for i in id_mes:
        mes = await ctx.channel.fetch_message(i)
        await mes.delete()
    await ctx.message.delete()


@bot.command(name='start', help="Force le setup d'un vote\nLimité aux admins")
async def start(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    await start_vote(ctx)


@bot.command(name='resume', help="Relance le processus de vote à partir du backup\nDemande l'id du vote\nà n'utiliser que si le bot s'est arreté en cours de vote\nRéservé aux admins")
async def resume(ctx, id_issue):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    if id_issue is None:
        await ctx.send("Besoin d'un id svp")
        return
    global CHANNEL, GUILD, CURRENT_ID
    CURRENT_ID = int(id_issue)
    if ISSUES[CURRENT_ID]["option_taken"] != -2:
        print(f"{CURRENT_ID} a deja recu un vote, annulation de la commande")
        await ctx.send(f"{CURRENT_ID} a deja recu un vote, annulation de la commande")
        return

    CHANNEL = ctx.guild.get_channel(int(CHANNEL_ISSUES_ID))
    if CHANNEL is None:
        CHANNEL = ctx.channel
    if ctx.guild.id == GUILD_ID:
        GUILD = ctx.guild

    print(f"{CURRENT_ID} resumed")
    await ctx.send(f"{CURRENT_ID} resumed")
    verif.start(ctx)


@bot.command(name='end', help="Conclut le vote actuel de force.\nRéservé aux admins")
async def end(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    await end_votes(ctx.channel)


@bot.command(name='res', help='Affiche un résultat de test\nLimité aux admins')
async def res(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    await results(ctx.channel, RESULTS_XML)


@bot.command(name='resxml', help='Pong!')
async def resxml(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    if ISSUE_RESULTS is not None:
        await ctx.send(ISSUE_RESULTS)
    else:
        await ctx.send("Pas de résultat à montrer, sorry")

# ----------------------------- FIN SETUP

# S'execute quand le bot est prêt; Affiche la liste des serveurs sur lesquelles le bot est actuellement


@bot.event
async def on_ready():
    print(f'{bot.user} is connected to the following guild:')
    for guild in bot.guilds:
        print(f'-{guild.name}')
    print(f'{bot.user} has started')


# lance le bot
bot.run(TOKEN)
