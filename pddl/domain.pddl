; EvacPlan-CSUF: evacuation domain v2 (Phase 2 + earthquake + stair crowding).
; Locations are nodes of data/building.json (corridors, rooms, stairs, elevators, exits).
; The problem generator emits the static facts (connected, stairs-down, elevator-link,
; exit, refuge) from the building graph and the rule layer emits the emergency facts
; (blocked, directed-by-responders, shelter-in-place-ok, shaking).
;
; Action costs make the planner prefer real evacuation: shelter actions cost more
; than any realistic route (checked by tools/check_costs.py), so a group only shelters
; when it cannot get out. shelter-in-place (90) < shelter-and-notify (100).
;
; Stair crowding is opt-in: a problem with (crowding) uses descend-stairs-crowded, a problem
; without it uses plain descend-stairs. Crowding is modelled with time waves and slot
; objects: a stair segment has K slots per wave, a descent takes a slot in the group's
; current wave and moves the group to the next wave, and a group can wait a wave. So no
; more than K groups cross one stair segment in the same wave. Walking does not advance
; the wave: groups are assumed to reach the stairs together (see docs/PROJECT_PLAN.md).
(define (domain evac)
  (:requirements :strips :typing :negative-preconditions :action-costs)
  (:types location group wave slot)

  (:predicates
    ;; building structure (static)
    (connected ?a ?b - location)        ; walkable edge, directed (generator adds both ways)
    (stairs-down ?upper ?lower - location) ; stair node on one floor -> same stair one floor below
    (elevator-link ?a ?b - location)    ; elevator car node on one floor <-> adjacent floor
    (exit ?l - location)                ; door to outside
    (refuge ?l - location)              ; area of refuge (assumption A3: elevator lobby)
    ;; emergency state (from the rule layer)
    (blocked ?l - location)             ; fire, smoke, debris, closed
    (directed-by-responders)            ; responders have authorized elevator use
    (shelter-in-place-ok)               ; emergency type allows plain shelter-in-place (e.g. hazmat)
    (shaking)                           ; earthquake in progress: nobody moves until it stops
    ;; groups
    (at ?g - group ?l - location)
    (mobility-impaired ?g - group)
    (notified ?g - group)               ; responders know where this group is
    (sheltered ?g - group)
    (evacuated ?g - group)
    (safe ?g - group)                   ; goal: evacuated, or sheltered with responders notified
    ;; stair crowding (only used when (crowding) holds)
    (crowding)
    (wave-next ?w ?w2 - wave)           ; time order of the waves
    (group-time ?g - group ?w - wave)   ; the wave the group is currently in
    (slot-of ?s - slot ?upper ?lower - location ?w - wave) ; slot for one stair segment in one wave
    (slot-free ?s - slot))

  (:functions (total-cost) - number)

  ;; Walk along a corridor, through a door, or across an open area.
  (:action move
    :parameters (?g - group ?from ?to - location)
    :precondition (and (at ?g ?from) (connected ?from ?to) (not (blocked ?to)) (not (shaking)))
    :effect (and (not (at ?g ?from)) (at ?g ?to) (increase (total-cost) 1)))

  ;; Take a stair down one floor, no capacity limit. Mobility-impaired groups cannot.
  (:action descend-stairs
    :parameters (?g - group ?upper ?lower - location)
    :precondition (and (at ?g ?upper) (stairs-down ?upper ?lower)
                       (not (blocked ?lower)) (not (mobility-impaired ?g)) (not (shaking))
                       (not (crowding)))
    :effect (and (not (at ?g ?upper)) (at ?g ?lower) (increase (total-cost) 2)))

  ;; Take a stair down one floor using a free slot in the group's current wave.
  (:action descend-stairs-crowded
    :parameters (?g - group ?upper ?lower - location ?w ?w2 - wave ?s - slot)
    :precondition (and (crowding) (at ?g ?upper) (stairs-down ?upper ?lower)
                       (not (blocked ?lower)) (not (mobility-impaired ?g)) (not (shaking))
                       (group-time ?g ?w) (wave-next ?w ?w2)
                       (slot-of ?s ?upper ?lower ?w) (slot-free ?s))
    :effect (and (not (at ?g ?upper)) (at ?g ?lower)
                 (not (slot-free ?s))
                 (not (group-time ?g ?w)) (group-time ?g ?w2)
                 (increase (total-cost) 2)))

  ;; Let a wave pass because the stair is full.
  (:action wait-a-wave
    :parameters (?g - group ?w ?w2 - wave)
    :precondition (and (crowding) (group-time ?g ?w) (wave-next ?w ?w2))
    :effect (and (not (group-time ?g ?w)) (group-time ?g ?w2) (increase (total-cost) 2)))

  ;; Elevators are banned during an emergency unless responders direct their use.
  (:action use-elevator
    :parameters (?g - group ?from ?to - location)
    :precondition (and (at ?g ?from) (elevator-link ?from ?to)
                       (not (blocked ?to)) (directed-by-responders) (not (shaking)))
    :effect (and (not (at ?g ?from)) (at ?g ?to) (increase (total-cost) 1)))

  ;; Leave the building.
  (:action exit-building
    :parameters (?g - group ?l - location)
    :precondition (and (at ?g ?l) (exit ?l) (not (blocked ?l)) (not (shaking)))
    :effect (and (not (at ?g ?l)) (evacuated ?g) (safe ?g) (increase (total-cost) 1)))

  ;; Earthquake: drop, cover and hold on until the shaking stops (global, not per group).
  (:action wait-for-shaking-to-stop
    :parameters ()
    :precondition (shaking)
    :effect (and (not (shaking)) (increase (total-cost) 1)))

  ;; Stay put without alerting anyone. Only when the rule layer allows it. Cheaper than
  ;; walking to a refuge, so a group in hazmat shelters where it is.
  (:action shelter-in-place
    :parameters (?g - group ?l - location)
    :precondition (and (at ?g ?l) (not (blocked ?l)) (shelter-in-place-ok))
    :effect (and (sheltered ?g) (safe ?g) (increase (total-cost) 90)))

  ;; Wait in an area of refuge and tell responders where the group is.
  (:action shelter-and-notify
    :parameters (?g - group ?l - location)
    :precondition (and (at ?g ?l) (refuge ?l) (not (blocked ?l)))
    :effect (and (sheltered ?g) (notified ?g) (safe ?g) (increase (total-cost) 100)))
)
