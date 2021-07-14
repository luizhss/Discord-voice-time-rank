import os
import elara
import asyncio
import discord
from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime, timedelta

DATABASE_PATH = 'db/'

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

PREFIX = ('>')
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)


def print_time(seconds):
    S = seconds % 60
    seconds //= 60
    M = seconds % 60
    seconds //= 60
    H = seconds
    return f'{H} hours, {M} minutes and {S} seconds'


def take_seconds(elem):
    return elem[1]['total']


@bot.event
async def on_ready():
    print('Logged successfuly!')

    # nullify all entries that have a valid ckp
    if not os.path.exists(DATABASE_PATH):
        os.mkdir(DATABASE_PATH)

    dbs = os.listdir(DATABASE_PATH)
    for db_file in dbs:
        if db_file.endswith('.db'):
            db = elara.exe(os.path.join(DATABASE_PATH, db_file))
            ids = db.getkeys()

            for id in ids:
                data = db.get(id)
                if data['ckp'] != -1:
                    data['ckp'] = -1
                    db.set(id, data)

            db.commit()


@bot.command(name='r', help='Shows current ranking in voice channels.')
async def ranking(ctx):

    db = elara.exe(os.path.join(DATABASE_PATH, f'{ctx.guild.id}.db'))
    try:
        data = db.retdb()
    except:
        data = {}

    for id in data.keys():
        member = ctx.guild.get_member(int(id))
        member_stat = data[id]['total']
        if member.voice is not None and data[id]['ckp'] != -1:
            last_ckp = datetime.strptime(data[id]['ckp'], "%d/%m/%Y %H:%M:%S")
            member_stat += (datetime.now() - last_ckp).total_seconds()
            member_stat = int(member_stat)
        data[id]['total'] = member_stat
    print(data)

    rank = dict(sorted(data.items(), key=take_seconds, reverse=True))
    s = '>>> Ranking of most time spent on voice channels\n'
    for i, id in enumerate(rank.keys()):
        #s += '>>> '
        if i == 0:
            s += ':first_place: '
        elif i == 1:
            s += ':second_place: '
        elif i == 2:
            s += ':third_place: '
        else:
            s += '    '
        member = ctx.guild.get_member(int(id))

        s += member.mention + '  -  '
        s += '*' + print_time(rank[id]['total']) + '*'
        s += '\n'

    await ctx.send(s)


@bot.command(name='c', help='Checks time spend in voice channels of given user.')
async def check(ctx, *arg):
    if len(arg) == 0:
        await ctx.send("You must provide the username.")
        return

    member = ctx.guild.get_member_named(arg[0])
    if member is not None:
        member_id = str(member.id)

        db = elara.exe(os.path.join(DATABASE_PATH, f'{ctx.guild.id}.db'))
        data = db.get(member_id)

        member_stat = data['total']

        if member.voice is not None:
            last_ckp = datetime.strptime(data['ckp'], "%d/%m/%Y %H:%M:%S")
            member_stat += (datetime.now() - last_ckp).total_seconds()
            member_stat = int(member_stat)

        await ctx.send(f'>>> {arg[0]} spent *{print_time(member_stat)}* on voice channels')
    else:
        await ctx.send('User not found!')


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)


@bot.event
async def on_voice_state_update(member, before, after):
    current_user = str(member.id)
    now = datetime.now()

    if before.channel is None and after.channel is not None:
        db = elara.exe(os.path.join(DATABASE_PATH, f'{after.channel.guild.id}.db'))
        data = db.get(current_user)
        if data is None:
            data = {'total': 0, 'ckp': now.strftime("%d/%m/%Y %H:%M:%S")}
        else:
            data['ckp'] = now.strftime("%d/%m/%Y %H:%M:%S")
        db.set(current_user, data)
        db.commit()

    elif before.channel is not None and after.channel is None:
        # open database of current guild
        db = elara.exe(os.path.join(DATABASE_PATH, f'{before.channel.guild.id}.db'))
        data = db.get(current_user)

        # if user is not on our db, then we cant estimate the time we was on
        # voice channel
        if data is None or data['ckp'] == -1:
            return

        # getting datetime of last checkpoint
        last_ckp = datetime.strptime(data['ckp'], "%d/%m/%Y %H:%M:%S")

        # defining new values of user
        data['total'] = int(data['total'] + (now - last_ckp).total_seconds())
        data['ckp'] = -1

        db.set(current_user, data)
        db.commit()


async def checkpoints():
    await bot.wait_until_ready()
    await asyncio.sleep(5)

    # update checkpoints of users in voice channels
    while not bot.is_closed():
        now = datetime.now()
        for guild in bot.guilds:
            db = elara.exe(os.path.join(DATABASE_PATH, f'{guild.id}.db'))
            for vc in guild.voice_channels:
                for member in vc.members:
                    member_id = str(member.id)
                    data = db.get(member_id)

                    if data is not None and data['ckp'] != -1:
                        last_ckp = datetime.strptime(
                            data['ckp'], "%d/%m/%Y %H:%M:%S")
                        data['total'] = int(
                            data['total'] + (now - last_ckp).total_seconds())
                    elif data is None:
                        data = {}
                        data['total'] = 0
                    data['ckp'] = now.strftime("%d/%m/%Y %H:%M:%S")
                    db.set(member_id, data)
            db.commit()
        await asyncio.sleep(60 * 30)  # make checkpoints at every 30 minutes

bot.loop.create_task(checkpoints())

bot.run(TOKEN)
