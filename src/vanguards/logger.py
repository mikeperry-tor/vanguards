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

def set_loglevel(level):
  global loglevel
  if level not in loglevels:
    plog("ERROR", "Invalid loglevel: "+str(level))
    sys.exit(1)
  loglevel = level

def set_logfile(filename):
  global logfile, logger
  try:
    logfile = open(filename, "a")
    logger_init()
  except Exception as e:
    plog("ERROR", "Can't open log file "+str(filename)+": "+str(e))
    sys.exit(1)

def logger_init():
  global logger, logfile

  # Default init = old TorCtl format + default behavior
  # Default behavior = log to stdout if TorUtil.logfile is None,
  # or to the open file specified otherwise.
  logger = logging.getLogger("TorCtl")
  formatter = logging.Formatter("%(levelname)s[%(asctime)s]: %(message)s",
                                "%a %b %d %H:%M:%S %Y")

  if not logfile:
    logfile = sys.stdout
  ch = logging.StreamHandler(logfile)
  ch.setFormatter(formatter)
  logger.addHandler(ch)
  logger.setLevel(loglevels[loglevel])


def plog(level, msg, *args):
  if not logger:
    logger_init()

  logger.log(loglevels[level], msg.strip(), *args)


