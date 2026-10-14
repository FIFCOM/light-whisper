------------------------- MODULE MicrophoneAsyncOwnership --------------------
EXTENDS Naturals, Sequences
CONSTANT Wrong
VARIABLE s, lastEvent
vars == <<s, lastEvent>>
Allowed == s.mounted /\ s.active /\ s.enabled /\ ~s.recording /\ s.currentTest = 0
Init ==
  /\ s = [mounted |-> TRUE, active |-> TRUE, enabled |-> TRUE, recording |-> FALSE,
    usedTests |-> {}, pendingTests |-> {}, latestTest |-> 0, currentTest |-> 0,
    invalidated |-> FALSE, reconciled |-> FALSE, generation |-> 0, captured |-> 0,
    phase |-> "idle", running |-> FALSE, ready |-> FALSE, staleResume |-> FALSE]
  /\ lastEvent = "init"
TestBegin(t) ==
  /\ t \in {1, 2} \ s.usedTests /\ (t = 2 => 1 \in s.usedTests)
  /\ s' = [s EXCEPT !.usedTests = @ \cup {t}, !.pendingTests = @ \cup {t},
    !.latestTest = t, !.currentTest = t, !.generation = @ + 1, !.ready = FALSE,
    !.phase = IF s.phase = "start" THEN @ ELSE "stop"]
  /\ lastEvent' = IF t = 1 THEN "mic:test:begin:1" ELSE "mic:test:begin:2"
TestComplete(t, outcome) ==
  /\ t \in s.pendingTests
  /\ LET owns == t = s.currentTest
         resume == owns \/ Wrong = "old-test"
     IN s' = [s EXCEPT !.pendingTests = @ \ {t},
       !.currentTest = IF resume THEN 0 ELSE @,
       !.generation = IF resume THEN @ + 1 ELSE @,
       !.staleResume = @ \/ (resume /\ ~owns),
       !.phase = IF resume /\ s.phase # "start" THEN "stop" ELSE @]
  /\ lastEvent' = "mic:test:" \o outcome \o (IF t = 1 THEN ":1" ELSE ":2")
Reconcile ==
  /\ ~s.reconciled /\ s.phase = "idle"
  /\ s' = [s EXCEPT !.reconciled = TRUE, !.generation = @ + 1, !.phase = "stop"]
  /\ lastEvent' = "mic:reconcile"
Stop ==
  /\ s.phase = "stop"
  /\ s' = [s EXCEPT !.running = FALSE, !.ready = FALSE,
    !.phase = IF Allowed THEN "start" ELSE "settled", !.captured = s.generation]
  /\ lastEvent' = "mic:monitor:stop"
Intent(kind) ==
  /\ ~s.invalidated
  /\ s' = [s EXCEPT !.invalidated = TRUE, !.generation = @ + 1,
    !.enabled = IF kind = "disabled" THEN FALSE ELSE @,
    !.active = IF kind = "inactive" THEN FALSE ELSE @,
    !.mounted = IF kind = "unmounted" THEN FALSE ELSE @,
    !.recording = IF kind = "recording" THEN TRUE ELSE @, !.ready = FALSE,
    !.phase = IF s.phase = "settled" THEN "stop" ELSE @]
  /\ lastEvent' = "mic:intent:" \o kind
StartComplete ==
  /\ s.phase = "start"
  /\ s' = [s EXCEPT !.running = TRUE, !.ready = Allowed /\ s.captured = s.generation,
    !.phase = IF Allowed /\ s.captured = s.generation THEN "settled"
              ELSE IF Wrong = "no-compensation" THEN "settled" ELSE "compensate"]
  /\ lastEvent' = "mic:monitor:start-complete"
Compensate ==
  /\ s.phase = "compensate"
  /\ s' = [s EXCEPT !.running = FALSE, !.phase = IF Allowed THEN "stop" ELSE "settled"]
  /\ lastEvent' = "mic:monitor:compensate"
Next == Reconcile \/ Stop \/ StartComplete \/ Compensate
  \/ (\E t \in {1, 2}: TestBegin(t) \/ (\E o \in {"success", "failure"}: TestComplete(t, o)))
  \/ (\E k \in {"disabled", "inactive", "unmounted", "recording"}: Intent(k))
Spec == Init /\ [][Next]_vars
SettledMonitorHonorsIntent == s.phase = "settled" /\ s.running => Allowed /\ s.captured = s.generation
ReadinessHasCurrentOwner == s.ready => Allowed /\ s.captured = s.generation
OlderTestCannotResume == ~s.staleResume
=============================================================================
