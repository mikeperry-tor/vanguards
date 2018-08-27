import stem
import sys
import getpass

from .logger import plog

from . import __version__

def authenticate_any(controller, passwd=""):
  try:
    controller.authenticate()
  except stem.connection.MissingPassword:
    if passwd == "":
      passwd = getpass.getpass("Controller password: ")

    try:
      controller.authenticate(password=passwd)
    except stem.connection.PasswordAuthFailed:
      print("Unable to authenticate, password is incorrect")
      sys.exit(1)
  except stem.connection.AuthenticationFailure as exc:
    print("Unable to authenticate: %s" % exc)
    sys.exit(1)

  plog("NOTICE", "Vanguards %s connected to Tor %s using stem %s",
       __version__, controller.get_version(), stem.__version__)

def get_consensus_weights(consensus_filename):
  parsed_consensus = next(stem.descriptor.parse_file(consensus_filename,
                          document_handler =
                            stem.descriptor.DocumentHandler.BARE_DOCUMENT))

  assert(parsed_consensus.is_consensus)
  return parsed_consensus.bandwidth_weights

def try_close_circuit(controller, circ_id):
  try:
    controller.close_circuit(circ_id)
    plog("NOTICE", "We force-closed circuit "+str(circ_id))
  except stem.InvalidRequest as e:
    plog("INFO", "Failed to close circuit "+str(circ_id)+": "+str(e.message))

