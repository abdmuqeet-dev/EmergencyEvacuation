; Phase 0 toy domain: a group walks along connected locations to an exit.
(define (domain toy-evac)
  (:requirements :strips :typing)
  (:types location group)
  (:predicates (at ?g - group ?l - location)
               (connected ?a ?b - location)
               (exit ?l - location)
               (evacuated ?g - group))
  (:action move
    :parameters (?g - group ?from ?to - location)
    :precondition (and (at ?g ?from) (connected ?from ?to))
    :effect (and (not (at ?g ?from)) (at ?g ?to)))
  (:action exit-building
    :parameters (?g - group ?l - location)
    :precondition (and (at ?g ?l) (exit ?l))
    :effect (and (not (at ?g ?l)) (evacuated ?g))))
