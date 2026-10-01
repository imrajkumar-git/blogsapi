# Backend — Django REST API

API for the Next.js frontend in `../frontend`: JWT auth with admin approval,
profiles with avatars, a blog (posts, covers, likes, comments) and a reviews wall.

## Run it

```bash
cd backend
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # then edit SECRET_KEY
python manage.py migrate
python manage.py createsuperuser                    # asks for email, username, password
python manage.py runserver                          # http://127.0.0.1:8000
```

Then, in `../frontend`: `cp .env.local.example .env.local && npm install && npm run dev`.
The frontend needs **no code changes**; its `.env.local.example` already points here.

Log in at <http://localhost:3000/login> with the superuser's **email** and password;
you'll see the Admin Panel link in the user menu.

Tested on Python 3.12 and 3.14 with Django 5.2 and 6.0.

### Troubleshooting

- **`AttributeError: 'super' object has no attribute 'dicts' ...` on any `/admin/` page** —
  that is an old Django (5.1 or earlier) running on Python 3.14. You're not using the
  project's virtualenv. Activate it and run `pip install -r requirements.txt`, then
  check with `python -m django --version` (needs 5.2+). The project now stops at startup
  with a clear message if it detects this.

## How sign-up works

1. A visitor registers → account is created with `is_verified=False`.
2. They can't log in (the login page shows "waiting on admin verification").
3. An admin ticks **Email verified** in the frontend's Admin Panel → Users (unverified
   accounts are listed first), or uses the *Verify selected users* action at `/admin/`.
4. They can now log in. Un-verifying or disabling someone also invalidates their
   existing tokens.

Superusers made with `createsuperuser` are verified automatically.

## Endpoints

| Prefix | Endpoint | Who |
|---|---|---|
| `/api/auth/` | `POST register/`, `POST login/`, `POST token/refresh/` | public |
| | `GET/PATCH profile/` (multipart ok, `profile_picture`) | signed in |
| | `GET admin/users/`, `PATCH/DELETE admin/users/<id>/` | staff |
| `/api/blog/` | `GET posts/`, `GET posts/<slug>/` | public (drafts: author + staff only) |
| | `POST posts/` (multipart: `title, excerpt, content, category, is_published, cover_image`) | signed in |
| | `PATCH/DELETE posts/<slug>/` (`remove_cover_image=true` clears the cover) | author or staff |
| | `POST posts/<slug>/like/` (toggle), `POST posts/<slug>/comments/` | signed in |
| | `DELETE comments/<id>/` | comment author or staff |
| `/api/reviews/` | `GET /` | public |
| | `POST /` (creates, or updates your one review), `GET mine/` (`null` if none) | signed in |
| | `DELETE <id>/` | review author or staff |
| `/admin/` | Django admin | superusers/staff |

Lists are plain arrays (not paginated) because the frontend filters them client-side.

## Configuration (`.env`)

See `.env.example`. The important ones: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
(add your LAN IP if you open the site from another device), `CORS_ALLOWED_ORIGINS`
(your frontend's origin), `BLOG_COVER_MAX_BYTES` (default 5 MB, matches the
frontend picker). With `DEBUG=False` the server refuses to start without a `SECRET_KEY`.

## Tests

```bash
python manage.py test        # 79 tests
```

## Going to production

- `DEBUG=False`, a long random `SECRET_KEY`, real `ALLOWED_HOSTS`, `USE_HTTPS=True`,
  and the deployed frontend origin in `CORS_ALLOWED_ORIGINS`. Update the frontend's
  `NEXT_PUBLIC_*_API_URL` values to the deployed API URLs.
- Run behind gunicorn/uvicorn + nginx. Serve `/static/` (`python manage.py collectstatic`)
  and `/media/` (uploaded avatars/covers) from nginx or object storage; Django only serves
  media itself when `DEBUG=True`.
- SQLite is the default. For PostgreSQL: `pip install "psycopg[binary]"` and replace
  `DATABASES` in `config/settings.py`.
- Login and register are rate-limited per IP (10/min, 10/hour); adjust under
  `DEFAULT_THROTTLE_RATES`. Behind a proxy, make sure it forwards the client IP.

## Not included

The contact form still posts to the Next.js route `app/api/contact/route.js`
(it only logs to the console today); this backend doesn't handle it.
