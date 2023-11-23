# movienightsbot

A Discord bot made for facilitating movie polls for our weekly movie night (Saturdays). The bot has been running on [Replit](https://replit.com/) since late 2020.

Recently, we've had issues with the bot's uptime on Replit, so I've moved the whole source here and will be deploying it somewhere else.

https://github.com/sbenemerito/movienightsbot/assets/20042067/8cfb7488-9647-49b1-9637-ce9af6af575c

## Setup (local)

### 1) Set environment variables

Rename/copy the `.env.example` file to `.env` and update its contents according to your needs.

### 2) Install requirements

```bash
pip install -r requirements.txt
```

### 3) Run

```bash
python main.py
```

### Tests

Not exactly sure how to unit test Discord bots, so there are none, apparently.

I think it practically makes sense to not have them in this case 🤣

## How the bot works

Basically, the bot handles the weekly poll for what movie our server watches on the coming Saturday night.

Movie data is taken from [The Movie Database (TMDB)](https://www.themoviedb.org/).

The poll automatically starts every Monday, and ends every Friday.

### Commands

```
!movies -> List of nominated movies

!nominate <movie_name> -year <year released> (-year is optional) -> Nominate movie by title

!nominate -id 508442 -> Nominate movie by movie ID in themoviedb.org

!remove <number in list> -> Remove item from list

!details <number in list> -> Movie details

Superuser-only commands

!force_start_poll
!force_end_poll
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.
