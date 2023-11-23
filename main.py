import json
import os
from datetime import datetime

import discord
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv
from replit import db

from keep_alive import keep_alive
# from setup_db import setup_db
# setup_db()

# load env variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TMDB_KEY = os.getenv('TMDB_KEY')
SUPERUSER_ID = int(os.getenv('SUPERUSER_ID', '0'))

bot = commands.Bot(command_prefix='!')


def get_movie_details(title, year, movie_id=None):
    payload = {
        'api_key': TMDB_KEY,
        'language': 'en-US',
        'query': title,
        'year': year,
        'include_adult': True
    }
    api_key_param = {'api_key': TMDB_KEY}

    if not movie_id:
        response = requests.get('https://api.themoviedb.org/3/search/movie', params=payload).json()
        if response['total_results'] != 1:
            return None

        movie_id = response['results'][0]['id']

    response = requests.get(f'https://api.themoviedb.org/3/movie/{movie_id}', params=api_key_param)
    movie_data = response.json()

    response = requests.get(f'https://api.themoviedb.org/3/movie/{movie_id}/credits', params=api_key_param).json()
    movie_data['actors'] = ', '.join(person['name'] for person in response['cast'][:5])
    movie_data['actors'] = f'{movie_data["actors"]} (among others)'

    movie_data['directors'] = ', '.join(person['name'] for person in response['crew'] if person['job'] == 'Director')

    return movie_data


def embed_movie_details(details, author=None):
    embed = discord.Embed(
        title='{} ({})'.format(details['title'], details['release_date'][:4]),
        color=discord.Colour.orange()
    )
    embed.add_field(name='Genre', value=', '.join(genre['name'] for genre in details['genres']))
    embed.add_field(name='Rated', value=f'{details["vote_average"]}/10')
    embed.add_field(name='Actors', value=details['actors'])
    embed.add_field(name='Plot', value=details['overview'])
    embed.add_field(name='Director', value=details['directors'])
    if details['poster_path']:
        embed.set_thumbnail(url=f'https://image.tmdb.org/t/p/w300{details["poster_path"]}')
        embed.set_footer(text='Click poster thumbnail to enlarge')
    if author:
        embed.set_author(name=author)
    return embed


async def start_poll_exec(channel):
    if channel.name != '╻🎥╹movie-nights' or db['poll_message_id']:
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


async def end_poll_exec(channel):
    if channel.name != '╻🎥╹movie-nights' or db['poll_message_id'] is None:
        return

    message = await channel.fetch_message(db['poll_message_id'])
    await message.unpin()

    highest = 0
    for i, reaction in enumerate(message.reactions):
        if reaction.count > message.reactions[highest].count:
            highest = i

    await channel.send('Poll closed!\n\n',
                       embed=embed_movie_details(
                           db['movie_list_details'][highest], 'Poll Winner'))

    db['poll_message_id'] = None
    db['movie_list'] = []
    db['movie_list_details'] = []
    db['movie_nominators_list'] = []


@bot.event
async def on_ready():
    print('Connected!')
    start_poll.start()
    end_poll.start()


@bot.command(name='nominate')
async def nominate(ctx, *, arg=None):
    if ctx.channel.name != '╻🎥╹movie-nights':
        return

    if not arg:
        await ctx.channel.send(
            'No movie title included! Use `!nominate <movie_title>` to nominate a movie to the poll. Add a `-year` flag like `!nominate the call -year 2020` if you want to specify a release year.'
        )
        return

    if len(db['movie_list']) == 10:
        await ctx.channel.send('Maximum number of nominees!')
        return

    movie_details = None
    user_input = arg.split()
    if '-id' in user_input:
        movie_id = user_input[-1]
        movie_details = get_movie_details(None, None, movie_id)
    else:
        if '-year' in user_input:
            year = user_input[-1]
            movie_title = ' '.join(user_input[:-2]).title()
        else:
            year = ''
            movie_title = ' '.join(user_input).title()

        movie_details = get_movie_details(movie_title, year)

    if movie_details is None:
        message = 'Multiple or no matches. Please help me by:\n1) Looking the movie up on https://www.themoviedb.org/'\
                  '\n2) Taking the movie `id` from movie URL (ex: `27205` in `https://www.themoviedb.org/movie/27205-inception`)'\
                  '\n3) Then doing `!nominate -id <id>`.'
        await ctx.channel.send('{}'.format(message))
        return

    movie_entry = '{} ({})'.format(movie_details['title'],
                                   movie_details['release_date'][:4])
    if movie_entry in db['movie_list']:
        await ctx.channel.send(
            '`{}` has already been nominated! `!movies` to see the currently nominated movie(s)'
            .format(movie_entry))
        return

    db['movie_list'] = db['movie_list'] + [movie_entry]
    db['movie_list_details'] = db['movie_list_details'] + [movie_details]
    db['movie_nominators_list'] = db['movie_nominators_list'] + [
        ctx.message.author.id
    ]

    await ctx.channel.send('', embed=embed_movie_details(movie_details))

    if db['poll_message_id']:
        message = await ctx.channel.fetch_message(db['poll_message_id'])

        description = ''
        for i, item in enumerate(db['movie_list']):
            description += '\n{} - {}'.format(db['reactions'][i], item)

        embed = discord.Embed(title='Movie Poll',
                              description=description,
                              color=discord.Colour.orange())
        embed.set_footer(text='Poll ends on Friday')

        await message.edit(content='', embed=embed)
        await message.add_reaction(db['reactions'][len(db['movie_list']) - 1])


@bot.command(name='remove')
async def remove(ctx, index):
    if ctx.channel.name != '╻🎥╹movie-nights':
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

    embed = discord.Embed(
        title='Successfully removed `{}`'.format(movie_entry),
        color=discord.Colour.orange())
    await ctx.channel.send('', embed=embed)


@bot.command(name='movies')
async def movies(ctx):
    if ctx.channel.name != '╻🎥╹movie-nights':
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
    if ctx.channel.name != '╻🎥╹movie-nights':
        return

    if index.isdigit() and int(index) > 0 and int(index) <= len(
            db['movie_list']):
        await ctx.channel.send('',
                               embed=embed_movie_details(
                                   db['movie_list_details'][int(index) - 1]))
        return

    await ctx.channel.send('Invalid number provided! Please refer to `!movies`'
                           )


@tasks.loop(hours=24)
async def start_poll():
    day = datetime.now().strftime("%A")

    channel = discord.utils.get(bot.get_all_channels(),
                                guild__name="Limbagong",
                                name='╻🎥╹movie-nights')
    if day == 'Monday' and not db['poll_message_id']:
        await start_poll_exec(channel)


@tasks.loop(hours=24)
async def end_poll():
    day = datetime.now().strftime("%A")

    channel = discord.utils.get(bot.get_all_channels(),
                                guild__name="Limbagong",
                                name='╻🎥╹movie-nights')
    if day == 'Friday':
        await end_poll_exec(channel)


@bot.command(name='force_start_poll')
async def force_start_poll(ctx):
    channel = discord.utils.get(bot.get_all_channels(),
                                guild__name="Limbagong",
                                name='╻🎥╹movie-nights')
    author = ctx.message.author
    if author.id == SUPERUSER_ID:
        await start_poll_exec(channel)


@bot.command(name='force_end_poll')
async def force_end_poll(ctx):
    channel = discord.utils.get(bot.get_all_channels(),
                                guild__name="Limbagong",
                                name='╻🎥╹movie-nights')
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


keep_alive()
bot.run(DISCORD_TOKEN)

