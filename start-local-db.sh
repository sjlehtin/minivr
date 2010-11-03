#!/bin/sh

# This script starts a postgres server running under a temp directory
# and with the current user account for test purposes.

if test '!' -d db; then
  initdb db
fi

pg_ctl -D db -l db.log start
