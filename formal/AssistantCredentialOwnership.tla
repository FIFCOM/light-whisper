---------------------- MODULE AssistantCredentialOwnership -------------------
EXTENDS Naturals, Sequences, FiniteSets
CONSTANT Wrong
VARIABLE s, lastEvent
vars == <<s, lastEvent>>
Ids == {1, 2}
Providers == {"deepseek", "openai"}
IdText(i) == IF i = 1 THEN "1" ELSE "2"
CurrentReadBase(i) == i = s.latestRead /\ s.readProvider[i] = s.provider
  /\ s.readSwitch[i] = s.switches /\ s.readVersion[i] = s.editVersion
CurrentRead(i) == CurrentReadBase(i) /\ ~s.readDirty[i] /\ ~s.draft[s.provider]
Init ==
  /\ s = [provider |-> "deepseek", switches |-> 0, edits |-> 0, editVersion |-> 0,
    phase |-> [i \in Ids |-> "unused"], owner |-> [i \in Ids |-> "deepseek"],
    retried |-> {}, writer |-> 0, latestEdit |-> [p \in Providers |-> 0],
    diskVersion |-> [p \in Providers |-> 0], draft |-> [p \in Providers |-> FALSE], badProvider |-> FALSE, badOrder |-> FALSE,
    reads |-> 0, readPhase |-> [i \in Ids |-> "unused"], latestRead |-> 0,
    readProvider |-> [i \in Ids |-> "deepseek"], readVersion |-> [i \in Ids |-> 0],
    readSwitch |-> [i \in Ids |-> 0], readDirty |-> [i \in Ids |-> FALSE], badRead |-> FALSE]
  /\ lastEvent = "init"
Edit(i) ==
  /\ i = s.edits + 1 /\ i \in Ids /\ s.reads = s.switches
  /\ s' = [s EXCEPT !.edits = i, !.editVersion = @ + 1, !.phase[i] = "debounced",
    !.owner[i] = s.provider, !.latestEdit[s.provider] = i, !.draft[s.provider] = TRUE]
  /\ lastEvent' = "key:edit:" \o IdText(i) \o ":" \o s.provider
Switch ==
  /\ s.switches < 2 /\ s.reads = s.switches
  /\ s' = [s EXCEPT !.switches = @ + 1, !.provider = IF @ = "deepseek" THEN "openai" ELSE "deepseek"]
  /\ lastEvent' = "key:switch:" \o (IF s.provider = "deepseek" THEN "openai" ELSE "deepseek")
Dispatch(i) ==
  /\ s.phase[i] = "debounced"
  /\ s' = [s EXCEPT !.phase[i] = "queued"]
  /\ lastEvent' = "key:dispatch:" \o IdText(i)
BeginWrite(i) ==
  /\ s.phase[i] = "queued" /\ s.writer = 0
  /\ \A earlier \in Ids: earlier < i => s.phase[earlier] \notin {"queued", "debounced"}
  /\ s' = [s EXCEPT !.phase[i] = "pending", !.writer = i]
  /\ lastEvent' = "key:write:begin:" \o IdText(i)
SaveSuccess(i) ==
  /\ s.phase[i] = "pending" /\ s.writer = i /\ s.reads = s.switches
  /\ LET target == IF Wrong = "provider" THEN s.provider ELSE s.owner[i]
     IN s' = [s EXCEPT !.diskVersion[target] = i, !.phase[i] = "saved", !.writer = 0,
       !.draft[s.owner[i]] = IF s.latestEdit[s.owner[i]] = i THEN FALSE ELSE @,
       !.badProvider = @ \/ target # s.owner[i], !.badOrder = @ \/ s.diskVersion[target] > i]
  /\ lastEvent' = "key:save:success:" \o IdText(i)
SaveFailure(i) ==
  /\ s.phase[i] = "pending" /\ s.writer = i
  /\ s' = [s EXCEPT !.phase[i] = "failed", !.writer = 0]
  /\ lastEvent' = "key:save:failure:" \o IdText(i)
Retry(i) ==
  /\ s.phase[i] = "failed" /\ i \notin s.retried /\ s.latestEdit[s.owner[i]] = i
  /\ s' = [s EXCEPT !.phase[i] = "queued", !.retried = @ \cup {i}]
  /\ lastEvent' = "key:retry:" \o IdText(i)
ReadBegin(i) ==
  /\ i = s.reads + 1 /\ i \in Ids
  /\ (s.reads = 0 => s.switches > 0)
  /\ (s.reads > 0 => s.readSwitch[s.reads] < s.switches)
  /\ s' = [s EXCEPT !.reads = i, !.latestRead = i, !.readPhase[i] = "pending",
    !.readProvider[i] = s.provider, !.readSwitch[i] = s.switches, !.readVersion[i] = s.editVersion,
    !.readDirty[i] = s.draft[s.provider]]
  /\ lastEvent' = "key:read:begin:" \o IdText(i)
ReadComplete(i, success) ==
  /\ s.readPhase[i] = "pending"
  /\ s' = [s EXCEPT !.readPhase[i] = IF success THEN "success" ELSE "failure",
    !.badRead = @ \/ (((Wrong = "stale-failure" /\ i = 1 /\ ~success
       /\ s.readPhase[2] = "success" /\ CurrentRead(2))
       \/ (Wrong = "saved-read" /\ CurrentReadBase(i) /\ ~s.draft[s.provider]) \/ CurrentRead(i)) /\ ~CurrentRead(i))]
  /\ lastEvent' = "key:read:" \o (IF success THEN "success:" ELSE "failure:") \o IdText(i)
Next == Switch \/ (\E i \in Ids: Edit(i) \/ Dispatch(i) \/ BeginWrite(i)
  \/ SaveSuccess(i) \/ SaveFailure(i) \/ Retry(i) \/ ReadBegin(i)
  \/ (\E success \in BOOLEAN: ReadComplete(i, success)))
Spec == Init /\ [][Next]_vars
CapturedProviderReceivesKey == ~s.badProvider
SaveVersionsNeverGoBackwards == ~s.badOrder
OnlyLatestReadPublishes == ~s.badRead
OneWriteOwnsStorage == Cardinality({i \in Ids: s.phase[i] = "pending"}) <= 1
=============================================================================
