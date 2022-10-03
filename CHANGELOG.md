# Changelog

## 1.2.2
 * Handling NULL's / None in Singer.Decimal columns.

## 1.2.1
 * Applying cursor array_size to incremental and log_based.
 * Renaming config parameter from `full_table_sync_batch_size` to `cursor_array_size`.
 * Increasing the default array size from 100 to 1000.

## 1.2.0
 * New config option to provide an offset for incremental loads - offset_value.
 * Changing the sort order to sort by the column_id so tables columns match the database source.

## 1.1.9
 * Pulling the database name from the env if v$database is unavailable.

## 1.1.8
 * Swapping singer-python for pipelinewise-singer-python
 * This variant uses orjson for serializing 40-50x faster than other libraries.

## 1.1.7
 * Bumping cx_Oracle to 8.3
 * Removing unnecessary call to get the database name 

## 1.1.6
 * Added support to emit numeric data using the singer.decimal notation to avoid numeric rounding issues.
 * To enable singer.decimal notation add the following config "use_singer_decimal": true

## 1.1.5
 * Large change to incorporate a number of cherry-picked features plus new features, table_filtering, no ora_rowscn full table loads.
   * Reverting commits for treating decimals and floats as singer.decimal.
   * Bumping cx_Oracle to 8.2
   * Adding query timeouts
   * Adding support to connect via service_name
   * Dynamically reduce the SCN_WINDOW_SIZE with timeouts occur
   * Support for Plugable database connections
   * Bumping singer-python to version 5.12.2
   * Allow full_table with no ORA_ROWSCN and order by clause. Note: Not restartable.
   * Adding Datetime, Date, NCLOB, CLOB, and BLOB datatypes
   * Discovery filter to set tables via ENV `MELTANO_EXTRACT__SELECT` or config item `filter_tables`.

## 1.1.2
 * Log value of mine_sql [#30](https://github.com/singer-io/tap-oracle/pull/30)

## 1.1.1
 * Set a maximum length on Singer Decimals, where a decimal past the cap is normalized via `decimal.normalize()` [#28](https://github.com/singer-io/tap-oracle/pull/28)

## 1.1.0
 * Values with Decimal precision will now be written as strings with a custom `singer.decimal` format in order to maintain that precision through the pipeline [#26](https://github.com/singer-io/tap-oracle/pull/26)

## 1.0.1
 * Increase default numeric scale from `6` to `38` [#24](https://github.com/singer-io/tap-oracle/pull/24)

## 1.0.0
 * Backwards incompatible change to the way that data types are discovered and parsed [#22](https://github.com/singer-io/tap-oracle/pull/22)
   * Oracle numeric types with a null scale (`NUMBER` and `NUMBER(*)`) will now be correctly discovered as floating point types rather than integers.
   * This may cause downstream issues with loading and reporting, so a major bump is required.

## 0.3.1
 * Adds handling for columns that do not have a datatype -- those columns will have `inclusion`=`unavailable` and `sql-datatype`=`"None"` [#19](https://github.com/singer-io/tap-oracle/pull/19)

## 0.3.0
 * Adds optional parameter `scn_window_size` to allow for an scn window during logminer replication [#18](https://github.com/singer-io/tap-oracle/pull/18)

## (2020-05-19) - Pipelinewise 1.0.1 

 * Fixed an issue when output messages were not compatible with `pipelinewise-transform-field` component

## (2019-09-08) - Pipelinewise 1.0.0 

 * Initial release and fork of singer `tap-oracle` 0.2.0
 * use `trap_stream_id` as stream in singer messages to make it compatible with PipelineWise components
