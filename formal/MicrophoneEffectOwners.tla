---------------------------- MODULE MicrophoneEffectOwners -------------------
EXTENDS Naturals, Sequences
CONSTANT Wrong
VARIABLE s, lastEvent
vars == <<s, lastEvent>>
Init ==
  /\ s = [one |-> "idle", kind |-> "start", retired |-> FALSE, owner |-> 1,
    held |-> FALSE, two |-> "absent", native |-> 0]
  /\ lastEvent = "init"
BeginOne(kind) ==
  /\ s.one = "idle"
  /\ s' = [s EXCEPT !.one = "pending", !.kind = kind, !.held = kind = "start"]
  /\ lastEvent' = "effect:first:begin:" \o kind
RetireOne ==
  /\ s.one = "pending" /\ ~s.retired
  /\ s' = [s EXCEPT !.retired = TRUE, !.owner = 0]
  /\ lastEvent' = "effect:first:retire"
MountTwo ==
  /\ s.retired /\ s.two = "absent"
  /\ s' = [s EXCEPT !.owner = 2, !.two = "queued"]
  /\ lastEvent' = "effect:second:mount"
SecondStart ==
  /\ s.two = "queued" /\ (~s.held \/ Wrong = "per-effect-queue")
  /\ s' = [s EXCEPT !.two = "running", !.native = 2]
  /\ lastEvent' = "effect:second:start-complete"
FirstComplete ==
  /\ s.one = "pending" /\ s.retired
  /\ s' = [s EXCEPT !.one = "complete"]
  /\ lastEvent' = "effect:first:complete"
FirstCleanup ==
  /\ s.one = "complete"
  /\ LET stop == s.kind = "start" \/ s.owner = 1 \/ Wrong = "retired-test-stop"
     IN s' = [s EXCEPT !.one = "settled", !.held = FALSE,
       !.native = IF stop THEN 0 ELSE @]
  /\ lastEvent' = "effect:first:cleanup"
Next == (\E kind \in {"start", "test"}: BeginOne(kind))
  \/ RetireOne \/ MountTwo \/ SecondStart \/ FirstComplete \/ FirstCleanup
Spec == Init /\ [][Next]_vars
RetiredEffectCannotStopReplacement == s.one = "settled" /\ s.two = "running" => s.native = 2
\* Replay fixtures resolve the retired promise only after the replacement has
\* started. The unrestricted positive model still checks earlier completions.
LateCompletionWitness == s.one # "complete" \/ s.two = "running"
=============================================================================
