------------------------- MODULE ThemeSynchronization -------------------------
EXTENDS Naturals
CONSTANT IndependentSubscribers

Windows == 1..2
Subscribers == 1..2
Themes == {"Light", "Dark", "System"}
StoredValues == Themes \cup {"Invalid", "Removed"}
Normalize(value) == IF value \in Themes THEN value ELSE "System"
Dark(theme, system) == IF theme = "System" THEN system ELSE theme = "Dark"

\* Two windows, each with two mounted hook consumers and one shared DOM.
\* Delivery reads the latest persisted preference, coalescing pending storage
\* notifications. The model makes no delivery-liveness or native-browser claim.
\* DOM application is atomic here; transition interruption and unmount cleanup
\* are exercised by the real-hook tests rather than represented in this model.
VARIABLE s

Init == \E stored \in StoredValues, system \in BOOLEAN:
  LET theme == Normalize(stored)
  IN s = [stored |-> stored, system |-> system, pending |-> {},
    accepted |-> [w \in Windows |-> theme],
    observed |-> [w \in Windows |-> [i \in Subscribers |-> theme]],
    dark |-> [w \in Windows |-> [i \in Subscribers |-> Dark(theme, system)]],
    dom |-> [w \in Windows |-> Dark(theme, system)]]

SelectTheme(w, i, theme) ==
  /\ w \in Windows /\ i \in Subscribers /\ theme \in Themes
  /\ s' = [s EXCEPT !.stored = theme, !.pending = Windows \ {w},
    !.accepted[w] = theme,
    !.observed[w] = [j \in Subscribers |->
      IF IndependentSubscribers /\ j # i THEN s.observed[w][j] ELSE theme],
    !.dark[w] = [j \in Subscribers |->
      IF IndependentSubscribers /\ j # i THEN s.dark[w][j] ELSE Dark(theme, s.system)],
    !.dom[w] = Dark(theme, s.system)]

\* Invalid, removed-key and clear-storage notifications all resolve to System.
StoragePreference(value) ==
  /\ value \in StoredValues
  /\ s' = [s EXCEPT !.stored = value, !.pending = Windows]

DeliverStorage(w) ==
  /\ w \in s.pending
  /\ LET theme == Normalize(s.stored)
     IN s' = [s EXCEPT !.pending = @ \ {w}, !.accepted[w] = theme,
       !.observed[w] = [i \in Subscribers |-> theme],
       !.dark[w] = [i \in Subscribers |-> Dark(theme, s.system)],
       !.dom[w] = Dark(theme, s.system)]

SystemPreference(dark) ==
  /\ dark \in BOOLEAN /\ dark # s.system
  /\ s' = [s EXCEPT !.system = dark,
    !.dark = [w \in Windows |-> [i \in Subscribers |->
      IF s.observed[w][i] = "System" THEN dark ELSE s.dark[w][i]]],
    !.dom = [w \in Windows |->
      IF \E i \in Subscribers: s.observed[w][i] = "System" THEN dark ELSE s.dom[w]]]

Next == (\E w \in Windows, i \in Subscribers, theme \in Themes: SelectTheme(w, i, theme))
  \/ (\E value \in StoredValues: StoragePreference(value))
  \/ (\E w \in Windows: DeliverStorage(w))
  \/ (\E dark \in BOOLEAN: SystemPreference(dark))
Spec == Init /\ [][Next]_s

TypeInvariant ==
  /\ s.stored \in StoredValues /\ s.system \in BOOLEAN /\ s.pending \subseteq Windows
  /\ s.accepted \in [Windows -> Themes]
  /\ s.observed \in [Windows -> [Subscribers -> Themes]]
  /\ s.dark \in [Windows -> [Subscribers -> BOOLEAN]]
  /\ s.dom \in [Windows -> BOOLEAN]
ManualPreferenceRetained == \A w \in Windows:
  s.accepted[w] # "System" => s.dom[w] = Dark(s.accepted[w], s.system)
SystemPreferenceRespected == \A w \in Windows:
  s.accepted[w] = "System" => s.dom[w] = s.system
CurrentSubscribersConsistent == \A w \in Windows, i \in Subscribers:
  /\ s.observed[w][i] = s.accepted[w]
  /\ s.dark[w][i] = Dark(s.accepted[w], s.system)
DeliveredWindowsMatchStorage == \A w \in Windows \ s.pending:
  s.accepted[w] = Normalize(s.stored)
=============================================================================
