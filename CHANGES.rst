0.2.1
-----

- Read ExcludeNodes from Tor and don't pick layer2 or layer3 guards in this
  set. #11
- Add --one_shot_vanguards and --disable_vanguards options (to enable
  OnionBalance synchronization). #12
- Don't write to torrc by default. #18
- Keep attempting to reconnect if the control port dies. #19
- Support tighter bounds on dropped data to defend against DropMark,
  and change circ_max_dropped_bytes_percent to circ_max_dropped_cells. #20.
- Added connectivity accounting: Warn if we're disconnected or can't build
  circuits for more than 'max_disconnected_secs'. Emit a notice if a
  connection dies while there are live circuits on it. #23
- Fix several false positive cases in rendguard. More may remain, so demote
  logline to NOTICE for now. #24

0.1.1
-----

- Initial release
