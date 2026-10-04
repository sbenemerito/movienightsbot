import os

from sqlitedict import SqliteDict

db = SqliteDict(os.getenv('DB_PATH', 'data.sqlite'))


def get_initial_db_data():
    return {
        'movie_list': [],
        'movie_list_details': [],
        'movie_nominators_list': [],
        'reactions': ["🐶", "🐼", "🐷", "🐻", "🐱", "🐰", "🐺", "🐸", "🐔", "🦄"],
        'poll_message_id': None,
    }


def get_db():
    """
    Initialize db if it's empty (ie. first run)
    """
    if db.get('reactions'):
        return db

    initial_data = get_initial_db_data()
    for key, value in initial_data.items():
        db[key] = value
    db.commit()
    return db
