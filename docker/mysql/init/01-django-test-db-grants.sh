#!/usr/bin/env bash
set -euo pipefail

database_name="${MYSQL_DATABASE:-homefinder}"
database_user="${MYSQL_USER:-homefinder_app}"
test_database_name="test_${database_name}"

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
GRANT ALL PRIVILEGES ON \`${test_database_name}\`.* TO '${database_user}'@'%';
FLUSH PRIVILEGES;
SQL
