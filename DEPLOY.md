# Deploying online-store

Flask + Flask-SQLAlchemy + Flask-Login storefront with a PayPal checkout.
Factory in `app/__init__.py`, WSGI object at `main:app`.

Public hostname: **store.harolditdata.uk** → `127.0.0.1:5764`
Overall verdict: **NEEDS WORK** — sections 1 and 2. Do not publish before both
are done.

---

## 1. Blocker: the session secret is a public constant

`app/__init__.py`:

```python
app.config['SECRET_KEY'] = 'do_not_show_this_to_anyone_100'
```

Unconditional, so no environment variable overrides it, and it is in git. Every
session cookie on this site is forgeable by anyone who has read the repository,
including a logged-in admin session. The fix is one line in `app/__init__.py`:

```python
app.config['SECRET_KEY'] = os.environ["SECRET_KEY"]
```

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 2. Blocker: a real `.env` is committed

`online-store/.env` exists in the working tree alongside `.env.example`. Assume
everything in it is burned and rotate it at each provider — PayPal credentials
in particular, since `app/paypal_client.py` is a live payments path.

`.dockerignore` excludes `.env` so it will not be baked into the image, but that
does not un-leak anything already pushed.

## 3. Why `requirements-deploy.txt` exists

`requirements.txt` pins `logging==0.4.9.6`. That is a 2005 Python-2-era package
that squats the name of the standard library's `logging` module; nothing here
imports it (`import logging` resolves to the stdlib) and a Python-2 sdist is not
something to have pip building inside a production image.

`requirements-deploy.txt` is that file verbatim with the one line removed. It is
purely additive — `requirements.txt` is untouched.

> Not build-verified. Docker is not installed on this machine, so this image has
> never been built. Treat the first `docker build` as the real test.

## 4. Environment variables

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | yes, after section 1 | 48+ random bytes |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | for checkout | rotate first, see section 2 |
| `PAYPAL_MODE` | no | `sandbox` until you have tested end to end |

## 5. Build and run

```bash
docker build -t online-store:latest .

docker volume create online-store-instance
docker volume create online-store-uploads

docker run -d --name online-store \
  --restart unless-stopped \
  -p 127.0.0.1:5764:5764 \
  -e SECRET_KEY="$SECRET_KEY" \
  -e PAYPAL_CLIENT_ID="$PAYPAL_CLIENT_ID" \
  -e PAYPAL_CLIENT_SECRET="$PAYPAL_CLIENT_SECRET" \
  -v online-store-instance:/app/instance \
  -v online-store-uploads:/app/app/static/profile_pics \
  --memory 384m --cpus 0.5 \
  online-store:latest
```

The publish is `127.0.0.1:5764:5764`, not `0.0.0.0`. `cloudflared` reaches it on
loopback; nothing else should be able to.

The old Dockerfile bound port 80. That is privileged, which is why it also ran
as root. This one uses 5764 and a uid-10008 `appuser`.

## 6. Persistence

| Path | Volume | Lost without it |
|---|---|---|
| `/app/instance` | `online-store-instance` | the SQLite database — products, customers, orders |
| `/app/app/static/profile_pics` | `online-store-uploads` | uploaded images |

`media/` ships inside the image and is read-only at runtime.

`create_app()` calls `db.create_all()` at import, so a fresh volume
self-initialises. There is no migration story: if a model changes, the schema on
an existing volume will not follow it.

## 7. Cloudflare tunnel

Rule for the shared `config.yml` (see `/home/onyango/Projects/DEPLOYMENT_PLAN.md`):

```yaml
  - hostname: store.harolditdata.uk
    service: http://127.0.0.1:5764
```

Keep Cloudflare Access on the hostname until sections 1 and 2 are closed.

## 8. Health

`GET /` is the probe; anything under HTTP 500 counts as alive.
