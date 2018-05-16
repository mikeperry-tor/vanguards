import stem

from stem.control import Controller
from . import config

def connect():
  if config.CONTROL_SOCKET != None:
    try:
      controller = Controller.from_socket_file(config.CONTROL_SOCKET)
    except stem.SocketError as exc:
      print("Unable to connect to Tor Control Socket at "\
            +config.CONTROL_SOCKET+": %s" % exc)
      sys.exit(1)
  else:
    try:
      controller = Controller.from_port(config.CONTROL_HOST,
                                        config.CONTROL_PORT)
    except stem.SocketError as exc:
      print("Unable to connect to Tor Control Port at "+config.CONTROL_HOST+":"
             +str(config.CONTROL_PORT)+" %s" % exc)
      sys.exit(1)

  try:
    controller.authenticate()
  except stem.connection.MissingPassword:
    pw = getpass.getpass("Controller password: ")

    try:
      controller.authenticate(password = pw)
    except stem.connection.PasswordAuthFailed:
      print("Unable to authenticate, password is incorrect")
      sys.exit(1)
  except stem.connection.AuthenticationFailure as exc:
    print("Unable to authenticate: %s" % exc)
    sys.exit(1)

  print("Tor is running version %s" % controller.get_version())

  return controller

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

