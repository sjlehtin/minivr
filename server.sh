#!/bin/sh

cd /var/minivr
sudo -u postgres /usr/lib/postgresql/8.3/bin/pg_ctl -D pg/db -l pg/db.log start
cd devsite
sudo -u testuser python manage.py runserver 0.0.0.0:8000
