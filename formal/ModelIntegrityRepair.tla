------------------------------ MODULE ModelIntegrityRepair -------------------
EXTENDS Naturals, Sequences
CONSTANT LegacyFallback
VARIABLE s, lastEvent
vars == <<s, lastEvent>>
Init ==
  /\ s = [fixture |-> FALSE, manifest |-> "absent", large |-> FALSE,
    inspected |-> FALSE, status |-> "unknown", repair |-> FALSE,
    phase |-> "idle", repaired |-> FALSE]
  /\ lastEvent = "init"
Provision(kind) ==
  /\ ~s.fixture
  /\ s' = [s EXCEPT !.fixture = TRUE, !.large = kind # "missing",
    !.manifest = IF kind \in {"valid", "invalid"} THEN kind ELSE "absent"]
  /\ lastEvent' = "cache:fixture:" \o kind
Inspect ==
  /\ s.fixture /\ ~s.inspected /\ s.phase = "idle"
  /\ LET ready == s.large /\ (s.manifest # "invalid" \/ LegacyFallback)
         status == IF ready THEN "ready" ELSE IF s.manifest = "invalid" THEN "corrupt" ELSE "missing"
     IN s' = [s EXCEPT !.inspected = TRUE, !.status = status, !.repair = status # "ready"]
  /\ lastEvent' = "cache:inspect"
RepairBegin ==
  /\ s.inspected /\ s.repair /\ ~s.repaired
  /\ s' = [s EXCEPT !.phase = "download", !.inspected = FALSE]
  /\ lastEvent' = "cache:repair:begin"
RepairComplete ==
  /\ s.phase = "download"
  /\ s' = [s EXCEPT !.phase = "idle", !.manifest = "valid", !.large = TRUE,
    !.repaired = TRUE, !.status = "unknown", !.repair = FALSE]
  /\ lastEvent' = "cache:repair:complete"
Next == Inspect \/ RepairBegin \/ RepairComplete
  \/ (\E k \in {"missing", "legacy", "valid", "invalid"}: Provision(k))
Spec == Init /\ [][Next]_vars
CorruptAlwaysOffersRepair == s.inspected /\ s.manifest = "invalid" => s.status = "corrupt" /\ s.repair
LegacyAbsentManifestStillWorks == s.inspected /\ s.manifest = "absent" /\ s.large => s.status = "ready"
ReadyAfterExplicitRepair == s.repaired /\ s.inspected => s.status = "ready"
\* Deliberately false reachability target, used only to generate a repair replay.
RepairPathNotReached == ~(s.repaired /\ s.inspected /\ s.status = "ready")
InvalidFixtureOnly == ~s.fixture \/ s.manifest = "invalid" \/ s.repaired
=============================================================================
