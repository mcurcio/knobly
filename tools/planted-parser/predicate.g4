// refused: a semantic predicate
// A predicate makes a decision depend on run-time state; the generator decides from the grammar alone.
grammar Predicate;

start : {true}? WORD EOF ;
WORD  : [a-z]+ ;
