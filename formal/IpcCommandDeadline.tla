------------------------------ MODULE IpcCommandDeadline ---------------------
EXTENDS Naturals
CONSTANT Wrong
VARIABLE s, lastEvent
vars == <<s, lastEvent>>
Init ==
  /\ s = [phase |-> "idle", elapsed |-> 0, deadline |-> 3,
    process |-> TRUE, locked |-> FALSE, used |-> FALSE]
  /\ lastEvent = "init"
Begin ==
  /\ ~s.used
  /\ s' = [s EXCEPT !.phase = "write", !.locked = TRUE, !.used = TRUE]
  /\ lastEvent' = "ipc:begin"
Advance ==
  /\ s.phase \in {"write", "flush"}
  /\ s' = [s EXCEPT !.phase = IF @ = "write" THEN "flush" ELSE "read",
    !.deadline = IF Wrong = "reset" THEN s.elapsed + 3 ELSE @]
  /\ lastEvent' = IF s.phase = "write" THEN "ipc:write:complete" ELSE "ipc:flush:complete"
Tick ==
  /\ s.locked /\ s.elapsed < 6
  /\ LET expired == s.elapsed + 1 >= s.deadline /\ ~(Wrong = "write-unbounded" /\ s.phase = "write")
     IN s' = [s EXCEPT !.elapsed = @ + 1,
       !.phase = IF expired THEN "invalid" ELSE @,
       !.process = IF expired THEN FALSE ELSE @,
       !.locked = IF expired THEN FALSE ELSE @]
  /\ lastEvent' = "ipc:tick"
Cancel ==
  /\ s.locked
  /\ s' = [s EXCEPT !.phase = "invalid", !.locked = FALSE, !.process = IF Wrong = "cancel-reuse" THEN @ ELSE FALSE]
  /\ lastEvent' = "ipc:cancel"
Reply ==
  /\ s.phase = "read"
  /\ s' = [s EXCEPT !.phase = "done", !.locked = FALSE]
  /\ lastEvent' = "ipc:reply"
Next == Begin \/ Advance \/ Tick \/ Cancel \/ Reply
Spec == Init /\ [][Next]_vars
OneTotalDeadline == s.elapsed >= 3 => ~s.locked
InvalidFrameCannotBeReused == s.phase = "invalid" => ~s.process /\ ~s.locked
=============================================================================
