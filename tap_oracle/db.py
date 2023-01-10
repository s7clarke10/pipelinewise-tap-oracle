import singer
import oracledb

LOGGER = singer.get_logger()

def fully_qualified_column_name(schema, table, column):
    return '"{}"."{}"."{}"'.format(schema, table, column)

def make_dsn(config):
    if config.get("service_name"):
        return oracledb.makedsn(host=config["host"], port=config["port"], service_name=config.get("service_name"))
    else:
        return oracledb.makedsn(host=config["host"], port=config["port"], sid=config.get("sid"))

def open_connection(config):
    LOGGER.info("dsn: %s", make_dsn(config))
    conn = oracledb.connect(user=config["user"], password=config["password"], dsn=make_dsn(config))
    return conn
    