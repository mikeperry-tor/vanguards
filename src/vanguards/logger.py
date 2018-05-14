#!/usr/bin/env python

import logging
import sys

logger = None
loglevel = "DEBUG"
logfile = None

loglevels = { "DEBUG":  logging.DEBUG,
              "INFO":   logging.INFO,
              "NOTICE": logging.INFO + 5,
              "WARN":   logging.WARN,
              "ERROR":  logging.ERROR,
              "NONE":   logging.ERROR + 5 }

def plog(level, msg, *args):
  global logger, logfile
  if not logger:
    # Default init = old TorCtl format + default behavior
    # Default behavior = log to stdout if TorUtil.logfile is None,
    # or to the open file specified otherwise.
    logger = logging.getLogger("TorCtl")
    formatter = logging.Formatter("%(levelname)s[%(asctime)s]:%(message)s",
                                  "%a %b %d %H:%M:%S %Y")

    if not logfile:
      logfile = sys.stdout
    ch = logging.StreamHandler(logfile)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(loglevels[loglevel])

  logger.log(loglevels[level], msg.strip(), *args)


