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
