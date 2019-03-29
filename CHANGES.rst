0.3.1:
- Workaround for dropped cell WARNS due to Tor bugs #29699, #29700,
  #29786, and #29927. These cases are now logged at INFO/NOTICE, with
  specific Tor bug number for each case. #37
- Re-apply vanguard config params upon SIGHUP. #40.

0.3.0
-----
- Apply bandguards limits to non-HS circuits too. #34.

0.2.3
-----
- Global option to disable circuit killing. #32.
- Fix config parsing of boolean values. #36.
- Add tests/default.conf to sdist/pip tarball. #27
- Do not allow any dropped cells if Tor 0.3.4.10+ is being used. #25 and #3.
- Retry Tor connection if Tor is missing descriptors at startup. #35.
- Reorganized README_SECURITY to link to specific mitigation sections for each
  adversary attack.

0.2.2
-----
- Fix exception when a connection to a guard is closed with more than one
  live circuit. #29
- Catch control+c and exit cleanly. #30.
- Use Tor's network liveness events to double-check connectivity.
- Print out relevant versions at startup.

0.2.1
-----

- Read ExcludeNodes from Tor and don't pick layer2 or layer3 guards in this
  set. #11
- Add --one_shot_vanguards and --disable_vanguards options (to enable
  OnionBalance synchronization). #12
- Don't write to torrc by default. #18
- Keep attempting to reconnect if the control port dies. #19
- Support tighter bounds on dropped data to defend against DropMark,
  and change circ_max_dropped_bytes_percent to circ_max_dropped_cells.
  However, leave these at NOTICE pending Tor patch #25573. #20.
- Limit rend requests from relays that are not in our consensus. #22.
- Added connectivity accounting: WARN if we're disconnected or can't build
  circuits for more than 'conn_max_disconnected_secs' and
  'circ_max_disconnected_secs'. Also emit a NOTICE if a connection dies while 
  there are live circuits on it. #23
- Fix several false positive cases in rendguard. More may remain, so demote
  logline to NOTICE for now. #24
- Change rendguard params to lower the false positive rate. If you use a
  conf file, be sure to update the values there, if specified. #24.
- Standardize using WARN for messages that we're confident represent
  serious issues, and use NOTICE for heuristics that may need more tuning.

0.1.1
-----

- Initial release
