from stem.response import ControlMessage

from vanguards.pathverify import PathVerify

import vanguards.logger
import time

vanguards.logger.loglevel = "INFO"

import stem.util.log
stem.util.log.LOGGER.setLevel("INFO")

from stem.response import ControlMessage

def orconn_event(conn_id, guard, status):
  s= "650 ORCONN "+guard+" "+status+" ID="+str(conn_id)+"\r\n"
  return ControlMessage.from_str(s, "EVENT")

def launched_general_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" LAUNCHED BUILD_FLAGS=ONEHOP_TUNNEL,IS_INTERNAL,NEED_CAPACITY PURPOSE=GENERAL TIME_CREATED=2018-05-13T00:05:18.651833\r\n"
  return ControlMessage.from_str(s, "EVENT")

def launched_hs_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" LAUNCHED BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2018-05-08T17:03:14.906877\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_circ(circ_id, purpose, guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s = "650 CIRC "+str(circ_id)+" BUILT "+guard+",$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$DBD67767640197FF96EC6A87684464FC48F611B6~nocabal,$387B065A38E4DAA16D9D41C2964ECBC4B31D30FF~redjohn1 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+purpose+" TIME_CREATED=2018-05-04T06:09:32.751920\r\n"
  return ControlMessage.from_str(s, "EVENT")

def failed_circ(circ_id):
  s =  "650 CIRC "+str(circ_id)+" FAILED $66CA5474346F35E375C4D4514C51A540545347EE~ToolspireRelay BUILD_FLAGS=IS_INTERNAL,NEED_UPTIME PURPOSE=HS_SERVICE_INTRO HS_STATE=HSSI_CONNECTING REND_QUERY=54dqclf77mj4qkzqjs372aozfykjcvkfrmzmzjkwyyiechicg2ssyfqd TIME_CREATED=2018-05-04T06:08:53.883058 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def closed_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" CLOSED $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$855BC2DABE24C861CD887DB9B2E950424B49FC34~Logforme,$E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005~BensTorRelay,$EAB114DAF0488F1223FF30778468E272E00EDC32~trnyc3 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_CLIENT_REND HS_STATE=HSCR_JOINED REND_QUERY=4u56zw2g4uvyyq7i TIME_CREATED=2018-05-04T05:50:41.751938 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def timeout_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" FAILED $3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$E3F98C86C9E01138DD8EA06B1E660A0CDB4B2782~Finisterre BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2018-05-08T16:14:45.612809 REASON=TIMEOUT\r\n"
  return ControlMessage.from_str(s, "EVENT")

def expired_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" FAILED $3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$E3F98C86C9E01138DD8EA06B1E660A0CDB4B2782~Finisterre BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=MEASURE_TIMEOUT TIME_CREATED=2018-05-08T16:14:45.612809 REASON=MEASUREMENT_EXPIRED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def purpose_changed_circ(circ_id, old_purpose, new_purpose,
                         guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s = "650 CIRC_MINOR "+str(circ_id)+" PURPOSE_CHANGED "+guard+",$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$DBD67767640197FF96EC6A87684464FC48F611B6~nocabal,$387B065A38E4DAA16D9D41C2964ECBC4B31D30FF~redjohn1 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+new_purpose+" OLD_PURPOSE="+old_purpose+" TIME_CREATED=2018-05-04T06:09:32.751920\r\n"
  return ControlMessage.from_str(s, "EVENT")

def purpose_changed_hs_circ(circ_id, old_purpose, new_purpose, old_state, new_state,
                            guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s = "650 CIRC_MINOR "+str(circ_id)+" PURPOSE_CHANGED "+guard+",$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$DBD67767640197FF96EC6A87684464FC48F611B6~nocabal,$387B065A38E4DAA16D9D41C2964ECBC4B31D30FF~redjohn1 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+new_purpose+" HS_STATE="+new_state+" OLD_PURPOSE="+old_purpose+" OLD_HS_STATE="+old_state+" TIME_CREATED=2018-05-04T06:09:32.751920\r\n"
  return ControlMessage.from_str(s, "EVENT")

def cannibalized_circ(circ_id, to_purpose):
  s = "650 CIRC_MINOR "+str(circ_id)+" CANNIBALIZED $FA255D3F828FBBA47FF4848343A92BAEE21B92E7~TorWay1,$6FF440DFB1D0697B942357D747900CC308DD57CC~atlantis,$C86C538EF0A24E010342F30DBCACC2A7EB7CA833~eowyn,$7964E5822260C5129AFDF291853F56D83283A448~lol BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+to_purpose+" HS_STATE=HSCI_CONNECTING TIME_CREATED=2018-05-08T17:02:36.905840 OLD_PURPOSE=HS_VANGUARDS OLD_TIME_CREATED=2018-05-08T17:02:37.943660\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_hsdir_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$CFBBA0D858F02E40B1432A65F6D13C9BDFE7A46B~0x3d001,$81A59766272894D27FE8375C4F83A6BA453671EF~chutney BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY PURPOSE=HS_SERVICE_HSDIR HS_STATE=HSSI_CONNECTING TIME_CREATED=2018-05-04T06:08:59.886885\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_serv_intro_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$CFBBA0D858F02E40B1432A65F6D13C9BDFE7A46B~0x3d001,$81A59766272894D27FE8375C4F83A6BA453671EF~chutney BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY PURPOSE=HS_SERVICE_INTRO HS_STATE=HSSI_CONNECTING TIME_CREATED=2018-05-04T06:08:59.886885\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_general_circ(circ_id, guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s = "650 CIRC "+str(circ_id)+" BUILT "+guard+",$8101421BEFCCF4C271D5483C5AABCAAD245BBB9D~rofltor1,$FDAC8BA3ABFCC107D1B1EAC953F195BEEBA7FF54~Viking,$705DB1E61846652FC447E7EC2DDAE0F7D5407D9E~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY PURPOSE=GENERAL TIME_CREATED=2018-05-04T08:24:07.078225\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_hs_circ(circ_id, purpose, hs_state, guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s =  "650 CIRC "+str(circ_id)+" BUILT "+guard+",$855BC2DABE24C861CD887DB9B2E950424B49FC34~Logforme,$E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005~BensTorRelay,$EAB114DAF0488F1223FF30778468E272E00EDC32~trnyc3 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+purpose+" HS_STATE="+hs_state+" REND_QUERY=4u56zw2g4uvyyq7i TIME_CREATED=2018-05-04T05:50:41.751938\r\n"
  return ControlMessage.from_str(s, "EVENT")


class MockController:
  def __init__(self):
    self.closed_circ = None
    self.bwstats = None
    self.layer1 = []
    self.layer2 = []
    self.layer3 = []
    self._logguard = None

  def signal(self, sig):
    pass

  def close_circuit(self, circ_id):
    self.closed_circ = circ_id
    self.bwstats.circ_event(closed_circ(circ_id))
    raise stem.InvalidRequest("Coverage")

  def get_conf(self, key, default):
    if key == "HSLayer2Nodes":
      return ",".join(self.layer2)
    if key == "HSLayer3Nodes":
      return ",".join(self.layer3)

  def get_info(self, key):
    if key == "orconn-status":
      ret = ""
      for l in self.layer1:
        ret += "$"+l+"~Unnamed CONNECTED\n"
      return ret

class MockEvent:
  def __init__(self, arrived_at):
    self.arrived_at = arrived_at

  def raw_content(self):
    return "nah"

def test_pathverify():
  controller = MockController()

  #
  # Test init with various guard and conf conditions
  # 

  # Test the right number of everything
  controller.layer1 = ["66CA5474346F35E375C4D4514C51A540545347EE", "5416F3E8F80101A133B1970495B04FDBD1C7446B"]
  controller.layer2 = ["5416F3E8F80101A133B1970495B04FDBD1C7446B", "855BC2DABE24C861CD887DB9B2E950424B49FC34",
                       "1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4"]
  controller.layer3 = ["DBD67767640197FF96EC6A87684464FC48F611B6", "E3F98C86C9E01138DD8EA06B1E660A0CDB4B2782",
                       "C86C538EF0A24E010342F30DBCACC2A7EB7CA833", "CFBBA0D858F02E40B1432A65F6D13C9BDFE7A46B",
                       "CFBBA0D858F02E40B1432A65F6D13C9BDFE7A469", "FDAC8BA3ABFCC107D1B1EAC953F195BEEBA7FF54",
                       "E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005", "705DB1E61846652FC447E7EC2DDAE0F7D5407D9E"]
  pv = PathVerify(controller, True, 2, 3, 8)
  assert pv.layer1.check_conn_counts() == 0
  assert pv._check_layer_counts()

  # Test too many guards
  controller.layer1 = ["66CA5474346F35E375C4D4514C51A540545347EE", "5416F3E8F80101A133B1970495B04FDBD1C7446B",
                       "3E53D3979DB07EFD736661C934A1DED14127B684"]
  controller.layer2 = ["5416F3E8F80101A133B1970495B04FDBD1C7446B", "855BC2DABE24C861CD887DB9B2E950424B49FC34",
                       "1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4", "8101421BEFCCF4C271D5483C5AABCAAD245BBB9D",
                       "66CA5474346F35E375C4D4514C51A540545347EE"]
  controller.layer3 = ["DBD67767640197FF96EC6A87684464FC48F611B6", "E3F98C86C9E01138DD8EA06B1E660A0CDB4B2782",
                       "C86C538EF0A24E010342F30DBCACC2A7EB7CA833", "CFBBA0D858F02E40B1432A65F6D13C9BDFE7A46B",
                       "CFBBA0D858F02E40B1432A65F6D13C9BDFE7A469", "FDAC8BA3ABFCC107D1B1EAC953F195BEEBA7FF54",
                       "E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005", "705DB1E61846652FC447E7EC2DDAE0F7D5407D9E",
                       "66CA5474346F35E375C4D4514C51A540545347EE"]
  pv = PathVerify(controller, True, 2, 3, 8)
  assert pv.layer1.check_conn_counts() == 1
  assert not pv._check_layer_counts()

  # Test too few guards
  controller.layer1 = ["66CA5474346F35E375C4D4514C51A540545347EE"]
  controller.layer2 = ["5416F3E8F80101A133B1970495B04FDBD1C7446B", "855BC2DABE24C861CD887DB9B2E950424B49FC34",
                       "1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4", "8101421BEFCCF4C271D5483C5AABCAAD245BBB9D"]
  controller.layer3 = ["DBD67767640197FF96EC6A87684464FC48F611B6", "E3F98C86C9E01138DD8EA06B1E660A0CDB4B2782",
                       "C86C538EF0A24E010342F30DBCACC2A7EB7CA833", "CFBBA0D858F02E40B1432A65F6D13C9BDFE7A46B",
                       "CFBBA0D858F02E40B1432A65F6D13C9BDFE7A469", "FDAC8BA3ABFCC107D1B1EAC953F195BEEBA7FF54",
                       "E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005"]
  pv = PathVerify(controller, True, 2, 3, 8)
  assert pv.layer1.check_conn_counts() == -1
  assert not pv._check_layer_counts()

  #
  # Test orconn event
  #

  # Test enough guards, but insufficient use
  pv.orconn_event(
         orconn_event(11,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  pv.circ_event(built_circ(23, "HS_SERVICE_INTRO",
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  assert pv.layer1.check_conn_counts() == 0
  assert pv.layer1.check_use_counts() == -1

  # Test sufficient use
  pv.circ_event(built_circ(23, "HS_SERVICE_INTRO",
                              "$66CA5474346F35E375C4D4514C51A540545347EE~Unnamed"))
  assert pv.layer1.check_conn_counts() == 0
  assert pv.layer1.check_use_counts() == 0

  # Test too many now
  pv.orconn_event(
         orconn_event(11,"$5416F3E8F80101A133B1970495B04FDBD1C7446D~Unnamed",
                      "CONNECTED"))
  pv.orconn_event(
         orconn_event(11,"$5416F3E8F80101A133B1970495B04FDBD1C7446D~Unnamed",
                      "CONNECTED"))
  pv.circ_event(built_circ(23, "HS_SERVICE_INTRO",
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446D~Unnamed"))
  assert pv.layer1.check_conn_counts() == 1
  assert pv.layer1.check_use_counts() == 1

  # Test closed of one, still too many
  pv.orconn_event(
         orconn_event(11,"$5416F3E8F80101A133B1970495B04FDBD1C7446D~Unnamed",
                      "CLOSED"))
  assert pv.layer1.check_conn_counts() == 1
  assert pv.layer1.check_use_counts() == 1

  # Close the second, and now normal
  pv.orconn_event(
         orconn_event(11,"$5416F3E8F80101A133B1970495B04FDBD1C7446D~Unnamed",
                      "CLOSED"))
  assert pv.layer1.check_conn_counts() == 0
  assert pv.layer1.check_use_counts() == 0

  ev = MockEvent(int(time.time()))
  ev.changed = {"HSLayer2Nodes": ["5416F3E8F80101A133B1970495B04FDBD1C7446D"],
                "HSLayer3Nodes": ["5416F3E8F80101A133B1970495B04FDBD1C7446D"]}
  pv.conf_changed_event(ev)
  assert pv._check_layer_counts() == False

  # Test use of a circuit with no valid layerN relays in it
  # Technically this is just coverage, but coverage is still useful
  pv.circ_event(built_circ(23, "HS_SERVICE_INTRO",
                              "$0416F3E8F80101A133B1970495B04FDBD1C74460~Unnamed"))


  #
  # Test circ_minor changes
  # These are just for coverage, but that is still useful
  #

  # Test circ_minor event invalid purpose change
  pv.circ_event(built_circ(24, "HS_VANGUARDS",
                         "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  pv.circ_minor_event(purpose_changed_circ(24, "HS_VANGUARDS", "GENERAL",
                         "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  pv.circ_minor_event(purpose_changed_circ(24, "GENERAL", "HS_VANGUARDS",
                         "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))

  # Test rando guard and bad pathlen of hsdir, for coverage
  pv.circ_minor_event(purpose_changed_circ(24, "HS_VANGUARDS", "HS_SERVICE_HSDIR",
                         "$9916F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  pv.circ_minor_event(cannibalized_circ(24, "HS_CLIENT_INTRO"))


  # Test wrong pathlens, for coverage
  pv.circ_event(built_hs_circ(23, "HS_CLIENT_INTRO", "HSCI_CONNECTING"))
  pv.circ_event(built_hs_circ(23, "HS_CLIENT_HSDIR", "HSCI_CONNECTING"))
