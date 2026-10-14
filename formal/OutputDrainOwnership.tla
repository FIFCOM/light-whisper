---------------------------- MODULE OutputDrainOwnership ---------------------
EXTENDS Naturals, Sequences
CONSTANT Wrong
VARIABLE s, lastEvent
vars == <<s, lastEvent>>
Init ==
  /\ s = [a |-> "processing", b |-> "idle", queue |-> <<>>,
    scheduled |-> FALSE, target |-> 100, foreground |-> 100,
    delivered |-> "none", changed |-> FALSE, exited |-> FALSE]
  /\ lastEvent = "init"
StartB ==
  /\ s.b = "idle" /\ ~s.exited
  /\ s' = [s EXCEPT !.b = "starting"] /\ lastEvent' = "output:B:start"
StartedB ==
  /\ s.b = "starting"
  /\ s' = [s EXCEPT !.b = "recording"] /\ lastEvent' = "output:B:recording"
CompleteA ==
  /\ s.a = "processing" /\ s.b \in {"starting", "recording"}
  /\ s' = [s EXCEPT !.a = "done", !.queue = <<[session |-> 41, target |-> 100, text |-> "Dictation A"]>>]
  /\ lastEvent' = "output:A:complete"
ChangeTarget ==
  /\ ~s.changed /\ s.delivered = "none"
  /\ s' = [s EXCEPT !.changed = TRUE, !.foreground = 200]
  /\ lastEvent' = "output:target:changed"
ExitB(kind) ==
  /\ s.b \in {"starting", "recording"} /\ ~s.exited
  /\ (kind \in {"cancel", "start_error"} => s.b = "starting")
  /\ (kind \notin {"cancel", "start_error"} => s.b = "recording")
  /\ s' = [s EXCEPT !.b = "idle", !.exited = TRUE,
    !.scheduled = ~((Wrong = "missing-drain" /\ kind # "success") \/ (Wrong = "missing-success" /\ kind = "success") \/ (Wrong = "missing-start-error" /\ kind = "start_error"))]
  /\ lastEvent' = "output:B:exit:" \o kind
Drain ==
  /\ s.scheduled /\ s.b = "idle" /\ Len(s.queue) > 0
  /\ s' = [s EXCEPT !.queue = <<>>, !.scheduled = FALSE,
    !.delivered = IF Wrong = "blind-paste" \/ s.foreground = s.target THEN "paste" ELSE "recovery"]
  /\ lastEvent' = "output:drain"
Next == StartB \/ StartedB \/ CompleteA \/ ChangeTarget \/ Drain
  \/ (\E kind \in {"success", "error", "cancel", "start_error"}: ExitB(kind))
Spec == Init /\ [][Next]_vars
IdlePendingHasScheduledDrain == s.exited /\ Len(s.queue) > 0 => s.scheduled
ChangedTargetNeverBlindPastes == s.delivered = "paste" => s.foreground = s.target
QueuedIdentityRetained == \A i \in 1..Len(s.queue):
    s.queue[i].session = 41 /\ s.queue[i].target = 100 /\ s.queue[i].text = "Dictation A"
=============================================================================
