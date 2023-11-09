#!/usr/bin/env python3
import copy
import datetime
import decimal
import pdb
import time

import dateutil.parser
import pytz
import singer
import singer.metadata as metadata
import singer.metrics as metrics
import tap_oracle.db as orc_db
import tap_oracle.sync_strategies.common as common
from singer import get_bookmark, utils, write_message
from singer.schema import Schema
from tap_oracle.connection_helper import oracledb

LOGGER = singer.get_logger()

UPDATE_BOOKMARK_PERIOD = 1000

SCN_WINDOW_SIZE = None
CALL_TIMEOUT = None
DYNAMIC_SCN_WINDOW_SIZE = False
ITER_WITH_REDUCTION_FACTOR = 10

BATCH_SIZE = 1000

def get_connection_with_common_user_or_default(conn_config):
    cdb_conn_config = conn_config.copy()
    if conn_config.get('common_user') and conn_config.get('common_password') and (conn_config.get('common_service_name') or conn_config.get('common_sid')):
        cdb_conn_config['user'] = conn_config.get('common_user')
        cdb_conn_config['password'] = conn_config.get('common_password')
        cdb_conn_config['sid'] = conn_config.get('common_sid')
        cdb_conn_config['service_name'] = conn_config.get('common_service_name')

    return orc_db.open_connection(cdb_conn_config)

def fetch_current_scn(conn_config):
   connection = get_connection_with_common_user_or_default(conn_config)
   cur = connection.cursor()
   current_scn = cur.execute("SELECT current_scn FROM V$DATABASE").fetchall()[0][0]
   cur.close()
   connection.close()
   return current_scn

def add_automatic_properties(stream):
   stream.schema.properties['scn'] = Schema(type = ['integer'])
   stream.schema.properties['_sdc_deleted_at'] = Schema(
            type=['null', 'string'], format='date-time')

   return stream

def get_stream_version(tap_stream_id, state):
   stream_version = singer.get_bookmark(state, tap_stream_id, 'version')

   if stream_version is None:
      raise Exception("version not found for log miner {}".format(tap_stream_id))

   return stream_version

def row_to_singer_message(stream, row, version, columns, time_extracted):
    row_to_persist = ()
    for idx, elem in enumerate(row):
        property_type = stream.schema.properties[columns[idx]].type
        multiple_of = stream.schema.properties[columns[idx]].multipleOf
        format = stream.schema.properties[columns[idx]].format #date-time
        if elem is None:
            row_to_persist += (elem,)
        elif 'integer' in property_type or property_type == 'integer':
            integer_representation = int(elem)
            row_to_persist += (integer_representation,)
        elif ('number' in property_type or property_type == 'number') and multiple_of:
            decimal_representation = decimal.Decimal(elem)
            row_to_persist += (decimal_representation,)
        elif ('number' in property_type or property_type == 'number'):
            row_to_persist += (float(elem),)
        elif format == 'date-time':
            row_to_persist += (elem,)
        else:
            row_to_persist += (elem,)

    rec = dict(zip(columns, row_to_persist))
    return singer.RecordMessage(
        stream=stream.tap_stream_id,
        record=rec,
        version=version,
        time_extracted=time_extracted)

def verify_db_supplemental_log_level(connection):
   cur = connection.cursor()
   cur.execute("SELECT SUPPLEMENTAL_LOG_DATA_ALL FROM V$DATABASE")
   result = cur.fetchone()[0]

   LOGGER.info("supplemental log level for database: %s", result)
   cur.close()
   return result == 'YES'

def verify_table_supplemental_log_level(stream, connection):
   cur = connection.cursor()
   cur.execute("""SELECT * FROM ALL_LOG_GROUPS WHERE table_name = :table_name AND LOG_GROUP_TYPE = 'ALL COLUMN LOGGING'""", table_name = stream.table)
   result = cur.fetchone()
   LOGGER.info("supplemental log level for table(%s): %s", stream.table, result)
   cur.close()
   return result is not None

def sync_tables(conn_config, streams, state, end_scn, scn_window_size = None):
   connection = get_connection_with_common_user_or_default(conn_config)

   if CALL_TIMEOUT:
      connection.call_timeout = CALL_TIMEOUT

   if not verify_db_supplemental_log_level(connection):
      for stream in streams:
         if not verify_table_supplemental_log_level(stream, connection):
            raise Exception("""
      Unable to replicate with logminer for stream({}) because supplmental_log_data is not set to 'ALL' for either the table or the database.
      Please run: ALTER DATABASE ADD SUPPLEMENTAL LOG DATA (ALL) COLUMNS;
            """.format(stream.tap_stream_id))

   cur = connection.cursor()
   cur.arraysize = BATCH_SIZE
   cur.execute("ALTER SESSION SET TIME_ZONE = '00:00'")
   cur.execute("""ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD"T"HH24:MI:SS."00+00:00"'""")
   cur.execute("""ALTER SESSION SET NLS_TIMESTAMP_FORMAT='YYYY-MM-DD"T"HH24:MI:SSXFF"+00:00"'""")
   cur.execute("""ALTER SESSION SET NLS_TIMESTAMP_TZ_FORMAT  = 'YYYY-MM-DD"T"HH24:MI:SS.FFTZH:TZM'""")

   start_scn_window = min([get_bookmark(state, s.tap_stream_id, 'scn') for s in streams])


   reduction_factor = 0
   iter_with_reduction_factor = ITER_WITH_REDUCTION_FACTOR
   while start_scn_window < end_scn:
      stop_scn_window = min(start_scn_window + SCN_WINDOW_SIZE, end_scn) if SCN_WINDOW_SIZE else end_scn

      if DYNAMIC_SCN_WINDOW_SIZE and reduction_factor > 0 and iter_with_reduction_factor > 0:
         stop_scn_window = start_scn_window + int((stop_scn_window - start_scn_window) / (10 ** reduction_factor))

      try:
         state = sync_tables_logminer(cur, streams, state, start_scn_window, stop_scn_window)

         if reduction_factor > 0:
            iter_with_reduction_factor -= 1

            if iter_with_reduction_factor == 0:
                reduction_factor = max(0, reduction_factor - 1)
                iter_with_reduction_factor = ITER_WITH_REDUCTION_FACTOR
      except oracledb.DatabaseError as ex:
         cur.execute("DBMS_LOGMNR.END_LOGMNR()")
         cur.close()
         LOGGER.warning(f"Exception at start_scn={start_scn_window} stop_scn={stop_scn_window} reduction_factor={reduction_factor}")
         iter_with_reduction_factor = ITER_WITH_REDUCTION_FACTOR
         if DYNAMIC_SCN_WINDOW_SIZE and reduction_factor < 5:
            reduction_factor += 1
            connection = get_connection_with_common_user_or_default(conn_config)
            if CALL_TIMEOUT:
                connection.call_timeout = CALL_TIMEOUT
            cur = connection.cursor()
            cur.execute("ALTER SESSION SET TIME_ZONE = '00:00'")
            cur.execute("""ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD"T"HH24:MI:SS."00+00:00"'""")
            cur.execute("""ALTER SESSION SET NLS_TIMESTAMP_FORMAT='YYYY-MM-DD"T"HH24:MI:SSXFF"+00:00"'""")
            cur.execute("""ALTER SESSION SET NLS_TIMESTAMP_TZ_FORMAT  = 'YYYY-MM-DD"T"HH24:MI:SS.FFTZH:TZM'""")
            continue
         else:
            raise ex

      start_scn_window = stop_scn_window

   cur.close()
   connection.close()

def sync_tables_logminer(cur, streams, state, start_scn, end_scn):

   time_extracted = utils.now()

   start_logmnr_sql = """BEGIN
                         DBMS_LOGMNR.START_LOGMNR(
                                 startScn => {},
                                 endScn => {},
                                 OPTIONS => DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG +
                                            DBMS_LOGMNR.COMMITTED_DATA_ONLY +
                                            DBMS_LOGMNR.CONTINUOUS_MINE);
                         END;""".format(start_scn, end_scn)

   LOGGER.info("Starting LogMiner for %s: %s -> %s", list(map(lambda s: s.tap_stream_id, streams)), start_scn, end_scn)
   LOGGER.info("%s",start_logmnr_sql)
   cur.execute(start_logmnr_sql)

   #mine changes
   for stream in streams:
      md_map = metadata.to_map(stream.metadata)
      desired_columns = [c for c in stream.schema.properties.keys() if common.should_sync_column(md_map, c)]
      redo_value_sql_clause = ",\n ".join(["""DBMS_LOGMNR.MINE_VALUE(REDO_VALUE, :{})""".format(idx+1)
                                           for idx,c in enumerate(desired_columns)])
      undo_value_sql_clause = ",\n ".join(["""DBMS_LOGMNR.MINE_VALUE(UNDO_VALUE, :{})""".format(idx+1)
                                           for idx,c in enumerate(desired_columns)])

      schema_name = md_map.get(()).get('schema-name')
      stream_version = get_stream_version(stream.tap_stream_id, state)
      mine_sql = """
      SELECT OPERATION, SQL_REDO, SCN, CSCN, COMMIT_TIMESTAMP,  {}, {} from v$logmnr_contents where table_name = :table_name AND seg_owner = :seg_owner AND operation in ('INSERT', 'UPDATE', 'DELETE')
      """.format(redo_value_sql_clause, undo_value_sql_clause)
      binds = [orc_db.fully_qualified_column_name(schema_name, stream.table, c) for c in desired_columns] + \
              [orc_db.fully_qualified_column_name(schema_name, stream.table, c) for c in desired_columns] + \
              [stream.table] + [schema_name]


      rows_saved = 0
      columns_for_record = desired_columns + ['scn', '_sdc_deleted_at']
      with metrics.record_counter(None) as counter:
         
         counter.tags["schema"] = schema_name
         counter.tags["table"] = stream.table
         
         LOGGER.info("Examining log for table %s", stream.tap_stream_id)
         common.send_schema_message(stream, ['lsn'])
         LOGGER.info("mine_sql=%s", mine_sql)
         for op, redo, scn, cscn, commit_ts, *col_vals in cur.execute(mine_sql, binds):
            redo_vals = col_vals[0:len(desired_columns)]
            undo_vals = col_vals[len(desired_columns):]
            if op == 'INSERT' or op == 'UPDATE':
               redo_vals += [cscn, None]
               record_message = row_to_singer_message(stream, redo_vals, stream_version, columns_for_record, time_extracted)
            elif op == 'DELETE':
               undo_vals += [cscn, singer.utils.strftime(commit_ts.replace(tzinfo=pytz.UTC))]
               record_message = row_to_singer_message(stream, undo_vals, stream_version, columns_for_record, time_extracted)
            else:
               raise Exception("unrecognized logminer operation: {}".format(op))

            singer.write_message(record_message)
            rows_saved = rows_saved + 1
            counter.increment()
            state = singer.write_bookmark(state,
                                          stream.tap_stream_id,
                                          'scn',
                                          int(cscn))


            if rows_saved % UPDATE_BOOKMARK_PERIOD == 0:
               singer.write_message(singer.StateMessage(value=copy.deepcopy(state)))

   for s in streams:
      LOGGER.info("updating bookmark for stream %s to end_lsn %s", s.tap_stream_id, end_scn)
      state = singer.write_bookmark(state, s.tap_stream_id, 'scn', end_scn)
      singer.write_message(singer.StateMessage(value=copy.deepcopy(state)))

   return state
