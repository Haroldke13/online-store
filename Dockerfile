# syntax=docker/dockerfile:1
###############################################################################
# online-store — Flask + SQLAlchemy + Flask-Login storefront with a PayPal
# checkout (app/paypal_client.py)
#
# Build:  docker build -t online-store:latest .
# Run:    see DEPLOY.md
#
# This REPLACES the nine-line Dockerfile that was here before. That one ran as
# root, bound port 80 (privileged, so it could never drop to a normal user),
# had no healthcheck, no pinned patch version, and installed requirements.txt
# including `logging==0.4.9.6`. See requirements-deploy.txt for that last one.
#
# BEFORE YOU POINT DNS AT THIS: app/__init__.py sets
#   app.config['SECRET_KEY'] = 'do_not_show_this_to_anyone_100'
# unconditionally, in a public repo. DEPLOY.md section 1.
###############################################################################

FROM python:3.12.3-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# requirements-deploy.txt, not requirements.txt — read the header of that file.
COPY requirements-deploy.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install -r requirements-deploy.txt

FROM python:3.12.3-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=5764

COPY --from=builder /opt/venv /opt/venv

RUN useradd --system --create-home --uid 10008 --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY --chown=root:root . /app

# create_app() calls create_database() -> db.create_all() at import time against
# sqlite:///database.sqlite3, which Flask-SQLAlchemy resolves into the instance
# folder. That directory must exist and be writable or the app cannot import.
# /app/app/static/profile_pics is UPLOAD_FOLDER.
RUN mkdir -p /app/instance /app/app/static/profile_pics \
 && chown -R appuser:appuser /app/instance /app/app/static/profile_pics
VOLUME ["/app/instance", "/app/app/static/profile_pics"]

USER appuser

EXPOSE 5764

# No /healthz route exists and this image adds no application code, so the probe
# is GET /. http.client does not raise on non-2xx, so a redirect to the login
# page still counts as alive; only 5xx or a dead socket fails.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import http.client,sys; c=http.client.HTTPConnection('127.0.0.1',5764,timeout=4); c.request('GET','/'); sys.exit(0 if c.getresponse().status<500 else 1)"

# SQLite: two workers is the ceiling before writes start colliding.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5764", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "main:app"]
