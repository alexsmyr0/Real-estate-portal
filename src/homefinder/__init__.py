try:
    import pymysql
except ModuleNotFoundError:
    pymysql = None
else:
    pymysql.install_as_MySQLdb()
