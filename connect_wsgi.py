"""Gunicorn entry point for the isolated Flama Connect process."""

from app.connect import create_connect_app


app = create_connect_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=4790)
