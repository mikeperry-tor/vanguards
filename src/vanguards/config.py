""" This file contains configuration defaults, options parsing, and config
    file code.
"""
import argparse
import os
import sys

from . import bandguards
from . import rendguard
from . import vanguards
from . import control

from .logger import plog

try:
  from configparser import SafeConfigParser, Error
except ImportError:
  from ConfigParser import SafeConfigParser, Error

################# Global options ##################

# Are use counts enabled?
RENDGUARD_ENABLED=True

BANDGUARDS_ENABLED=True

CBTVERIFY_ENABLED=False

# State file location
STATE_FILE = "vanguards.state"

# Config file location
CONFIG_FILE = "vanguards.conf"

# Loglevel (XXX: use)
LOGLEVEL = "NOTICE"

CONTROL_IP = "127.0.0.1"
CONTROL_PORT = 9051
CONTROL_SOCKET = None

def setup_options():
  global CONTROL_IP, CONTROL_PORT, CONTROL_SOCKET, STATE_FILE
  global BANDGUARDS_ENABLED, RENDGUARD_ENABLED, CBTVERIFY_ENABLED

  parser = argparse.ArgumentParser()

  # XXX: add --loglevel and --generate-config
  parser.add_argument("--state", dest="state_file",
                      default=os.environ.get("VANGUARDS_STATE", STATE_FILE),
                      help="File to store vanguard state")

  parser.add_argument("--generate_config", dest="write_file", type=str,
                      help="Write config to a file after applying command args")

  parser.add_argument("--config", dest="config_file",
                      default=os.environ.get("VANGUARDS_CONFIG", CONFIG_FILE),
                      help="Location of config file with more advanced settings")

  parser.add_argument("--control_ip", dest="control_ip", default=CONTROL_IP,
                    help="The IP address of the Tor Control Port to connect to (default: "+
                    CONTROL_IP+")")
  parser.add_argument("--control_port", type=int, dest="control_port",
                      default=CONTROL_PORT,
                      help="The Tor Control Port to connect to (default: "+
                      str(CONTROL_PORT)+")")

  parser.add_argument("--control_socket", dest="control_socket",
                      default=CONTROL_SOCKET,
                      help="The Tor Control Socket path to connect to "+
                      "(default: "+str(CONTROL_SOCKET)+")")

  parser.add_argument("--disable_bandguards", dest="bandguards_enabled",
                      action="store_false",
                      help="Disable circuit side channel checks (may help performance)")
  parser.set_defaults(bandguards_eabled=BANDGUARDS_ENABLED)

  parser.add_argument("--disable_rendguard", dest="rendguard_enabled",
                      action="store_false",
                      help="Disable rendezvous misuse checks (may help performance)")
  parser.set_defaults(rendguard_enabled=RENDGUARD_ENABLED)

  parser.add_argument("--enable_cbtverify", dest="cbtverify_enabled",
                      action="store_true",
                      help="Enable Circuit Build Time monitoring")
  parser.set_defaults(cbtverify_enabled=CBTVERIFY_ENABLED)

  options = parser.parse_args()

  # If the user specifies a config file, any values there should override
  # any previous config file options, but not options on the command line.
  if options.config_file != CONFIG_FILE:
    if not vanguards.config.apply_config(options.config_file):
      plog("ERROR",
           "Specified config file "+options.config_file+ " can't be read!")
      sys.exit(1)

  (STATE_FILE, CONTROL_IP, CONTROL_PORT, CONTROL_SOCKET, BANDGUARDS_ENABLED,
   RENDGUARD_ENABLED, CBTVERIFY_ENABLED) = \
      (options.state_file, options.control_ip, options.control_port,
       options.control_socket, options.bandguards_enabled,
       options.rendguard_enabled,options.cbtverify_enabled)

  if options.write_file != None:
    config = generate_config()
    config.write(file(options.write_file, "w"))
    plog("NOTICE", "Wrote config to "+options.write_file)
    sys.exit(0)

  return options

# Avoid a big messy dict of defaults. We already have them.
def get_option(config, section, option, default):
  try:
    ret = config.get(section, option)
  except Error:
    return default
  return ret

def get_options_for_module(config, module, section):
  for param in dir(module):
    if param.isupper() and param[0] != '_':
      val = getattr(module, param)
      setattr(module, param,
              get_option(config, section, param.lower(), val))

def set_options_from_module(config, module, section):
  config.add_section(section)
  for param in dir(module):
    if param.isupper() and param[0] != '_':
      val = getattr(module, param)
      config.set(section, param, str(val))

def generate_config():
  config = SafeConfigParser(allow_no_value=True)
  set_options_from_module(config, sys.modules[__name__], "Global")
  set_options_from_module(config, vanguards, "Vanguards")
  set_options_from_module(config, bandguards, "Bandguards")
  set_options_from_module(config, rendguard, "Rendguard")

  return config

def apply_config(config_file):
  config = SafeConfigParser(allow_no_value=True)

  # XXX: Bail if any issues here..
  try:
    config.read(config_file)
  except:
    return 0

  get_options_for_module(config, sys.modules[__name__], "Global")
  get_options_for_module(config, vanguards, "Vanguards")
  get_options_for_module(config, bandguards, "Bandguards")
  get_options_for_module(config, rendguard, "Rendguard")

  return 1
