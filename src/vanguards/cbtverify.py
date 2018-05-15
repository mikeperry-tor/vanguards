""" This code monitors the circuit build timeout. It is non-essential """

class CircuitStat:
  def __init__(self, circ_id, is_hs):
    self.circ_id = circ_id
    self.is_hs = is_hs

class TimeoutStats:
  def __init__(self):
    self.circuits = {}
    self.all_launched = 0
    self.all_built = 0
    self.all_timeout = 0
    self.hs_launched = 0
    self.hs_built = 0
    self.hs_timeout = 0
    self.hs_changed = 0

  def circ_event(self, event):
    is_hs = event.hs_state or event.purpose[0:2] == "HS"

    if event.status == "LAUNCHED":
      self.add_circuit(event.id, is_hs)
    elif event.status == "BUILT":
      self.built_circuit(event.id)
    elif event.reason == "TIMEOUT":
      self.timeout_circuit(event.id)
    self.update_circuit(event.id, is_hs)

  def cbt_event(self, event):
    # TODO: Check if this is too high...
    plog("INFO", "CBT Timeout rate: "+str(event.timeout_rate)+"; Our measured timeout rate: "+str(timeouts.timeout_rate_all())+"; Hidden service timeout rate: "+str(timeouts.timeout_rate_hs()))
    plog("DEBUG", event.raw_content())

  def add_circuit(self, circ_id, is_hs):
    if circ_id in self.circuits:
      plog("WARN", "Circuit "+circ_id+" already exists in map!")
    self.circuits[circ_id] = CircuitStat(circ_id, is_hs)
    self.all_launched += 1
    if is_hs: self.hs_launched += 1

  def update_circuit(self, circ_id, is_hs):
    if circ_id not in self.circuits: return
    if self.circuits[circ_id].is_hs != is_hs:
      self.hs_changed += 1
      self.hs_launched += 1
      self.circuits[circ_id].is_hs = is_hs

  def built_circuit(self, circ_id):
    if circ_id in self.circuits:
      self.all_built += 1
      if self.circuits[circ_id].is_hs:
        self.hs_built += 1
      del self.circuits[circ_id]

  def timeout_circuit(self, circ_id):
    if circ_id in self.circuits:
      self.all_timeout += 1
      if self.circuits[circ_id].is_hs:
        self.hs_timeout += 1
      del self.circuits[circ_id]

  def timeout_rate_all(self):
    if self.all_launched:
      return float(self.all_timeout)/(self.all_launched)
    else: return 0.0

  def timeout_rate_hs(self):
    if self.hs_launched:
      return float(self.hs_timeout)/(self.hs_launched)
    else: return 0.0



