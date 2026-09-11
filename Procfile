# create_app() runs db.create_all() itself at import time, so there is no
# release phase to run. Install from requirements-deploy.txt, not
# requirements.txt — see the header of that file.
web: gunicorn --bind 0.0.0.0:${PORT:-5764} --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile - main:app
