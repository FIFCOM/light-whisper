---------------------- MODULE HistoryLeaseInterleavings ----------------------
EXTENDS Naturals, FiniteSets, Sequences
CONSTANT WrongOrder
VARIABLE s, lastEvent
vars == <<s, lastEvent>>
Tasks == {1, 2}
Audio == {"A", "B"}
Holders(a) == {t \in Tasks: s.holder[t] = a}
Init ==
  /\ s = [holder |-> [t \in Tasks |-> "None"], used |-> {},
    count |-> [a \in Audio |-> 0], rows |-> Audio, files |-> Audio,
    transaction |-> 0, audio |-> "A", phase |-> "idle"]
  /\ lastEvent = "init"
Acquire(t, a) ==
  /\ s.transaction = 0 /\ t \notin s.used /\ a \in s.rows
  /\ s' = [s EXCEPT !.holder[t] = a, !.used = @ \cup {t}, !.count[a] = @ + 1]
  /\ lastEvent' = IF t = 1 THEN "acquire:1:" \o a ELSE "acquire:2:" \o a
Remove(a) ==
  /\ s.transaction = 0 /\ a \in s.rows
  /\ s' = [s EXCEPT !.rows = @ \ {a}]
  /\ lastEvent' = "delete:" \o a
BeginRelease(t) ==
  /\ s.transaction = 0 /\ s.holder[t] # "None" /\ s.holder[t] \notin s.rows
  /\ s' = [s EXCEPT !.transaction = t, !.audio = s.holder[t], !.phase = "delete-one"]
  /\ lastEvent' = IF t = 1 THEN "release:begin:1" ELSE "release:begin:2"
DeleteOne ==
  /\ s.phase = "delete-one"
  /\ s' = [s EXCEPT !.count[s.audio] =
       IF WrongOrder THEN (IF @ > 1 THEN @ - 1 ELSE @)
       ELSE (IF @ = 1 THEN 0 ELSE @), !.phase = "decrement-many"]
  /\ lastEvent' = "release:delete-one"
DecrementMany ==
  /\ s.phase = "decrement-many"
  /\ s' = [s EXCEPT !.count[s.audio] =
       IF WrongOrder THEN (IF @ = 1 THEN 0 ELSE @)
       ELSE (IF @ > 1 THEN @ - 1 ELSE @), !.phase = "commit"]
  /\ lastEvent' = "release:decrement-many"
CommitRelease ==
  /\ s.phase = "commit"
  /\ s' = [s EXCEPT !.holder[s.transaction] = "None", !.transaction = 0, !.phase = "idle"]
  /\ lastEvent' = "release:commit"
Collect(a) ==
  /\ s.transaction = 0 /\ a \notin s.rows /\ s.count[a] = 0 /\ a \in s.files
  /\ s' = [s EXCEPT !.files = @ \ {a}]
  /\ lastEvent' = "gc:" \o a
Next == (\E t \in Tasks, a \in Audio: Acquire(t, a))
  \/ (\E a \in Audio: Remove(a) \/ Collect(a))
  \/ (\E t \in Tasks: BeginRelease(t)) \/ DeleteOne \/ DecrementMany \/ CommitRelease
Spec == Init /\ [][Next]_vars
LeaseCountMatchesHolders == s.transaction = 0 =>
    \A a \in Audio: s.count[a] = Cardinality(Holders(a))
LiveHoldersKeepAudio == \A a \in Audio: Holders(a) # {} => a \in s.files
=============================================================================
