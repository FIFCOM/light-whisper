---------------------- MODULE EngineConfigurationWrites ----------------------
EXTENDS Naturals
CONSTANT Serialize
Writers == {"engine", "model", "gpu", "models_dir"}
Fields == Writers \cup {"unknown"}
EmptyConfig == [field \in Fields |-> IF field = "unknown" THEN 7 ELSE 0]
VARIABLE s

\* One process, one update per writer. Atomic replacement either publishes the
\* complete snapshot or fails without changing disk. The mutex covers read,
\* mutation and replacement; it also releases when replacement fails.
Init == s = [disk |-> EmptyConfig,
  snapshot |-> [writer \in Writers |-> EmptyConfig],
  phase |-> [writer \in Writers |-> "New"], owner |-> "None"]
Begin(writer) ==
  /\ s.phase[writer] = "New"
  /\ ~Serialize \/ s.owner = "None"
  /\ s' = [s EXCEPT !.snapshot[writer] = s.disk,
    !.phase[writer] = "Writing",
    !.owner = IF Serialize THEN writer ELSE @]
Finish(writer, success) ==
  /\ s.phase[writer] = "Writing" /\ success \in BOOLEAN
  /\ ~Serialize \/ s.owner = writer
  /\ s' = [s EXCEPT
    !.disk = IF success THEN [s.snapshot[writer] EXCEPT ![writer] = 1] ELSE @,
    !.phase[writer] = IF success THEN "Done" ELSE "Failed",
    !.owner = IF Serialize THEN "None" ELSE @]
Next == \E writer \in Writers:
  Begin(writer) \/ (\E success \in BOOLEAN: Finish(writer, success))
Spec == Init /\ [][Next]_s
  /\ \A writer \in Writers:
    WF_s(\E success \in BOOLEAN: Finish(writer, success))
TypeOK ==
  /\ s.disk \in [Fields -> {0, 1, 7}]
  /\ s.snapshot \in [Writers -> [Fields -> {0, 1, 7}]]
  /\ s.phase \in [Writers -> {"New", "Writing", "Done", "Failed"}]
  /\ s.owner \in Writers \cup {"None"}
CommittedUpdatesPreserved == \A writer \in Writers:
  s.phase[writer] = "Done" => s.disk[writer] = 1
UnknownFieldsPreserved == s.disk["unknown"] = 7
OwnerMatchesActiveTransaction ==
  s.owner # "None" => s.phase[s.owner] = "Writing"
TransactionsSettle == \A writer \in Writers:
  (s.phase[writer] = "Writing") ~> (s.phase[writer] \in {"Done", "Failed"})
=============================================================================
