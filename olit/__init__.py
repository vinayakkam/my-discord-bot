"""OLIT / Launch Tower Discord bot package.

Holds everything that used to live in the 7,000-line `main.py` monolith:

- `config`   shared env vars, intents and hardcoded IDs
- `storage`  JSON persistence helpers and the game score store
- `registry` the command catalog that drives the help system
- `errors`   the single command-error handler
- `features` one module per feature area, each exposing `setup(bot)`
"""
