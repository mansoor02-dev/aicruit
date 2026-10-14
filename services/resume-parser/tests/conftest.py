import os

# Importing app.api initializes its database tables. Keep test collection
# isolated from any developer or production database configured in the shell.
os.environ["DATABASE_URL"] = "sqlite://"
