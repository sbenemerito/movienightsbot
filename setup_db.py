from replit import db


def setup_db():
    db['movie_list'] = []
    db['movie_list_details'] = []
    db['movie_nominators_list'] = []
    db['reactions'] = ["🐶", "🐼", "🐷", "🐻", "🐱", "🐰", "🐺", "🐸", "🐔", "🦄"]
    db['poll_message_id'] = None
    db['initial_state'] = True
