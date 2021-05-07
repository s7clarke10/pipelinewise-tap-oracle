# pipelinewise-tap-oracle

[![PyPI version](https://badge.fury.io/py/pipelinewise-tap-oracle.svg)](https://badge.fury.io/py/pipelinewise-tap-oracle)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pipelinewise-tap-oracle.svg)](https://pypi.org/project/pipelinewise-tap-oracle/)
[![License: MIT](https://img.shields.io/badge/License-GPLv3-yellow.svg)](https://opensource.org/licenses/GPL-3.0)

[Singer](https://www.singer.io/) tap that extracts data from a [Oracle](https://www.oracle.com/database/) database and produces JSON-formatted data following the [Singer spec](https://github.com/singer-io/getting-started/blob/master/docs/SPEC.md).

This is a [PipelineWise](https://transferwise.github.io/pipelinewise) compatible tap connector.

## How to use it

The recommended method of running this tap is to use it from [PipelineWise](https://transferwise.github.io/pipelinewise). When running it from PipelineWise you don't need to configure this tap with JSON files and most of things are automated. Please check the related documentation at [Tap Oracle](https://transferwise.github.io/pipelinewise/connectors/taps/oracle.html)

If you want to run this [Singer Tap](https://singer.io) independently please read further.

## Log based replication

Tap-Oracle Log-based replication requires some configuration changes in Oracle database:

* Enable `ARCHIVELOG` mode

* Set retention period a reasonable and long enough period, ie. 1 day, 3 days, etc.

* Enable Supplemental logging

### Setting up Log-based replication on a self hosted Oracle Database: 

To verify the current archiving mode, if the result is `ARCHIVELOG`, archiving is enabled:
```
  SQL> SELECT LOG_MODE FROM V$DATABASE
```

To enable `ARCHIVELOG` mode (if not enabled yet):
```
  SQL> SHUTDOWN IMMEDIATE
  SQL> STARTUP MOUNT
  SQL> ALTER DATABASE ARCHIVELOG
  SQL> ALTER DATABASE OPEN
```

To set retention period, use RMAN:
```
  RMAN> CONFIGURE RETENTION POLICY TO RECOVERY WINDOW OF 1 DAYS;
```

To enable supplemental logging:
```
  SQL> ALTER DATABASE ADD SUPPLEMENTAL LOG DATA (ALL) COLUMNS
```

### Setting up Log-based replication on Oracle on Amazon RDS

To set retention period:
```
  begin
      rdsadmin.rdsadmin_util.set_configuration(
          name  => 'archivelog retention hours',
          value => '24');
  end;
```

To enable supplemental logging:
```
  begin
    rdsadmin.rdsadmin_util.alter_supplemental_logging(p_action => 'ADD');
  end;
```

### Install and Run

First, make sure Python 3 is installed on your system or follow these
installation instructions for [Mac](http://docs.python-guide.org/en/latest/starting/install3/osx/) or
[Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-install-python-3-and-set-up-a-local-programming-environment-on-ubuntu-16-04).


It's recommended to use a virtualenv:

```bash
  python3 -m venv venv
  pip install pipelinewise-tap-oracle
```

or

```bash
  python3 -m venv venv
  . venv/bin/activate
  pip install --upgrade pip
  pip install .
```

### Configuration

Running the the tap requires a `config.json` file. Example with the minimal settings:

```json
  {
    "host": "foo.com",
    "port": 1521,
    "user": "my_user",
    "password": "password",
    "sid": "ORCL",
    "filter_schemas": "MY_USER", # optional, note that when this is sent the database that is selected will use filter_schemas directly
    "turn_off_multipleof": true #optional, by default discovery will put multipleOf in each field to denote its type
  }
```

### To run tests:

Tests require Oracle on Amazon RDS >= 12.1, and a user called `ROOT`.

1. Define environment variables that requires running the tests.
```
  export TAP_ORACLE_HOST=<oracle-rds-host>
  export TAP_ORACLE_PORT=<oracle-rds-port>
  export TAP_ORACLE_USER=ROOT
  export TAP_ORACLE_PASSWORD=<oracle-rds-password>
  export TAP_ORACLE_SID=<oracle-rds-sid>
```

1. Install python dependencies in a virtual env and run nose unit and integration tests
```
  python3 -m venv venv
  . venv/bin/activate
  pip install --upgrade pip
  pip install .
  pip install nose
```

3. To run unit tests:
```
  nosetests
```
