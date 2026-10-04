import discord
import requests


def get_movie_details(title, year, API_KEY, movie_id=None):
    payload = {
        'api_key': API_KEY,
        'language': 'en-US',
        'query': title,
        'year': year,
        'include_adult': True
    }
    api_key_param = {'api_key': API_KEY}

    if not movie_id:
        response = requests.get(
            'https://api.themoviedb.org/3/search/movie',
            params=payload
        ).json()
        if response['total_results'] != 1:
            return None

        movie_id = response['results'][0]['id']

    response = requests.get(
        f'https://api.themoviedb.org/3/movie/{movie_id}',
        params=api_key_param
    )
    movie_data = response.json()

    response = requests.get(
        f'https://api.themoviedb.org/3/movie/{movie_id}/credits',
        params=api_key_param
    ).json()
    movie_data['actors'] = ', '.join(person['name'] for person in response['cast'][:5])
    movie_data['actors'] = f'{movie_data["actors"]} (among others)'

    movie_data['directors'] = ', '.join(
        person['name'] for person in response['crew'] if person['job'] == 'Director'
    )

    return movie_data


def _truncate(text, limit):
    return text if len(text) <= limit else text[:limit - 3] + '...'


def _field_value(value):
    value = (value or '').strip()
    return _truncate(value, 1024) if value else 'N/A'


def embed_movie_details(details, author=None):
    year = (details.get('release_date') or '')[:4]
    suffix = f' ({year})' if year else ''
    embed = discord.Embed(
        title=_truncate(details['title'], 256 - len(suffix)) + suffix,
        color=discord.Colour.orange()
    )
    genres = ', '.join(genre['name'] for genre in details.get('genres') or [])
    embed.add_field(name='Genre', value=_field_value(genres))
    embed.add_field(name='Rated', value=f'{details["vote_average"]}/10')
    embed.add_field(name='Actors', value=_field_value(details['actors']))
    embed.add_field(name='Plot', value=_field_value(details['overview']))
    embed.add_field(name='Director', value=_field_value(details['directors']))
    if details['poster_path']:
        embed.set_thumbnail(url=f'https://image.tmdb.org/t/p/w300{details["poster_path"]}')
        embed.set_footer(text='Click poster thumbnail to enlarge')
    if author:
        embed.set_author(name=author)
    return embed
