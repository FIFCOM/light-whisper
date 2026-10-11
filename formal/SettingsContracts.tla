------------------------- MODULE SettingsContracts -------------------------
EXTENDS Naturals, FiniteSets
CONSTANTS IgnoreStorageFailure, ProfileLoadWorkload
Providers == {"BuiltIn", "Custom"}
Fields == IF ProfileLoadWorkload THEN {"History"}
  ELSE {"Sound", "Input", "Prompt", "Translation", "FastMode", "Reasoning",
  "Vision", "Selection", "Jev", "Structure", "History", "AppRules", "R2T2"}
VARIABLE s
Init == s = [preferences |-> [f \in Fields |-> 0], version |-> 0,
  providers |-> Providers, active |-> "Custom", assistant |-> "Custom",
  selection |-> "Custom", validation |-> "Custom", vision |-> "Custom",
  keyDisk |-> [p \in Providers |-> FALSE], keyRuntime |-> [p \in Providers |-> FALSE],
  error |-> FALSE, failedKeyWasReported |-> TRUE, edits |-> 0,
  urlOpened |-> "None", invalidUrlOpened |-> FALSE, readVersion |-> 0,
  invalidPreferenceChanged |-> FALSE,
  profileState |-> IF ProfileLoadWorkload THEN "Pending" ELSE "Ready",
  profileReads |-> IF ProfileLoadWorkload THEN 1 ELSE 0,
  unreadyProfileWrite |-> FALSE]
\* One failed initial load and a retry; a successful load restores saved values
\* before controls can trigger writes. Existing command workloads stay ready.
RetryProfileLoad ==
  /\ ProfileLoadWorkload /\ s.profileState = "Failed" /\ s.profileReads < 2
  /\ s' = [s EXCEPT !.profileState = "Pending", !.profileReads = @ + 1]
FinishProfileLoad(ok) ==
  /\ ProfileLoadWorkload /\ s.profileState = "Pending" /\ ok \in BOOLEAN
  /\ s' = [s EXCEPT !.profileState = IF ok THEN "Ready" ELSE "Failed",
    !.preferences = IF ok THEN [f \in Fields |-> 2] ELSE @]
Preference(field, value, valid) ==
  /\ field \in Fields /\ value \in 0..2 /\ valid \in BOOLEAN /\ s.edits < 2
  /\ s.profileState = "Ready"
  /\ LET nextValue == IF valid THEN value ELSE s.preferences[field]
     IN s' = [s EXCEPT !.edits = @ + 1, !.error = ~valid,
    !.preferences[field] = nextValue,
    !.invalidPreferenceChanged = s.invalidPreferenceChanged \/ (~valid /\ nextValue # s.preferences[field]),
    !.unreadyProfileWrite = s.unreadyProfileWrite \/ s.profileState # "Ready",
    !.version = IF valid THEN @ + 1 ELSE @]
RemoveProvider ==
  /\ "Custom" \in s.providers
  /\ s.profileState = "Ready"
  /\ s' = [s EXCEPT !.providers = @ \ {"Custom"},
    !.active = "BuiltIn", !.assistant = "BuiltIn",
    !.selection = "BuiltIn", !.validation = "BuiltIn", !.vision = "None",
    !.unreadyProfileWrite = s.unreadyProfileWrite \/ s.profileState # "Ready"]
ProviderEdit(valid) ==
  /\ valid \in BOOLEAN /\ s.edits < 2
  /\ s.profileState = "Ready"
  /\ s' = [s EXCEPT !.edits = @ + 1, !.error = ~valid,
    !.unreadyProfileWrite = s.unreadyProfileWrite \/ s.profileState # "Ready",
    !.version = IF valid THEN @ + 1 ELSE @]
KeyWrite(provider, value, ok) ==
  /\ provider \in Providers /\ value \in BOOLEAN /\ ok \in BOOLEAN /\ s.edits < 2
  /\ s.profileState = "Ready"
  /\ s' = [s EXCEPT !.edits = @ + 1,
    !.unreadyProfileWrite = s.unreadyProfileWrite \/ s.profileState # "Ready",
    !.keyDisk[provider] = IF ok THEN value ELSE @,
    !.keyRuntime[provider] = IF ok \/ IgnoreStorageFailure THEN value ELSE @,
    !.error = ~ok /\ ~IgnoreStorageFailure,
    !.failedKeyWasReported = s.failedKeyWasReported /\ (ok \/ ~IgnoreStorageFailure)]
OpenUrl(purpose, scheme, host, parseOK) ==
  /\ purpose \in {"Source", "Release", "Provider"}
  /\ scheme \in {"Http", "Https", "File", "Javascript", "Other"}
  /\ host \in {"Github", "Other"} /\ parseOK \in BOOLEAN
  /\ LET allowed == parseOK /\
       IF purpose = "Release" THEN scheme = "Https" /\ host = "Github"
       ELSE scheme \in {"Http", "Https"}
     IN s' = [s EXCEPT !.urlOpened = IF allowed THEN purpose ELSE @,
       !.error = ~allowed,
       !.invalidUrlOpened = s.invalidUrlOpened \/ (allowed /\ scheme \in {"File", "Javascript"})]
ReadSnapshot == s' = [s EXCEPT !.readVersion = s.version]
Next == RemoveProvider \/ ReadSnapshot
  \/ RetryProfileLoad \/ (\E ok \in BOOLEAN: FinishProfileLoad(ok))
  \/ (\E field \in Fields, value \in 0..2, valid \in BOOLEAN: Preference(field, value, valid))
  \/ (\E valid \in BOOLEAN: ProviderEdit(valid))
  \/ (\E provider \in Providers, value, ok \in BOOLEAN: KeyWrite(provider, value, ok))
  \/ (\E purpose \in {"Source", "Release", "Provider"},
       scheme \in {"Http", "Https", "File", "Javascript", "Other"},
       host \in {"Github", "Other"}, parseOK \in BOOLEAN: OpenUrl(purpose, scheme, host, parseOK))
Spec == Init /\ [][Next]_s
ResolvedProvidersExist ==
  s.active \in s.providers /\ s.assistant \in s.providers
  /\ s.selection \in s.providers /\ s.validation \in s.providers
  /\ (s.vision = "None" \/ s.vision \in s.providers)
CredentialFailureIsReported == s.failedKeyWasReported
FailedStorageDoesNotPublishKey == s.keyDisk = s.keyRuntime
NoExecutableUrl == ~s.invalidUrlOpened
NoInvalidPreferencePublication == ~s.invalidPreferenceChanged
SnapshotsDoNotPredictFuture == s.readVersion <= s.version
ProfileRequiredForWrites == ~s.unreadyProfileWrite
LoadedProfileRestoresSavedPreferences ==
  ~ProfileLoadWorkload \/ s.profileState # "Ready" \/ s.edits > 0
    \/ s.preferences = [f \in Fields |-> 2]
=============================================================================
