import asyncio
import os
from datetime import datetime, time

import discord
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv

from db import get_db
from utils import embed_movie_details, get_movie_details, movie_select_option, search_movies

# load env variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TMDB_KEY = os.getenv('TMDB_KEY')
CHANNEL_NAME = os.getenv('CHANNEL_NAME')
SERVER_NAME = os.getenv('SERVER_NAME')
SUPERUSER_ID = int(os.getenv('SUPERUSER_ID', '0'))

# daily poll check runs at this local time (discord.py treats naive times as UTC)
POLL_CHECK_TIME = time(hour=0, minute=5, tzinfo=datetime.now().astimezone().tzinfo)

ID_HELP = 'Please help me by:'\
          '\n1) Looking the movie up on https://www.themoviedb.org/'\
          '\n2) Taking the movie `id` from movie URL '\
          '(ex: `27205` in `https://www.themoviedb.org/movie/27205-inception`)'\
          '\n3) Then doing `!nominate -id <id>`.\n'

# load db using util function
db = get_db()

# initialize bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)


async def start_poll_exec(channel):
    if channel.name != CHANNEL_NAME or db['poll_message_id']:
        return

    if not db['movie_list']:
        await channel.send(
            'No movies have been nominated yet! Use `!nominate <movie_title>` '
            'to nominate a movie to the poll.')
        return

    description = ''
    for i, item in enumerate(db['movie_list']):
        description += '\n{} - {}'.format(db['reactions'][i], item)

    embed = discord.Embed(title='Movie Poll',
                          description=description,
                          color=discord.Colour.orange())
    embed.set_footer(text='Poll ends on Friday')

    message = await channel.send('', embed=embed)
    await message.pin()
    for i, item in enumerate(db['movie_list']):
        await message.add_reaction(db['reactions'][i])

    db['poll_message_id'] = message.id
    db.commit()


def count_poll_votes(reactions):
    # map each poll emoji to its movie index, ignoring non-poll reactions
    poll_reactions = db['reactions'][:len(db['movie_list'])]
    votes = {}
    for reaction in reactions:
        emoji = str(reaction.emoji)
        if emoji not in poll_reactions:
            continue
        # don't count the bot's own reaction
        count = reaction.count - 1 if reaction.me else reaction.count
        votes[db['reactions'].index(emoji)] = count

    return votes


async def end_poll_exec(channel):
    if channel.name != CHANNEL_NAME or db['poll_message_id'] is None:
        return

    message = await channel.fetch_message(db['poll_message_id'])
    await message.unpin()

    votes = count_poll_votes(message.reactions)
    highest = max(votes.values(), default=0)

    if highest == 0:
        await channel.send('Poll closed!\n\nNo votes were cast.')
    else:
        tied = sorted(i for i, count in votes.items() if count == highest)
        winner = tied[0]

        content = 'Poll closed!\n\n'
        if len(tied) > 1:
            tied_titles = ', '.join('`{}`'.format(db['movie_list'][i])
                                    for i in tied)
            content += 'It\'s a tie between {} with {} vote(s) each! '\
                       'Picking `{}`.'.format(tied_titles, highest,
                                              db['movie_list'][winner])
        else:
            content += '`{}` wins with {} vote(s)!'.format(
                db['movie_list'][winner], highest)

        await channel.send(content,
                           embed=embed_movie_details(
                               db['movie_list_details'][winner],
                               'Poll Winner'))

    db['poll_message_id'] = None
    db['movie_list'] = []
    db['movie_list_details'] = []
    db['movie_nominators_list'] = []
    db.commit()


@bot.event
async def on_ready():
    print('Connected!')
    # on_ready fires again after reconnects, so don't relaunch running loops
    if not start_poll.is_running():
        start_poll.start()
    if not end_poll.is_running():
        end_poll.start()

    # time-based loops don't run on start, so catch up on any missed day now
    await start_poll()
    await end_poll()


async def call_tmdb(channel, func, *args):
    # run a blocking TMDB lookup off the event loop; reply and return None on errors
    try:
        return await asyncio.to_thread(func, *args, TMDB_KEY)
    except requests.HTTPError as e:
        # invalid/nonexistent id -> "no matches" help
        if e.response is not None and e.response.status_code == 404:
            await channel.send('No matches. {}'.format(ID_HELP))
            return None
    except (requests.RequestException, KeyError, ValueError):
        pass
    await channel.send("Couldn't reach TMDB, please try again later.")
    return None


def single_match(results, title):
    # the only search result, or the only one whose title matches the query exactly
    if len(results) == 1:
        return results[0]
    query = title.casefold()
    exact = [result for result in results if query in (
        (result.get('title') or '').casefold(), (result.get('original_title') or '').casefold())]
    return exact[0] if len(exact) == 1 else None


async def add_nomination(channel, author_id, movie_details):
    if len(db['movie_list']) >= 10:
        await channel.send('Maximum number of nominees!')
        return

    movie_entry = '{} ({})'.format(movie_details['title'],
                                   movie_details['release_date'][:4])
    if movie_entry in db['movie_list']:
        await channel.send(
            '`{}` has already been nominated! `!movies` to see the currently nominated movie(s)'
            .format(movie_entry))
        return

    db['movie_list'] = db['movie_list'] + [movie_entry]
    db['movie_list_details'] = db['movie_list_details'] + [movie_details]
    db['movie_nominators_list'] = db['movie_nominators_list'] + [author_id]
    db.commit()

    await channel.send('', embed=embed_movie_details(movie_details))

    if db['poll_message_id']:
        message = await channel.fetch_message(db['poll_message_id'])

        description = ''
        for i, item in enumerate(db['movie_list']):
            description += '\n{} - {}'.format(db['reactions'][i], item)

        embed = discord.Embed(title='Movie Poll',
                              description=description,
                              color=discord.Colour.orange())
        embed.set_footer(text='Poll ends on Friday')

        await message.edit(content='', embed=embed)
        await message.add_reaction(db['reactions'][len(db['movie_list']) - 1])


class NominationPicker(discord.ui.View):
    def __init__(self, author_id, results):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.message = None
        self.pick.options = [movie_select_option(result) for result in results[:5]] + [
            discord.SelectOption(label='None of these', value='none')
        ]

    async def interaction_check(self, interaction):
        if interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message("This isn't your nomination!", ephemeral=True)
        return False

    async def on_timeout(self):
        self.pick.disabled = True
        try:
            await self.message.edit(content='Movie picker timed out.', view=self)
        except discord.HTTPException:
            pass

    @discord.ui.select(placeholder='Pick the movie to nominate')
    async def pick(self, interaction, select):
        self.stop()
        select.disabled = True
        choice = next(option for option in select.options if option.value == select.values[0])
        # editing the picker acknowledges the interaction before the slow TMDB lookup
        await interaction.response.edit_message(content='Picked `{}`.'.format(choice.label), view=self)

        if choice.value == 'none':
            await interaction.channel.send('No problem! {}'.format(ID_HELP))
            return

        movie_details = await call_tmdb(interaction.channel, get_movie_details, choice.value)
        if movie_details:
            await add_nomination(interaction.channel, interaction.user.id, movie_details)


@bot.command(name='nominate')
async def nominate(ctx, *, arg=None):
    if ctx.channel.name != CHANNEL_NAME:
        return

    if not arg:
        await ctx.channel.send(
            'No movie title included! Use `!nominate <movie_title>` to nominate a movie '\
            'to the poll. Add a `-year` flag like `!nominate the call -year 2020` if you '\
            'want to specify a release year.'
        )
        return

    if len(db['movie_list']) >= 10:
        await ctx.channel.send('Maximum number of nominees!')
        return

    user_input = arg.split()
    if '-id' in user_input:
        movie_id = user_input[-1]
    else:
        if '-year' in user_input:
            year = user_input[-1]
            movie_title = ' '.join(user_input[:-2]).title()
        else:
            year = ''
            movie_title = ' '.join(user_input).title()

        results = await call_tmdb(ctx.channel, search_movies, movie_title, year)
        if results is None:
            return
        if not results:
            await ctx.channel.send('No matches. {}'.format(ID_HELP))
            return

        match = single_match(results, movie_title)
        if not match:
            view = NominationPicker(ctx.author.id, results)
            view.message = await ctx.send('Multiple matches found, pick one:', view=view)
            return
        movie_id = match['id']

    movie_details = await call_tmdb(ctx.channel, get_movie_details, movie_id)
    if movie_details:
        await add_nomination(ctx.channel, ctx.author.id, movie_details)


@bot.command(name='remove')
async def remove(ctx, index):
    if ctx.channel.name != CHANNEL_NAME:
        return

    if not index.isdigit() or int(index) == 0 or int(index) > len(
            db['movie_list']):
        await ctx.channel.send(
            'Invalid number provided! Please refer to `!movies`')
        return

    author = ctx.message.author
    index = int(index) - 1
    if author.id != db['movie_nominators_list'][
            index] and author.id != SUPERUSER_ID:
        await ctx.channel.send(
            'You cannot remove nominated movies that you did not nominate!')
        return

    if db['poll_message_id']:
        await ctx.channel.send(
            'You cannot remove movies when the poll has started!')
        return

    movie_entry = db['movie_list'][index]
    tmp_movie_list = [x for i, x in enumerate(db['movie_list']) if i != index]
    tmp_movie_list_details = [
        x for i, x in enumerate(db['movie_list_details']) if i != index
    ]
    tmp_movie_nominators_list = [
        x for i, x in enumerate(db['movie_nominators_list']) if i != index
    ]
    db['movie_list'] = tmp_movie_list
    db['movie_list_details'] = tmp_movie_list_details
    db['movie_nominators_list'] = tmp_movie_nominators_list
    db.commit()

    embed = discord.Embed(
        title='Successfully removed `{}`'.format(movie_entry),
        color=discord.Colour.orange())
    await ctx.channel.send('', embed=embed)


@bot.command(name='movies')
async def movies(ctx):
    if ctx.channel.name != CHANNEL_NAME:
        return

    description = '`!details <number_in_list>` to get movie details\n'
    for i, item in enumerate(db['movie_list'], 1):
        description += '\n{}) - {}'.format(i, item)

    embed = discord.Embed(title='Movie List',
                          description=description,
                          color=discord.Colour.orange())
    embed.set_footer(text='\n\n{} currently nominated movie(s)\n'.format(
        len(db['movie_list'])))

    await ctx.channel.send('', embed=embed)


@bot.command(name='details')
async def details(ctx, index):
    if ctx.channel.name != CHANNEL_NAME:
        return

    if index.isdigit() and int(index) > 0 and int(index) <= len(
            db['movie_list']):
        await ctx.channel.send('',
                               embed=embed_movie_details(
                                   db['movie_list_details'][int(index) - 1]))
        return

    await ctx.channel.send('Invalid number provided! Please refer to `!movies`')


@tasks.loop(time=POLL_CHECK_TIME)
async def start_poll():
    weekday = datetime.now().weekday()  # Monday is 0

    channel = discord.utils.get(bot.get_all_channels(),
                                guild__name=SERVER_NAME,
                                name=CHANNEL_NAME)
    # Monday to Thursday, so a missed Monday still gets a poll; only nag about
    # an empty list on Monday so later days don't repeat the reminder
    if weekday <= 3 and not db['poll_message_id'] and (db['movie_list'] or weekday == 0):
        await start_poll_exec(channel)


@tasks.loop(time=POLL_CHECK_TIME)
async def end_poll():
    weekday = datetime.now().weekday()  # Monday is 0

    channel = discord.utils.get(bot.get_all_channels(), guild__name=SERVER_NAME, name=CHANNEL_NAME)
    # Friday to Sunday, so a missed Friday still closes the poll
    if weekday >= 4 and db['poll_message_id']:
        await end_poll_exec(channel)


@bot.command(name='force_start_poll')
async def force_start_poll(ctx):
    channel = discord.utils.get(bot.get_all_channels(), guild__name=SERVER_NAME, name=CHANNEL_NAME)
    author = ctx.message.author
    if author.id == SUPERUSER_ID:
        await start_poll_exec(channel)


@bot.command(name='force_end_poll')
async def force_end_poll(ctx):
    channel = discord.utils.get(bot.get_all_channels(),
                                guild__name=SERVER_NAME,
                                name=CHANNEL_NAME)
    author = ctx.message.author
    if author.id == SUPERUSER_ID:
        await end_poll_exec(channel)


@bot.command(name='poll')
async def poll(ctx):
    if not db['poll_message_id']:
        await ctx.channel.send('The poll has not started yet!')
        return

    message = await ctx.channel.fetch_message(db['poll_message_id'])
    await ctx.channel.send('Click link to see poll -> {}'.format(
        message.jump_url))


bot.run(DISCORD_TOKEN)  # program execution pauses here
# so this only gets ran when discord bot stops running
db.close()
