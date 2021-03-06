import asyncio
import os
import yaml
import discord
import time
import math
import re
import requests
from random import shuffle
import defusedxml.ElementTree as DT
from copy import deepcopy
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

# ----------------------------- SETUP VARIABLES GLOBALES ET BOT

global NATION, PASSWORD, GUILD, CHANNEL, ISSUES, PATH, EMOJI, UPDATE, COOLDOWN_VOTE, RAPPEL, BANNED_HOURS
global EMOJI_VOTE, MIN_BEFORE_COOLDOWN, LIST_RANK_ID, RESULTS_XML, INPUT_XML, ROLE_PING, CURRENT_ID, ISSUE_RESULTS, BANNER_TITLES

UPDATE = 1
COOLDOWN_VOTE = 5
RAPPEL = 0
MIN_BEFORE_COOLDOWN = 1
CURRENT_ID = 0
CHANNEL = None
GUILD = None
ISSUE_RESULTS = None

BANNED_HOURS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 22, 23, 24]
ROLE_PING = "671696364056477707"
EMOJI_VOTE = ["☑️", "✅"]
EMOJI = [":apple:", ":pineapple:", ":kiwi:", ":cherries:", ":banana:", ":eggplant:", ":tomato:", ":corn:", ":carrot:"]
NATION = 'controlistania'
PATH = 'vote.yml'
RESULTS_XML = DT.parse("test_result.xml")
INPUT_XML = DT.parse("test_input.xml")

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PASSWORD = os.getenv('PASSWORD')

bot = commands.Bot(command_prefix='!')

# ----------------------------- LECTURE DES FICHIERS

# Charge la liste des rangs et des bannieres lors du lancement de l'application
with open("list_data.yml") as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    LIST_RANK_ID = data["ranks"]
    BANNER_TITLES = data["banners"]
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
    if t % 3600 == 0:
        return f"{math.floor(t/3600)}h"
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


def define_guild_channel(ctx):
    global CHANNEL, GUILD
    GUILD = ctx.guild
    CHANNEL = ctx.channel


def print_xml(xml, tab=""):
    if xml is None:
        return
    try:
        print(f"{tab}<{xml.tag}>\n{tab}{xml.text}")
    except AttributeError:
        print(xml)
    try:
        for x in xml:
            print_xml(x, f" {tab}")
    except TypeError:
        return
    try:
        print(f"{tab}</{xml.tag}>")
    except AttributeError:
        return

# ----------------------------- FONCTIONS GESTION DE VOTE


def check_idop():
    response = requests.get(
        f"https://www.nationstates.net/cgi-bin/api.cgi?nation={NATION}&q=issues",
        headers={
            'User-Agent': 'Controlistania Discord Bot - owner:timothee.bouvin@gmail.com',
            'X-Password': PASSWORD
        },
    )
    n = DT.fromstring(response.text)

    for i in n.find('ISSUES').findall('ISSUE'):

        txt = f"{i.get('id')} :"
        for option in i.findall('OPTION'):
            txt += f"{option.get('id')} "
        print(txt)


# Setup un vote et lance verif()
async def start_vote(issues):
    issue = issues[len(issues)-1]

    issue_id = int(issue.get('id'))
    try:
        test = ISSUES[issue_id]
        return 0
    except KeyError:
        print("started")
    title = issue.find('TITLE').text
    text = issue.find("TEXT").text.replace("<i>", "*").replace("</i>", "*")
    msg = embed(title, text, color=0xdb151b, footer=f"ID : {issue_id}")
    title_message = await CHANNEL.send(embed=msg)

    shuffle(EMOJI)
    options = {}
    i = 1
    for option in issue.findall('OPTION'):
        txt = option.text.replace("<i>", "*").replace("</i>", "*")
        msgoption = embed(fv=txt, num=i, color=0xecb440, footer=f"ID : {option.get('id')}")
        option_message = await CHANNEL.send(embed=msgoption)
        options[int(option.get("id"))] = {
            "id_message": option_message.id,
            "text": txt
        }
        i += 1

    msg_info = f"**<@&{ROLE_PING}>, un nouveau vote est lancé!**\nVeuillez voter en mettant une réaction sous l'option de votre choix (Un vote par personne! En cas de multiple vote, la premiere option rencontrée sera prise et les autres seront ignorées)\n"
    msg_info += "En cas d'égalité, le vote sera annulé, et l'issue révoquée\n"
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
        "guild_id": GUILD.id,
        "channel_id": CHANNEL.id
    }

    global CURRENT_ID
    CURRENT_ID = issue_id

    backup()

    verif.start()
    return 1


def request_issues():
    response = requests.get(
        f"https://www.nationstates.net/cgi-bin/api.cgi?nation={NATION}&q=issues",
        headers={
            'User-Agent': 'Controlistania Discord Bot - owner:timothee.bouvin@gmail.com',
            'X-Password': PASSWORD
        },
    )
    return DT.fromstring(response.text)


# Envoie le résultat du vote et retourne l'xml reçu grace à la requete
def launch_issue(issue, option):
    # response = requests.get(
    #     f"https://www.nationstates.net/cgi-bin/api.cgi?nation={NATION}&c=issue&issue={issue}&option={option}",
    #     headers={
    #         'User-Agent': 'Controlistania Discord Bot - owner:timothee.bouvin@gmail.com',
    #         'X-Password': PASSWORD
    #     },
    # )
    # global ISSUE_RESULTS
    # ISSUE_RESULTS = response.text
    # print(response.text)
    # n = DT.fromstring(response.text)
    # return n
    return RESULTS_XML


# Compte les votes de la listes de messages dans le canal "channel" et renvoie un tableau contenant le nombre de vote de chaque option
# Skip les votes d'un user ayant deja voté
async def count_votes(opt):
    channel = CHANNEL
    votes = {}
    voters = []
    for x, o in enumerate(opt):
        id_mes = opt[o]["id_message"]
        if id_mes == 0 or id_mes is None:
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
        votes[x] = {
            "nb_vote": count,
            "id": o
        }
    return votes


# Conclut le vote. Utilise launch_issue() pour envoyer les résultats et obtenir le xml de retour, qu'il envoie ensuite à results()
# Stoppe de force verif()
async def end_votes():
    channel = CHANNEL
    iss = ISSUES[CURRENT_ID]
    if CURRENT_ID == 0 or iss["option_taken"] != -2:
        await channel.send("Pas de vote en cours, annulation de la commande")
        return
    votes = await count_votes(iss["option_msg_id"])
    print(votes)
    tp = math.floor(time.time()-iss["time_posted"])
    msg = "__**RESULTAT DES VOTES**__\n"
    msg += f"ID : {CURRENT_ID}\nTemps écoulé : **{duree(tp)}**\n"
    maxv = 0
    winv = -1
    numv = 0
    for x, v in enumerate(votes):
        cv = votes[v]["nb_vote"]
        if cv == maxv:
            numv += 1
        if cv > maxv:
            maxv = cv
            winv = x
            numv = 1

        msg += f"Option {x+1} : {cv} votes\n"
    if numv > 1:
        winv = -1
        msg += f"Egalité"
    else:

        msg += f"\n **Option gagnante : {winv+1} avec {maxv} votes**\n"
        winv = votes[winv]["id"]

    print(f"winv : {winv}")
    ISSUES[CURRENT_ID]["option_taken"] = winv
    iss["option_taken"] = winv
    backup()
    await channel.send(msg)
    xml = launch_issue(CURRENT_ID, winv)
    if winv != -1:
        await results(xml)
    verif.stop()


@tasks.loop(seconds=UPDATE, reconnect=True)
async def check_start():
    t = int(time.strftime("%H", time.gmtime()))+1  # sans le +1, représente l'heure à GMT+0, or on est en GMT+1
    if t not in BANNED_HOURS:
        n = request_issues()
        # n = DT.fromstring("<NATION></NATION>")
        if n is None or n.find('ISSUES') is None or n.find('ISSUES').find('ISSUE') is None or n.find('ISSUES').find('ISSUE').find('OPTION') is None:
            # print_xml(n)
            print("vide")
            return
        else:
            try:
                issues = n.find('ISSUES').findall('ISSUE')
                iid = int(issues[len(issues)-1].get("id"))
            except IndexError:
                # sert au debogage
                print("ID incorrecte")
                print_xml(n)
                check_start.stop()
                return

            print(f"id :{iid}")
            if(CURRENT_ID == iid):
                print(f"erreur : issue #{iid} deja en cours vote({CURRENT_ID})")
            else:
                try:
                    ISSUES[iid]
                except KeyError:
                    started = await start_vote(issues)
                    if started == 1:
                        check_start.stop()
                    else:
                        print("Erreur, pas pu commencer")
                else:
                    resumed = resume_issue(iid)
                    if resumed == 1:
                        check_start.stop()
    else:
        print("pas dans l'horaire")
        return

# Boucle toutes les UPDATE secondes
# Gere les conditions de fin de vote
# Une fois que le bot est lancé, vérifie si le nombre de vote est suffisent
# Si assez de gens ont votés, un temps limite est décidé (les votes ne seront plus comptés jusqu'à la fin du vote)
# Quand la limite de temps est atteinte, les votes sont comptés une derniere fois, et le processus de cloture du vote peut démarrer
@tasks.loop(seconds=UPDATE)
async def verif():
    iss = ISSUES[CURRENT_ID]
    opt = iss["option_msg_id"]
    guild = GUILD
    channel = CHANNEL
    if iss["option_taken"] != -2:
        print("continue")
        return True
    if iss["time_start_countdown"] == 0:
        votes = await count_votes(opt)
        cvotes = 0
        lv = []
        for v in votes:
            cvotes += votes[v]["nb_vote"]
            lv.append(votes[v]["nb_vote"])

        print(f"{lv}")
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
            await end_votes()
            verif.stop()
            print("start sleep")
            await asyncio.sleep(10)
            print("stop sleep, go")
            check_start.start()
            return False


# Converti l'xml de résultats en messages clairs
async def results(xml):
    channel = CHANNEL
    msg = ""
    # issue = RESULTS_XML.find("ISSUE")
    issue = xml.find("ISSUE")
    desc = issue.find("DESC").text
    id_issue = int(issue.get("id"))
    origin = None
    if issue == 99999:
        origin = INPUT_XML
    else:
        origin = ISSUES
    text_issue = origin[id_issue]["title_text"]
    choice_issue = int(issue.get("choice"))
    if choice_issue == -1:
        return
    text_option = ""
    for x, y in origin[id_issue]["option_msg_id"][choice_issue].items():
        text_option = y
    msg += f"__**RESOLUTION DE PROBLEME**__\n"
    msg += f"Le problème **#{id_issue}** (*{text_issue}*) a été résolu via l'option **{choice_issue+1}**.\n"
    msg += f"**{desc.upper()}**\n"
    await channel.send(msg)
    msg = ""
    if issue.find("UNLOCKS") is not None:
        msg += "**__Unlocks : __**\n"
        for unlock in issue.find("UNLOCKS"):
            if unlock.tag.lower() == "banner":
                title = BANNER_TITLES[unlock.text]["name"].replace("(Name)", NATION)
                criteria = BANNER_TITLES[unlock.text]["criteria"]
                msg += f"**{title}** (*{criteria}*)\nhttps://www.nationstates.net/images/banners/samples/{unlock.text}.jpg\n"
            else:
                msg += f"{unlock.tag.lower()} : {unlock.text}\n"
        # await channel.send(msg)
        # msg = ""

    if issue.find("RECLASSIFICATIONS") is not None and issue.find("RECLASSIFICATIONS").find("RECLASSIFY") is not None:
        msg += "**__Reclassification : __**\n"
        for r in issue.find("RECLASSIFICATIONS").findall("RECLASSIFY"):
            if str(r.get("type")) == "govt":
                rtype = "Government"
            else:
                rtype = LIST_RANK_ID[int(r.get("type"))]
            fro = r.find("FROM").text
            to = r.find("TO").text
            msg += f"{rtype} : from {fro} to {to}\n"

    if issue.find("HEADLINES") is not None and issue.find("HEADLINES").findall("HEADLINE") is not None:
        msg += "**__Headlines: __**\n"
        for h in issue.find("HEADLINES").findall("HEADLINE"):
            msg += f"{h.text}\n"
    if len(msg) > 0:
        await channel.send(msg)
        msg = ""
    if issue.find("NEW_POLICIES") is not None:
        msg += "**__Nouvelles Stratégies : __**\n"
        for p in issue.find("NEW_POLICIES").findall("POLICY"):
            msg += f"**{p.find('NAME').text}** : {p.find('DESC').text} ({p.find('CAT').text})\n"
            msg += f"https://www.nationstates.net/images/banners/samples/{p.find('PIC').text}.jpg\n"
    if issue.find("REMOVED_POLICIES") is not None:
        msg += "**__Stratégies Enlevées : __**\n"
        for p in issue.find("REMOVED_POLICIES"):
            msg += f"{p.tag} : {p.text}\n"

    print(f"Message infos : {len(msg)}")
    if len(msg) > 0:
        await channel.send(msg)
        msg = ""
    msg = "**__CHANGEMENT DE RANGS__**\n```c++\n"
    dictranks = {}
    for r in issue.find("RANKINGS").findall("RANK"):
        id_r = int(r.get("id"))
        name = LIST_RANK_ID[int(id_r)]
        score = r.find("SCORE").text
        change = float(r.find("CHANGE").text)
        pchange = round(float(r.find("PCHANGE").text), 2)
        dictranks[id_r] = {
            "name": name,
            "score": score,
            "change": change,
            "pchange": pchange
        }

    dictranks = sorted(dictranks.items(), key=lambda x: float(x[1]["pchange"]), reverse=True)
    for r in dictranks:
        id_r = r[0]
        name = r[1]["name"]
        score = r[1]["score"]
        change = r[1]["change"]
        pchange = r[1]["pchange"]
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
    if(len(msg) < 2000 and len(msg) > 0):
        await channel.send(msg+"```")
        print(f"dernier message : {len(msg)}")
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


@bot.command(name='forcestart', help="Force le setup d'un vote\nLimité aux admins")
async def forcestart(ctx, *debug):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    if len(debug) == 0:
        n = request_issues()
        if n is None or n.find('ISSUES') is None or n.find('ISSUES').find('ISSUE') is None or n.find('ISSUES').find('ISSUE').find('OPTION') is None:
            await ctx.send("Pas d'issues :(")
            return
        else:
            define_guild_channel(ctx)
            started = await start_vote(n)
            if started == 0:
                await ctx.send("Erreur lors du lancement")
    else:
        print("start debug")
        await start_vote(INPUT_XML)


@bot.command(name='resume', help="Relance le processus de vote à partir du backup\nDemande l'id du vote\nà n'utiliser que si le bot s'est arreté en cours de vote\nRéservé aux admins")
async def resume(ctx, id_issue):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    if id_issue is None:
        await ctx.send("Besoin d'un id svp")
        return
    try:
        ISSUES[int(id_issue)]
    except KeyError:
        await ctx.send("Cet id n'existe pas dans la base de donnée")
        return
    resumed = resume_issue(id_issue)
    if resumed == 0:
        await ctx.send(f"{id_issue} a deja recu un vote")
    elif resumed == -1:
        await ctx.send("Le canal n'a pas été trouvé")
    elif resumed == 1:
        await ctx.send(f"{CURRENT_ID} resumed")


def resume_issue(id_issue):
    global CHANNEL, GUILD, CURRENT_ID

    if ISSUES[int(id_issue)]["option_taken"] != -2:
        print(f"{CURRENT_ID} a deja recu un vote, annulation de la commande")
        return 0
    CURRENT_ID = int(id_issue)
    for guild in bot.guilds:
        if guild.id == ISSUES[CURRENT_ID]["guild_id"]:
            GUILD = guild
    CHANNEL = GUILD.get_channel(ISSUES[CURRENT_ID]["channel_id"])
    if CHANNEL is None:
        print(f"Le canal n'a pas été trouvé...\nID du canal sauvegardée : {ISSUES[CURRENT_ID]['channel_id']}")
        return -1
    print(f"{CURRENT_ID} resumed")
    verif.start()
    return 1


@bot.command(name='end', help="Conclut le vote actuel de force.\nRéservé aux admins")
async def end(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    await end_votes()


@bot.command(name='res', help='Affiche un résultat de test\nLimité aux admins')
async def res(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    if CHANNEL is None:
        define_guild_channel(ctx)
    await results(RESULTS_XML)


@bot.command(name='resxml', help='Enregistre dans un fichier le contenu xml de la derniere reponse\nLimité aux admins')
async def resxml(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    if ISSUE_RESULTS is not None:
        with open("results_dump.txt", mode="w+") as x:
            x.truncate(0)
            x.write(ISSUE_RESULTS)
            x.close()
    else:
        await ctx.send("Pas de résultat à montrer, sorry")


@bot.command(name='start', help='Pong!')
async def start(ctx):
    if ctx.author.id != 123742890902945793 and ctx.author.id != 111552820225814528:
        await ctx.send("Negatif")
        return
    try:
        check_start.start()
        define_guild_channel(ctx)
    except RuntimeError:
        await ctx.send("La commande est déjà en cours")
    # await check_start()

# ----------------------------- FIN SETUP

# S'execute quand le bot est prêt; Affiche la liste des serveurs sur lesquelles le bot est actuellement


@bot.event
async def on_ready():
    print(f'{bot.user} is connected to the following guild:')
    for guild in bot.guilds:
        print(f'-{guild.name}')
    print(f'{bot.user} has started (debug version)')


# lance le bot
bot.run(TOKEN)
